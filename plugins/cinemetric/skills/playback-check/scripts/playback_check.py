#!/usr/bin/env python3
"""Cinemetric playback-check: read-only list of files likely to transcode on common devices.

Checks every movie and episode for the few universal causes: image-based subtitles, TrueHD or DTS
audio, and a bitrate above the remote streaming limit. With Tautulli, also shows which devices and
people transcode most, and why. Uses only the Python standard library. Prints one JSON document to
stdout; errors go to stderr.

Safety rules: see openspec/specs/security/spec.md in the Cinemetric repository.
"""

import argparse
import collections
import ipaddress
import json
import os
import re
import ssl
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.26.1"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
LIBRARY_PAGE_SIZE = 500
DETAIL_BATCH = 100
TAUTULLI_PAGE_SIZE = 1000
HISTORY_CAP = 20000
STREAM_DATA_CAP = 200
TOP_GROUPS = 10

# The only Plex server paths this script may request. Details are read for 1 to 100 titles at once.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
    re.compile(r"^/library/metadata/\d+(?:,\d+){0,99}$"),
    re.compile(r"^/:/prefs$"),
]

# The only Tautulli API commands this script may run. All of them only read data.
TAUTULLI_COMMANDS = {
    "get_tautulli_info",
    "get_history",
    "get_stream_data",
}

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
TYPE_MOVIE, TYPE_SHOW, TYPE_EPISODE = 1, 2, 4

# Plex stream types.
AUDIO, SUBTITLE = 2, 3

IMAGE_SUBTITLE_CODECS = {"pgs", "hdmv_pgs_subtitle", "vobsub", "dvd_subtitle", "dvb_subtitle", "xsub"}
DTS_CODECS = {"dca", "dca-ma", "dts"}
COMMON_AUDIO_CODECS = {"ac3", "eac3", "aac"}

CAUSES = ("image_subtitles", "truehd_audio", "dts_audio", "over_bitrate_limit")
# Causes that convert the whole picture, not just the sound. Listed first.
PICTURE_CAUSES = {"image_subtitles", "over_bitrate_limit"}
REASONS = ("subtitles", "video", "audio", "unknown", "not_checked")

LIMITS = (
    "These are likely causes on common devices, not a promise: what each device can play differs. "
    "Image-based subtitles only cause a conversion while subtitles are on, and the bitrate limit "
    "only affects people watching from outside the home network."
)


class ReportError(Exception):
    """An error with a message that is safe to show the user."""


# ---------------------------------------------------------------- config

def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "cinemetric", "config.json")


def read_config_file():
    path = config_path()
    if not os.path.exists(path):
        return {}
    info = os.stat(path)
    if os.name == "posix":
        if info.st_uid != os.getuid():
            raise ReportError(f"Refusing to read {path}: it is owned by another user.")
        if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise ReportError(
                f"Refusing to read {path}: other users can access it. Fix with: chmod 600 {path}"
            )
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ReportError(f"Could not read {path}: {exc.__class__.__name__}") from None
    if not isinstance(data, dict):
        raise ReportError(f"{path} must contain a JSON object.")
    return data


def load_config():
    """Return {"plex": (url, token, verify) or None, "tautulli": (url, key, verify) or None,
    "tautulli_problem": reason or None}.

    Environment variables win over the config file, and the file is only read when the
    environment leaves something missing. If Plex is fully set up from the environment, a
    problem with the file only makes Tautulli unavailable (with the reason) instead of failing.
    """
    env = os.environ.get
    plex_from_env = bool(env("PLEX_URL") and env("PLEX_TOKEN"))
    tautulli_from_env = bool(env("TAUTULLI_URL") and env("TAUTULLI_API_KEY"))
    data, problem = {}, None
    if not (plex_from_env and tautulli_from_env):
        try:
            data = read_config_file()
        except ReportError as exc:
            if not plex_from_env:
                raise
            problem = str(exc)

    plex_url = env("PLEX_URL") or data.get("plex_url")
    plex_token = env("PLEX_TOKEN") or data.get("plex_token")
    taut_url = env("TAUTULLI_URL") or data.get("tautulli_url")
    taut_key = env("TAUTULLI_API_KEY") or data.get("tautulli_api_key")

    config = {"plex": None, "tautulli": None, "tautulli_problem": problem}
    if plex_url and plex_token:
        # Plex from the environment keeps certificate checks on, like the other report scripts.
        verify = True if plex_from_env else data.get("verify_tls", True) is not False
        config["plex"] = (validate_url(plex_url, "plex_url"), str(plex_token).strip(), verify)
    if taut_url and taut_key:
        config["tautulli"] = (validate_url(taut_url, "tautulli_url"), str(taut_key).strip(),
                              data.get("tautulli_verify_tls", True) is not False)
    if not config["plex"] and not config["tautulli"]:
        raise ReportError(
            "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN)."
        )
    return config


def validate_url(url, name):
    parts = urllib.parse.urlsplit(str(url).strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ReportError(f"{name} must look like http://host:port or https://host")
    if parts.username or parts.password:
        raise ReportError(f"{name} must not contain a username or password.")
    if parts.query or parts.fragment:
        raise ReportError(f"{name} must not contain ? or # parts.")
    if parts.scheme == "http" and not looks_local(parts.hostname):
        print(
            f"warning: {name} uses plain http to a non-local address, so your credentials travel "
            "unencrypted. Prefer https for anything outside your home network.",
            file=sys.stderr,
        )
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def looks_local(host):
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return "." not in host or host.endswith((".local", ".lan", ".home.arpa", ".internal"))


# ---------------------------------------------------------------- http

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReportError(
            f"The server answered with a redirect (HTTP {code}). Cinemetric does not follow "
            "redirects so your credentials stay with your server. Use the final address instead."
        )


def build_opener(base_url, verify_tls):
    if base_url.startswith("https://") and not verify_tls:
        print("warning: TLS certificate checking is OFF for " + base_url, file=sys.stderr)
        context = ssl._create_unverified_context()
    else:
        context = ssl.create_default_context()
    return urllib.request.build_opener(_NoRedirect(), urllib.request.HTTPSHandler(context=context))


def fetch_json(opener, request, what, secret):
    def scrub(text):
        return str(text).replace(secret, "[hidden]") if secret else str(text)

    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise ReportError(f"{what} rejected the credentials (HTTP 401 Unauthorized).") from None
        raise ReportError(f"{what} returned HTTP {exc.code}.") from None
    except urllib.error.URLError as exc:
        raise ReportError(f"Could not reach {what}: {scrub(exc.reason)}") from None
    except (TimeoutError, OSError) as exc:
        raise ReportError(f"Network error talking to {what}: {scrub(exc)}") from None
    try:
        return json.loads(body)
    except ValueError:
        raise ReportError(f"{what} sent a response that was not JSON.") from None


class PlexClient:
    def __init__(self, base_url, token, verify_tls):
        self.base_url = base_url
        self._token = token
        self._opener = build_opener(base_url, verify_tls)

    def get(self, path, params=None, start=None, size=None):
        if not any(rule.match(path) for rule in ALLOWED_PATHS):
            raise ReportError(f"Blocked request to a path outside the allowlist: {path}")
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {
            "Accept": "application/json",
            "X-Plex-Token": self._token,
            "X-Plex-Product": "Cinemetric",
            "X-Plex-Version": VERSION,
            "X-Plex-Client-Identifier": "cinemetric-playback-check",
        }
        if start is not None:
            headers["X-Plex-Container-Start"] = str(start)
            headers["X-Plex-Container-Size"] = str(size)
        request = urllib.request.Request(url, headers=headers, method="GET")
        data = fetch_json(self._opener, request, f"the Plex server ({path})", self._token)
        return data.get("MediaContainer", {}) if isinstance(data, dict) else {}


class TautulliClient:
    def __init__(self, base_url, api_key, verify_tls):
        self.base_url = base_url
        self._key = api_key
        self._opener = build_opener(base_url, verify_tls)

    def call(self, command, **params):
        if command not in TAUTULLI_COMMANDS:
            raise ReportError(f"Blocked Tautulli command outside the allowlist: {command}")
        query = urllib.parse.urlencode({"apikey": self._key, "cmd": command, **params})
        request = urllib.request.Request(
            f"{self.base_url}/api/v2?{query}", headers={"Accept": "application/json"}, method="GET"
        )
        data = fetch_json(self._opener, request, "Tautulli", self._key)
        response = data.get("response", {}) if isinstance(data, dict) else {}
        if response.get("result") != "success":
            message = clean(response.get("message")) or "unknown error"
            raise ReportError(f"Tautulli refused {command}: {message}")
        return response.get("data")


# ---------------------------------------------------------------- helpers

def clean(text):
    """Titles and names are untrusted data: strip control characters and cap the length."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text or "")).strip()
    return text[:MAX_TITLE_LENGTH]


def as_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default



def as_bool(value):
    return value is True or str(value).lower() in ("1", "true")


def gb(size):
    return round(size / 1e9, 1)


def share(part, whole):
    return round(100 * part / whole) if whole else 0


# ---------------------------------------------------------------- library

def get_all(client, section_id, type_number):
    """Every item of one type in a section, fetched in pages."""
    path = f"/library/sections/{section_id}/all"
    items, start = [], 0
    while True:
        page = client.get(path, {"type": type_number}, start=start, size=LIBRARY_PAGE_SIZE)
        batch = page.get("Metadata", []) or []
        items.extend(batch)
        total = as_int(page.get("totalSize", page.get("size", len(items))))
        start += len(batch)
        if not batch or start >= total:
            return items


def get_details(client, keys):
    """Rating key -> detail item (with audio and subtitle tracks), read 100 titles per request."""
    keys = [k for k in keys if k.isdigit()]
    details = {}
    for first in range(0, len(keys), DETAIL_BATCH):
        page = client.get("/library/metadata/" + ",".join(keys[first:first + DETAIL_BATCH]))
        for item in page.get("Metadata", []) or []:
            details[str(item.get("ratingKey"))] = item
    return details


def read_once(fn):
    """Call fn the first time only, then hand back the same result (or raise the same error)."""
    saved = []

    def wrapper():
        if not saved:
            try:
                saved.append((fn(), None))
            except ReportError as exc:
                saved.append((None, exc))
        result, error = saved[0]
        if error:
            raise error
        return result
    return wrapper


def remote_limit(read_prefs, wanted):
    """Returns (bitrate_limit, problem). The option wins; otherwise the server's remote limit."""
    if wanted:
        return {"kbps": wanted, "source": "option"}, None
    try:
        prefs = read_prefs()
    except ReportError as exc:
        return None, f"The server's remote streaming limit couldn't be read: {exc}"
    # Only this setting is read here: /:/prefs also holds values that must never be printed.
    for setting in prefs.get("Setting", []) or []:
        if setting.get("id") == "WanPerStreamMaxUploadRate":
            kbps = as_int(setting.get("value"))
            return ({"kbps": kbps, "source": "server"} if kbps > 0 else None), None
    return None, None


def codec(stream):
    return str(stream.get("codec") or "").lower()


def language(stream):
    return stream.get("languageTag") or stream.get("languageCode") or None


def check_file(media, limit_kbps, have_streams):
    """The causes for one media version, plus the details shown for it."""
    streams = [s for part in media.get("Part", []) or [] for s in part.get("Stream", []) or []]
    streams = streams if have_streams else []
    causes = []

    subtitles = [s for s in streams if as_int(s.get("streamType")) == SUBTITLE]
    image = [s for s in subtitles if codec(s) in IMAGE_SUBTITLE_CODECS]
    text_languages = {language(s) for s in subtitles if codec(s) not in IMAGE_SUBTITLE_CODECS}
    # An image-based track counts when it is likely to be the one shown.
    shown = [s for s in image if as_bool(s.get("forced")) or as_bool(s.get("default"))
             or language(s) not in text_languages]
    if shown:
        causes.append("image_subtitles")

    tracks = [s for s in streams if as_int(s.get("streamType")) == AUDIO]
    main = (next((s for s in tracks if as_bool(s.get("selected"))), None)
            or next((s for s in tracks if as_bool(s.get("default"))), None)
            or (tracks[0] if tracks else None))
    if main is not None:
        main_codec, profile = codec(main), main.get("profile")
    elif not have_streams:
        main_codec, profile = str(media.get("audioCodec") or "").lower(), media.get("audioProfile")
    else:
        main_codec, profile = "", None
    audio = None
    if main_codec == "truehd" or main_codec in DTS_CODECS:
        causes.append("truehd_audio" if main_codec == "truehd" else "dts_audio")
        audio = {
            "codec": main_codec,
            "profile": clean(profile) or None,
            "common_alternative": any(codec(s) in COMMON_AUDIO_CODECS for s in tracks if s is not main),
        }

    bitrate = as_int(media.get("bitrate"))
    if limit_kbps and bitrate > limit_kbps:
        causes.append("over_bitrate_limit")

    return {
        "causes": causes,
        "forced_image": any(as_bool(s.get("forced")) for s in image),
        "image_with_text": bool(image) and not shown,
        "image_subtitle_languages": sorted({clean(language(s)) or "unknown" for s in shown}),
        "audio": audio,
        "resolution": media.get("videoResolution"),
        "size_gb": gb(sum(as_int(p.get("size")) for p in media.get("Part", []) or [])),
        "bitrate_kbps": bitrate or None,
    }


def empty_counts():
    counts = {"titles": 0, "files": 0, "unavailable": 0, "details_missing": 0, "files_flagged": 0}
    counts.update({cause: 0 for cause in CAUSES})
    counts.update({"forced_image_subtitles": 0, "image_subtitles_with_text": 0})
    return counts


def sort_listed(entries, *keys):
    """Picture conversions first, then the given counts (most first), then title."""
    entries.sort(key=lambda e: (not e["_picture"], *(-e[k] for k in keys), e["title"].lower()))
    for entry in entries:
        del entry["_picture"]
    return entries


def check_library(client, section, limit_kbps, list_limit):
    is_show = section.get("type") == "show"
    key = section.get("key")
    items = get_all(client, key, TYPE_EPISODE if is_show else TYPE_MOVIE)
    details = get_details(client, [str(item.get("ratingKey")) for item in items])
    counts = empty_counts()
    groups = collections.OrderedDict()
    if is_show:
        for show in get_all(client, key, TYPE_SHOW):
            groups[str(show.get("ratingKey"))] = {
                "title": clean(show.get("title")), "year": as_int(show.get("year")) or None,
                "episodes": 0, "episodes_flagged": 0, **{cause: 0 for cause in CAUSES},
                "_picture": False,
            }

    for item in items:
        counts["titles"] += 1
        detail = details.get(str(item.get("ratingKey")))
        if detail is None:
            counts["details_missing"] += 1
        flagged, causes_here = [], set()
        for media in (detail or item).get("Media", []) or []:
            if media.get("deletedAt"):
                counts["unavailable"] += 1
                continue
            counts["files"] += 1
            result = check_file(media, limit_kbps, detail is not None)
            counts["forced_image_subtitles"] += result["forced_image"]
            counts["image_subtitles_with_text"] += result["image_with_text"]
            if result["causes"]:
                counts["files_flagged"] += 1
                for cause in result["causes"]:
                    counts[cause] += 1
                causes_here.update(result["causes"])
                flagged.append(result)

        if is_show:
            show_key = str(item.get("grandparentRatingKey"))
            show = groups.setdefault(show_key, {
                "title": clean(item.get("grandparentTitle")), "year": None,
                "episodes": 0, "episodes_flagged": 0, **{cause: 0 for cause in CAUSES},
                "_picture": False,
            })
            show["episodes"] += 1
            if flagged:
                show["episodes_flagged"] += 1
                show["_picture"] = show["_picture"] or bool(causes_here & PICTURE_CAUSES)
                for cause in causes_here:
                    show[cause] += 1
        elif flagged:
            groups[str(item.get("ratingKey"))] = {
                "title": clean(item.get("title")), "year": as_int(item.get("year")) or None,
                "files": [{k: r[k] for k in ("resolution", "size_gb", "bitrate_kbps", "causes",
                                              "image_subtitle_languages", "audio")} for r in flagged],
                "_causes": len(causes_here), "_gb": sum(r["size_gb"] for r in flagged),
                "_picture": bool(causes_here & PICTURE_CAUSES),
            }

    if is_show:
        listed = sort_listed([g for g in groups.values() if g["episodes_flagged"]], "episodes_flagged")
    else:
        # Movies rarely have more than one flagged file, so the number of different causes and then
        # the size of the flagged files decide the order.
        listed = sort_listed(list(groups.values()), "_causes", "_gb")
        for entry in listed:
            del entry["_causes"], entry["_gb"]
    return dict(
        {"name": clean(section.get("title")), "type": section.get("type")},
        **counts, listed=listed[:list_limit], more=max(0, len(listed) - list_limit),
    )


# ---------------------------------------------------------------- history

def stream_reasons(data):
    """Why one transcoded play was transcoded, from Tautulli's stream data."""
    data = data if isinstance(data, dict) else {}

    def decision(name):
        return str(data.get("stream_" + name + "_decision") or data.get(name + "_decision") or "").lower()

    reasons = []
    if decision("subtitle") == "burn":
        reasons.append("subtitles")
    elif decision("video") == "transcode":
        reasons.append("video")
    if decision("audio") == "transcode":
        reasons.append("audio")
    return reasons or ["unknown"]


class Group:
    def __init__(self, **label):
        self.label = label
        self.plays = self.direct_play = self.direct_stream = self.transcodes = self.remote = 0
        self.reasons = collections.Counter()

    def add(self, row):
        self.plays += 1
        if row["decision"] == "transcode":
            self.transcodes += 1
            self.remote += row["remote"]
            self.reasons.update(row["reasons"])
        elif row["decision"] == "copy":
            self.direct_stream += 1
        else:
            self.direct_play += 1

    def out(self):
        return dict(self.label, plays=self.plays, direct_play=self.direct_play,
                    direct_stream=self.direct_stream, transcodes=self.transcodes,
                    transcode_share=share(self.transcodes, self.plays), remote_transcodes=self.remote,
                    reasons={r: self.reasons[r] for r in REASONS})


def top(groups, name):
    ranked = [g for g in groups.values() if g.transcodes]
    ranked.sort(key=lambda g: (-g.transcodes, -share(g.transcodes, g.plays), str(g.label[name]).lower()))
    return [g.out() for g in ranked[:TOP_GROUPS]]


def read_plays(client, after):
    """Movie and episode plays since `after`, newest first. Only the fields used are kept."""
    plays = []
    for media_type in ("movie", "episode"):
        start = 0
        while len(plays) < HISTORY_CAP:
            size = min(TAUTULLI_PAGE_SIZE, HISTORY_CAP - len(plays))
            # grouping=1 merges a play that was paused and resumed later into one row.
            page = client.call("get_history", after=after, grouping=1, media_type=media_type,
                               order_column="date", order_dir="desc", start=start, length=size) or {}
            batch = page.get("data", []) or []
            for row in batch:
                if as_int(row.get("live")):
                    continue
                plays.append({
                    "row_id": row.get("row_id"),
                    "date": as_int(row.get("date") or row.get("started")),
                    "decision": str(row.get("transcode_decision") or "").lower(),
                    "remote": str(row.get("location") or "").lower() == "wan",
                    "person": clean(row.get("friendly_name") or row.get("user")) or "Unknown",
                    "device": clean(row.get("player")) or "Unknown",
                    "app": clean(row.get("product")) or None,
                    "platform": clean(row.get("platform")) or None,
                    "title_key": str(row.get("rating_key")),
                    "title": clean(row.get("full_title") or row.get("title")),
                    "reasons": [],
                })
            start += len(batch)
            if len(batch) < size:
                break
    plays.sort(key=lambda p: -p["date"])
    return plays, len(plays) >= HISTORY_CAP


def playback_history(client, days, now):
    after = time.strftime("%Y-%m-%d", time.localtime(now - days * 86400))
    plays, capped = read_plays(client, after)
    transcoded = [p for p in plays if p["decision"] == "transcode"]
    for n, play in enumerate(transcoded):
        if n >= STREAM_DATA_CAP:
            play["reasons"] = ["not_checked"]
        else:
            try:
                play["reasons"] = stream_reasons(client.call("get_stream_data", row_id=play["row_id"]))
            except ReportError:
                play["reasons"] = ["unknown"]  # Tautulli has no stream data for this play

    devices, people, titles = {}, {}, {}
    overall = Group(name="all")
    for play in plays:
        overall.add(play)
        device_key = (play["device"], play["app"], play["platform"])
        devices.setdefault(device_key, Group(device=play["device"], app=play["app"],
                                             platform=play["platform"])).add(play)
        people.setdefault(play["person"], Group(person=play["person"])).add(play)
        if play["decision"] == "transcode":
            title = titles.setdefault(play["title_key"], {"title": play["title"], "transcodes": 0,
                                                           "reasons": collections.Counter()})
            title["transcodes"] += 1
            title["reasons"].update(play["reasons"])

    # A title transcoded once says little about the title, so only repeats are listed.
    ranked_titles = sorted((t for t in titles.values() if t["transcodes"] >= 2),
                           key=lambda t: (-t["transcodes"], t["title"].lower()))
    return {
        "days": days,
        "plays": overall.plays,
        "direct_play": overall.direct_play,
        "direct_stream": overall.direct_stream,
        "transcodes": overall.transcodes,
        "history_capped": capped,
        "reasons": {r: overall.reasons[r] for r in REASONS},
        "devices": top(devices, "device"),
        "people": top(people, "person"),
        "devices_total": len(devices),
        "people_total": len(people),
        "titles": [{"title": t["title"], "transcodes": t["transcodes"],
                    "reasons": {r: t["reasons"][r] for r in REASONS}}
                   for t in ranked_titles[:TOP_GROUPS]],
    }


def history_part(config, days, now):
    """The history fields of the report. Never fails the report."""
    if days == 0:
        return {"playback_history": None,
                "playback_history_note": "Transcode history wasn't checked (--days 0)."}
    if config["tautulli_problem"]:
        return {"playback_history": None,
                "playback_history_error": f"Tautulli settings couldn't be read: {config['tautulli_problem']}"}
    if not config["tautulli"]:
        return {"playback_history": None, "playback_history_note": (
            "Transcodes by device and person need Tautulli, because Plex's own history doesn't "
            "record whether a play was transcoded.")}
    print("reading transcode history from Tautulli", file=sys.stderr)
    try:
        try:
            return {"playback_history": playback_history(TautulliClient(*config["tautulli"]), days, now)}
        except (AttributeError, KeyError, TypeError, IndexError, ValueError):
            raise ReportError("Tautulli sent data in a shape Cinemetric didn't expect.") from None
    except ReportError as exc:
        return {"playback_history": None, "playback_history_error": str(exc)}


# ---------------------------------------------------------------- report

def need_plex(config):
    if not config["plex"]:
        raise ReportError(
            "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN). The library list only "
            "comes from Plex."
        )
    return PlexClient(*config["plex"])


def choose_sections(sections, wanted):
    if wanted:
        names = {name.lower() for name in wanted}
        sections = [s for s in sections if str(s.get("title", "")).lower() in names]
        if not sections:
            raise ReportError("No library matched --library. Run without it to see all names.")
        if not any(s.get("type") in ("movie", "show") for s in sections):
            raise ReportError("Only movie and TV libraries are checked for playback problems.")
    checked = [s for s in sections if s.get("type") in ("movie", "show")]
    skipped = [{"name": clean(s.get("title")), "type": s.get("type")}
               for s in sections if s.get("type") not in ("movie", "show")]
    return checked, skipped


# ---------------------------------------------------------------- media deletion
#
# Shared helper: the same code is in every script that reads from Plex. Keep every copy in step.

def media_deletion_allowed(read_prefs):
    """Whether Plex's "Allow media deletion" setting is on: True, False, or None when it can't be
    told. read_prefs returns the /:/prefs answer. Only this one setting is looked at, since /:/prefs
    also holds values that must never be printed. Never raises: a failed check mustn't stop a report."""
    try:
        prefs = read_prefs()
        settings = prefs.get("Setting", []) if isinstance(prefs, dict) else []
        for setting in settings or []:
            if isinstance(setting, dict) and setting.get("id") == "allowMediaDeletion":
                value = str(setting.get("value")).strip().lower()
                return True if value in ("1", "true") else False if value in ("0", "false") else None
    except Exception:
        pass
    return None


def build_report(config, args, now=None):
    now = time.time() if now is None else now
    client = need_plex(config)
    root = client.get("/")
    sections = client.get("/library/sections").get("Directory", []) or []
    checked, skipped = choose_sections(sections, args.library)
    # One /:/prefs request feeds both the bitrate limit and the media deletion setting.
    prefs = read_once(lambda: client.get("/:/prefs"))
    bitrate_limit, limit_problem = remote_limit(prefs, args.max_bitrate)
    limit_kbps = bitrate_limit["kbps"] if bitrate_limit else 0

    libraries = []
    for section in checked:
        print(f"checking library: {clean(section.get('title'))}", file=sys.stderr)
        libraries.append(check_library(client, section, limit_kbps, args.limit))

    totals = {key: sum(lib[key] for lib in libraries)
              for key in ("titles", "files", "files_flagged") + CAUSES}
    report = {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(now)),
        "server": {"name": clean(root.get("friendlyName")), "version": root.get("version")},
        "bitrate_limit": bitrate_limit,
        "limits": LIMITS,
        "libraries": libraries,
        "skipped_libraries": skipped,
        "totals": totals,
        "media_deletion_allowed": media_deletion_allowed(prefs),
    }
    if limit_problem:
        report["bitrate_limit_problem"] = limit_problem
    report.update(history_part(config, args.days, now))
    return report


def check(config):
    result = {"ok": True, "plex": None, "tautulli": None}
    root = need_plex(config).get("/")
    result["plex"] = {"server": clean(root.get("friendlyName")), "version": root.get("version")}
    if config["tautulli"]:
        try:
            info = TautulliClient(*config["tautulli"]).call("get_tautulli_info") or {}
            result["tautulli"] = {"ok": True, "version": info.get("tautulli_version")}
        except ReportError as exc:
            result["tautulli"] = {"ok": False, "error": str(exc)}
            result["ok"] = False
    elif config["tautulli_problem"]:
        result["tautulli"] = {"ok": False, "error": config["tautulli_problem"]}
        result["ok"] = False
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Read-only list of Plex files likely to transcode, and who transcodes most (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connections")
    parser.add_argument("--library", action="append", help="limit to a library by name (repeatable)")
    parser.add_argument("--limit", type=int, default=25, help="titles listed per library (default 25)")
    parser.add_argument("--max-bitrate", type=int, default=None,
                        help="flag files above this many kbps (default: the server's remote limit)")
    parser.add_argument("--days", type=int, default=90,
                        help="days of Tautulli history to read (default 90, 0 to skip)")
    args = parser.parse_args()
    args.limit = max(0, min(args.limit, 500))
    args.days = max(0, min(args.days, 3650))
    if args.max_bitrate is not None:
        args.max_bitrate = max(100, min(args.max_bitrate, 1000000))

    try:
        config = load_config()
        result = check(config) if args.check else build_report(config, args)
    except ReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    json.dump(result, sys.stdout, indent=1, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
