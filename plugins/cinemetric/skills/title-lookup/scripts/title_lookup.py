#!/usr/bin/env python3
"""Cinemetric title-lookup: read-only answer about one movie, show or episode on a Plex server.

Finds the title, then reports its files and quality, the likely transcode causes for each file (the
same rules as playback-check), its collections, a show's seasons, and who watched it. Uses only the
Python standard library. Prints one JSON document to stdout; errors go to stderr.

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

VERSION = "0.27.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
MAX_SUMMARY_LENGTH = 300
LIBRARY_PAGE_SIZE = 500
DETAIL_BATCH = 100
TAUTULLI_PAGE_SIZE = 1000
HISTORY_CAP = 20000
PLEX_PAGE_SIZE = 500
MAX_MATCHES = 20

# The only Plex server paths this script may request. Details are read for 1 to 100 titles at once.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
    re.compile(r"^/library/metadata/\d+(?:,\d+){0,99}$"),
    re.compile(r"^/library/metadata/\d+/allLeaves$"),
    re.compile(r"^/status/sessions/history/all$"),
    re.compile(r"^/accounts$"),
    re.compile(r"^/:/prefs$"),
]

# The only Tautulli API commands this script may run. All of them only read data.
TAUTULLI_COMMANDS = {
    "get_tautulli_info",
    "get_history",
}

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
TYPE_MOVIE, TYPE_SHOW = 1, 2

# Plex stream types.
VIDEO, AUDIO, SUBTITLE = 1, 2, 3

IMAGE_SUBTITLE_CODECS = {"pgs", "hdmv_pgs_subtitle", "vobsub", "dvd_subtitle", "dvb_subtitle", "xsub"}
DTS_CODECS = {"dca", "dca-ma", "dts"}
COMMON_AUDIO_CODECS = {"ac3", "eac3", "aac"}

CAUSES = ("image_subtitles", "truehd_audio", "dts_audio", "over_bitrate_limit")
# Transfer characteristics Plex reports for HDR video: HDR10 / HDR10+ / Dolby Vision, and HLG.
HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}

LIMITS = (
    "Playback causes are likely on common devices, not a promise: what each device can play differs. "
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
            "X-Plex-Client-Identifier": "cinemetric-title-lookup",
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


# ---------------------------------------------------------------- playback rules
#
# Copied from playback_check.py: the same rules must give the same answer in both scripts.

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


def clean_long(text, length):
    """Like clean, for longer text such as a summary."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(text or "")).strip()[:length]


def when(epoch):
    # Plex uses 0 or -1 for "never".
    epoch = as_int(epoch)
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch)) if epoch > 0 else None


def normalize(text):
    """Title text for matching: case, spaces and punctuation ignored."""
    return re.sub(r"[\W_]+", "", str(text or "").casefold())


def tags(item, name):
    return [clean(t.get("tag")) for t in item.get(name, []) or [] if isinstance(t, dict) and t.get("tag")]


def rating(value):
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- finding the title

def get_listing(client, section_id, type_number, params=None):
    """Items of one type in a section, fetched in pages."""
    path = f"/library/sections/{section_id}/all"
    items, start = [], 0
    while True:
        page = client.get(path, dict({"type": type_number}, **(params or {})),
                          start=start, size=LIBRARY_PAGE_SIZE)
        batch = page.get("Metadata", []) or []
        items.extend(batch)
        total = as_int(page.get("totalSize", page.get("size", len(items))))
        start += len(batch)
        if not batch or start >= total:
            return items


def choose_sections(sections, wanted, kind):
    if wanted:
        names = {name.lower() for name in wanted}
        sections = [s for s in sections if str(s.get("title", "")).lower() in names]
        if not sections:
            raise ReportError("No library matched --library. Run without it to see all names.")
        if not any(s.get("type") in ("movie", "show") for s in sections):
            raise ReportError("Only movie and TV libraries can be searched for a title.")
    types = {"movie": ("movie",), "show": ("show",)}.get(kind, ("movie", "show"))
    return [s for s in sections if s.get("type") in types]


def same_title_key(item):
    """Copies of a title in several libraries share a Plex guid. Unmatched items have none to share."""
    guid = str(item.get("guid") or "")
    return guid if guid and not guid.startswith("local://") else "key:" + str(item.get("ratingKey"))


def find_matches(client, sections, query, year):
    """Every movie and show whose title contains the query, merged across libraries by guid."""
    wanted = normalize(query)

    def search(params):
        found = []
        for section in sections:
            type_number = TYPE_SHOW if section.get("type") == "show" else TYPE_MOVIE
            for item in get_listing(client, section.get("key"), type_number, params):
                titles = (item.get("title"), item.get("originalTitle"))
                if any(wanted in normalize(t) for t in titles if t):
                    found.append((section, item))
        return found

    # Plex's title filter keeps the listing short; if it finds nothing (punctuation such as
    # "Spider-Man" asked for as "spiderman"), read the titles and match here instead.
    found = search({"title": query}) or search(None)
    if year:
        found = [(s, i) for s, i in found if as_int(i.get("year")) == year]
    exact = [(s, i) for s, i in found
             if wanted in (normalize(i.get("title")), normalize(i.get("originalTitle")))]
    found = exact or found

    matches = collections.OrderedDict()
    for section, item in found:
        match = matches.setdefault(same_title_key(item), {"items": []})
        match["items"].append((section, item))
    return list(matches.values())


def describe_match(match):
    section, item = match["items"][0]
    return {
        "rating_key": str(item.get("ratingKey")),
        "title": clean(item.get("title")),
        "year": as_int(item.get("year")) or None,
        "type": "show" if section.get("type") == "show" else "movie",
        "libraries": [clean(s.get("title")) for s, _ in match["items"]],
    }


def match_for_key(client, sections, key):
    """The title with this rating key, plus its copies in other libraries."""
    try:
        found = (client.get(f"/library/metadata/{key}").get("Metadata") or [None])[0]
    except ReportError as exc:
        if "HTTP 404" not in str(exc):
            raise
        found = None
    if not found:
        raise ReportError(f"No title on the server has the rating key {key}.")
    kind = found.get("type")
    if kind not in ("movie", "show", "episode"):
        raise ReportError("Only movies, shows and episodes can be looked up.")
    section = next((s for s in sections if str(s.get("key")) == str(found.get("librarySectionID"))),
                   {"key": found.get("librarySectionID"), "title": found.get("librarySectionTitle"),
                    "type": "show" if kind == "episode" else kind})
    if kind == "episode":
        return {"items": [(section, found)]}, found
    searchable = [s for s in sections if s.get("type") == section.get("type")]
    for match in find_matches(client, searchable, found.get("title") or "", None):
        if any(str(i.get("ratingKey")) == str(key) for _, i in match["items"]):
            return match, None
    return {"items": [(section, found)]}, None


# ---------------------------------------------------------------- details

def get_details(client, keys):
    """Rating key -> detail item (with audio and subtitle tracks), read 100 titles per request."""
    keys = [k for k in keys if k.isdigit()]
    details = {}
    for first in range(0, len(keys), DETAIL_BATCH):
        page = client.get("/library/metadata/" + ",".join(keys[first:first + DETAIL_BATCH]))
        for item in page.get("Metadata", []) or []:
            details[str(item.get("ratingKey"))] = item
    return details


def is_hdr(media):
    video = [s for part in media.get("Part", []) or [] for s in part.get("Stream", []) or []
             if as_int(s.get("streamType")) == VIDEO]
    for stream in video:
        if as_bool(stream.get("DOVIPresent")):
            return True
        if str(stream.get("colorTrc") or "").lower() in HDR_TRANSFERS:
            return True
    return False


def bit_depth(media):
    for part in media.get("Part", []) or []:
        for stream in part.get("Stream", []) or []:
            if as_int(stream.get("streamType")) == VIDEO and as_int(stream.get("bitDepth")):
                return as_int(stream.get("bitDepth"))
    return 10 if "10" in str(media.get("videoProfile") or "") else None


def describe_file(media, library, limit_kbps, have_streams):
    parts = media.get("Part", []) or []
    available = not media.get("deletedAt")
    entry = {
        "library": library,
        "resolution": media.get("videoResolution"),
        "video_codec": media.get("videoCodec"),
        "hdr": is_hdr(media),
        "bit_depth": bit_depth(media),
        "audio_codec": media.get("audioCodec"),
        "audio_channels": as_int(media.get("audioChannels")) or None,
        "container": media.get("container"),
        "bitrate_kbps": as_int(media.get("bitrate")) or None,
        "size_bytes": sum(as_int(p.get("size")) for p in parts),
        "path": clean_long(parts[0].get("file"), 500) if parts else None,
        "available": available,
    }
    if available:
        result = check_file(media, limit_kbps, have_streams)
        entry["playback_causes"] = result["causes"]
        entry["image_subtitle_languages"] = result["image_subtitle_languages"]
        entry["audio"] = result["audio"]
    return entry


def title_facts(item, kind):
    facts = {
        "type": kind,
        "title": clean(item.get("title")),
        "year": as_int(item.get("year")) or None,
        "rating_key": str(item.get("ratingKey")),
        "added_at": when(item.get("addedAt")),
        "content_rating": clean(item.get("contentRating")) or None,
        "genres": tags(item, "Genre"),
        "audience_rating": rating(item.get("audienceRating")),
        "critic_rating": rating(item.get("rating")),
        "collections": tags(item, "Collection"),
        "summary": clean_long(item.get("summary"), MAX_SUMMARY_LENGTH) or None,
    }
    if kind != "show":
        facts["duration_minutes"] = round(as_int(item.get("duration")) / 60000) or None
    if kind == "episode":
        facts.update(show_title=clean(item.get("grandparentTitle")),
                     season=as_int(item.get("parentIndex"), None), episode=as_int(item.get("index"), None))
    return facts


def files_part(client, copies, limit_kbps):
    """copies: [(library name, item)]. Files of every copy, read from the details."""
    details = get_details(client, [str(item.get("ratingKey")) for _, item in copies])
    files = []
    for library, item in copies:
        detail = details.get(str(item.get("ratingKey")))
        for media in (detail or item).get("Media", []) or []:
            files.append(describe_file(media, library, limit_kbps, detail is not None))
    return files, details


def episode_key(item):
    season, number = item.get("parentIndex"), item.get("index")
    if season is None or number is None:
        return ("key", str(item.get("ratingKey")))
    return (as_int(season), as_int(number))


def show_part(client, leaves, limit_kbps):
    """Seasons, sizes and a playback summary for a show's episodes (from every library copy)."""
    episodes = collections.OrderedDict()
    for item in leaves:
        episodes.setdefault(episode_key(item), []).append(item)

    seasons, added = {}, []
    for (season, _), items in episodes.items():
        season = None if season == "key" else season
        row = seasons.setdefault(season, {"season": season, "episodes": 0, "unavailable": 0, "size_bytes": 0})
        media = [m for item in items for m in item.get("Media", []) or []]
        available = [m for m in media if not m.get("deletedAt")]
        if available:
            row["episodes"] += 1
            row["size_bytes"] += sum(as_int(p.get("size")) for m in available for p in m.get("Part", []) or [])
        else:
            row["unavailable"] += 1
        added.extend(as_int(item.get("addedAt")) for item in items if as_int(item.get("addedAt")) > 0)

    details = get_details(client, [str(item.get("ratingKey")) for item in leaves])
    summary = {"files": 0, "files_flagged": 0, "details_missing": 0, **{cause: 0 for cause in CAUSES}}
    for item in leaves:
        detail = details.get(str(item.get("ratingKey")))
        if detail is None:
            summary["details_missing"] += 1
        for media in (detail or item).get("Media", []) or []:
            if media.get("deletedAt"):
                continue
            summary["files"] += 1
            causes = check_file(media, limit_kbps, detail is not None)["causes"]
            summary["files_flagged"] += bool(causes)
            for cause in causes:
                summary[cause] += 1

    ordered = sorted(seasons.values(), key=lambda r: (r["season"] is None, r["season"] or 0))
    for row in ordered:
        row["specials"] = row["season"] == 0
    return {
        "seasons": ordered,
        "episode_count": sum(r["episodes"] for r in ordered),
        "total_size_bytes": sum(r["size_bytes"] for r in ordered),
        "first_added_at": when(min(added)) if added else None,
        "last_added_at": when(max(added)) if added else None,
        "playback_summary": summary,
    }


def get_leaves(client, copies):
    leaves = []
    for _, show in copies:
        leaves.extend(client.get(f"/library/metadata/{show.get('ratingKey')}/allLeaves").get("Metadata", []) or [])
    return leaves


# ---------------------------------------------------------------- watching

class Viewer:
    def __init__(self, name):
        self.name = name
        self.plays = 0
        self.last_played = self.last_finished = 0
        self.finished_episodes = set()
        self.finished = False
        self.furthest = None

    def add(self, date, finished, percent, episode):
        self.plays += 1
        self.last_played = max(self.last_played, date)
        if finished:
            self.finished = True
            self.last_finished = max(self.last_finished, date)
            if episode is not None:
                self.finished_episodes.add(episode)
        if percent is not None:
            self.furthest = max(self.furthest or 0, percent)

    def out(self, is_show, with_percent):
        row = {"name": self.name, "plays": self.plays, "last_played_at": when(self.last_played),
               "finished": self.finished,
               "furthest_percent": min(100, self.furthest or 0) if with_percent else None}
        if is_show:
            row["episodes_finished"] = len(self.finished_episodes)
        return row


def summarize_plays(plays, source, is_show, capped=False):
    """plays: dicts with name, date, finished, percent, episode."""
    viewers = {}
    for play in plays:
        viewers.setdefault(play["name"], Viewer(play["name"])).add(
            play["date"], play["finished"], play["percent"], play["episode"])
    people = sorted(viewers.values(), key=lambda v: (-v.last_played, v.name.lower()))
    finished = [p["date"] for p in plays if p["finished"]]
    result = {
        "source": source,
        "plays": len(plays),
        "last_played_at": when(max((p["date"] for p in plays), default=0)),
        "last_finished_at": when(max(finished, default=0)),
        "people": [v.out(is_show, source == "tautulli") for v in people],
    }
    if source == "plex":
        result["history_capped"] = capped
    return result


def tautulli_plays(client, keys, is_show):
    """Plays of these rating keys (shows by their episodes). Only the fields used are kept."""
    plays = []
    for key in keys:
        start = 0
        while len(plays) < HISTORY_CAP:
            filters = {"grandparent_rating_key": key} if is_show else {"rating_key": key}
            # grouping=1 merges a play that was paused and resumed later into one row.
            page = client.call("get_history", grouping=1, order_column="date", order_dir="desc",
                               start=start, length=TAUTULLI_PAGE_SIZE, **filters) or {}
            batch = page.get("data", []) or []
            for row in batch:
                if as_int(row.get("live")):
                    continue
                episode = ((as_int(row.get("parent_media_index")), as_int(row.get("media_index")))
                           if is_show else None)
                plays.append({
                    "name": clean(row.get("friendly_name") or row.get("user")) or "Unknown",
                    "date": as_int(row.get("date") or row.get("started")),
                    "finished": as_int(row.get("watched_status")) >= 1,
                    "percent": as_int(row.get("percent_complete"), None),
                    "episode": episode,
                })
            start += len(batch)
            if len(batch) < TAUTULLI_PAGE_SIZE:
                break
    return plays


def key_from(value):
    """A rating key from a field like "123" or "/library/metadata/123"."""
    match = re.search(r"(\d+)$", str(value or ""))
    return match.group(1) if match else None


def plex_plays(client, keys, is_show):
    """Finished plays of these rating keys from Plex's own history (shows by their episodes)."""
    accounts = {str(a.get("id")): clean(a.get("name")) or f"user {a.get('id')}"
                for a in client.get("/accounts").get("Account", []) or []}
    plays, read = [], 0
    for key in keys:
        start = 0
        while read < HISTORY_CAP:
            # metadataItemID asks Plex for this title's entries only (a show's covers its episodes).
            page = client.get("/status/sessions/history/all", {"sort": "viewedAt:desc", "metadataItemID": key},
                              start=start, size=PLEX_PAGE_SIZE)
            batch = page.get("Metadata", []) or []
            read += len(batch)
            for entry in batch:
                # Kept only if it really belongs to the title, whatever the filter did.
                if is_show:
                    if key_from(entry.get("grandparentRatingKey") or entry.get("grandparentKey")) != key:
                        continue
                    episode = (as_int(entry.get("parentIndex")), as_int(entry.get("index")))
                else:
                    if key_from(entry.get("ratingKey") or entry.get("key")) != key:
                        continue
                    episode = None
                account = str(entry.get("accountID"))
                plays.append({"name": accounts.get(account, f"user {account}"),
                              "date": as_int(entry.get("viewedAt")), "finished": True, "percent": None,
                              "episode": episode})
            start += len(batch)
            if len(batch) < PLEX_PAGE_SIZE:
                break
    return plays, read >= HISTORY_CAP


def watching_part(config, plex, keys, is_show, source):
    """(fields for the report). Only --source tautulli failing stops the report."""
    fallback_reason = None
    if source in ("auto", "tautulli"):
        if config["tautulli"]:
            print("reading watch history from Tautulli", file=sys.stderr)
            try:
                try:
                    plays = tautulli_plays(TautulliClient(*config["tautulli"]), keys, is_show)
                except (AttributeError, KeyError, TypeError, IndexError, ValueError):
                    raise ReportError("Tautulli sent data in a shape Cinemetric didn't expect.") from None
                return {"fallback_reason": None, "watching": summarize_plays(plays, "tautulli", is_show),
                        "watching_unavailable": None}
            except ReportError as exc:
                if source == "tautulli":
                    raise
                fallback_reason = f"Tautulli is configured but failed: {exc}"
        elif config["tautulli_problem"]:
            fallback_reason = f"Tautulli settings couldn't be read: {config['tautulli_problem']}"
            if source == "tautulli":
                raise ReportError(fallback_reason)
        elif source == "tautulli":
            raise ReportError("TAUTULLI_NOT_CONFIGURED: no Tautulli address and API key are set up.")
        else:
            fallback_reason = "Tautulli is not set up"

    print("reading watch history from Plex", file=sys.stderr)
    try:
        try:
            plays, capped = plex_plays(plex, keys, is_show)
        except (AttributeError, KeyError, TypeError, IndexError, ValueError):
            raise ReportError("Plex sent history in a shape Cinemetric didn't expect.") from None
    except ReportError as exc:
        if "401" in str(exc) or "403" in str(exc):
            reason = ("Plex only shares the server's watch history with the server owner's account. "
                      "Connect with the owner's account, or set up Tautulli.")
        else:
            reason = f"The watch history couldn't be read: {exc}"
        return {"fallback_reason": fallback_reason, "watching": None, "watching_unavailable": reason}
    return {"fallback_reason": fallback_reason, "watching": summarize_plays(plays, "plex", is_show, capped),
            "watching_unavailable": None}


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


# ---------------------------------------------------------------- report

def need_plex(config):
    if not config["plex"]:
        raise ReportError(
            "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN). Titles are looked up on Plex."
        )
    return PlexClient(*config["plex"])


def describe(client, match, episode_item, args, limit_kbps):
    """The title part of the report, the rating keys whose plays count, and whether it's a show."""
    copies = [(clean(section.get("title")), item) for section, item in match["items"]]
    first = copies[0][1]
    kind = "episode" if episode_item is not None else first.get("type") or (
        "show" if match["items"][0][0].get("type") == "show" else "movie")
    extra = {}

    if kind == "show":
        leaves = get_leaves(client, copies)
        wanted = (args.season, args.episode) if args.season is not None else None
        chosen = [leaf for leaf in leaves if wanted and episode_key(leaf) == wanted]
        if wanted and not chosen:
            extra["episode_not_found"] = {"season": args.season, "episode": args.episode}
        if chosen:
            libraries = {str(show.get("ratingKey")): name for name, show in copies}
            copies = [(libraries.get(key_from(leaf.get("grandparentRatingKey")), copies[0][0]), leaf)
                      for leaf in chosen]
            kind = "episode"
        else:
            show_detail = get_details(client, [str(first.get("ratingKey"))]).get(str(first.get("ratingKey")))
            title = title_facts(show_detail or first, "show")
            title["libraries"] = [name for name, _ in copies]
            title.update(show_part(client, leaves, limit_kbps))
            return title, [str(item.get("ratingKey")) for _, item in copies], True, extra

    if episode_item is not None:
        copies = [(copies[0][0], episode_item)]
    files, details = files_part(client, copies, limit_kbps)
    first_detail = details.get(str(copies[0][1].get("ratingKey"))) or copies[0][1]
    title = title_facts(first_detail, kind)
    title["libraries"] = list(collections.OrderedDict.fromkeys(name for name, _ in copies))
    title["files"] = files
    title["total_size_bytes"] = sum(f["size_bytes"] for f in files if f["available"])
    return title, [str(item.get("ratingKey")) for _, item in copies], False, extra


def build_report(config, args, now=None):
    now = time.time() if now is None else now
    client = need_plex(config)
    root = client.get("/")
    sections = client.get("/library/sections").get("Directory", []) or []
    searchable = choose_sections(sections, args.library, args.type)

    report = {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(now)),
        "server": {"name": clean(root.get("friendlyName")), "version": root.get("version")},
        "query": clean(args.title) if args.title else None,
    }
    episode_item = None
    if args.key:
        match, episode_item = match_for_key(client, sections, args.key)
        matches = [match]
    else:
        matches = find_matches(client, searchable, args.title, args.year)
    report["match_count"] = len(matches)
    if len(matches) != 1:
        report["matches"] = [describe_match(m) for m in matches[:MAX_MATCHES]]
        report["title"] = None
        report["media_deletion_allowed"] = media_deletion_allowed(lambda: client.get("/:/prefs"))
        return report

    match = matches[0]
    if args.season is not None and episode_item is None and match["items"][0][0].get("type") != "show":
        raise ReportError("--season and --episode only apply to shows.")
    # One /:/prefs request feeds both the bitrate limit and the media deletion setting.
    prefs = read_once(lambda: client.get("/:/prefs"))
    bitrate_limit, limit_problem = remote_limit(prefs, args.max_bitrate)
    limit_kbps = bitrate_limit["kbps"] if bitrate_limit else 0

    title, keys, is_show, extra = describe(client, match, episode_item, args, limit_kbps)
    report["matches"] = []
    report["title"] = title
    report.update(extra)
    report["bitrate_limit"] = bitrate_limit
    if limit_problem:
        report["bitrate_limit_problem"] = limit_problem
    report["limits"] = LIMITS
    report.update(watching_part(config, client, keys, is_show, args.source))
    report["media_deletion_allowed"] = media_deletion_allowed(prefs)
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only answer about one movie, show or episode on Plex (JSON output).")
    parser.add_argument("title", nargs="?", help="the title to look up")
    parser.add_argument("--key", help="the rating key of the title (from an earlier list of matches)")
    parser.add_argument("--year", type=int, help="only titles from this year")
    parser.add_argument("--library", action="append", help="only search this library (repeatable)")
    parser.add_argument("--type", choices=("movie", "show"), help="only movies or only shows")
    parser.add_argument("--season", type=int, help="season number, with --episode")
    parser.add_argument("--episode", type=int, help="episode number, with --season")
    parser.add_argument("--source", choices=("auto", "tautulli", "plex"), default="auto",
                        help="where watch history comes from (default auto: Tautulli if set up)")
    parser.add_argument("--max-bitrate", type=int, default=None,
                        help="flag files above this many kbps (default: the server's remote limit)")
    parser.add_argument("--check", action="store_true", help="only test the connections")
    args = parser.parse_args(argv)
    if args.check:
        return args
    if bool(args.title and args.title.strip()) == bool(args.key):
        parser.error("give a title or --key (one of them, not both)")
    if args.key is not None and not args.key.isdigit():
        parser.error("--key must be a rating key: digits only")
    if (args.season is None) != (args.episode is None):
        parser.error("--season and --episode go together")
    for name in ("season", "episode"):
        if getattr(args, name) is not None and getattr(args, name) < 0:
            parser.error(f"--{name} must be 0 or more")
    for name in ("year", "max_bitrate"):
        if getattr(args, name) is not None and getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be a positive whole number")
    if args.max_bitrate is not None:
        args.max_bitrate = max(100, min(args.max_bitrate, 1000000))
    return args


def main():
    args = parse_args()
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
