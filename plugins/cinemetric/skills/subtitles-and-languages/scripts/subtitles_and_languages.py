#!/usr/bin/env python3
"""Cinemetric subtitles-and-languages: read-only check of the audio and subtitle languages on a Plex server.

Lists files with audio in another language and no subtitles in the user's language, files with no
subtitles in the user's language at all, and files with tracks that have no language set, plus a
summary of the languages in each library. Goes by the language labels on each track. Uses only the
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

VERSION = "0.29.2"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
LIBRARY_PAGE_SIZE = 500
DETAIL_BATCH = 100
MAX_LANGUAGES = 5
SUMMARY_LANGUAGES = 15
MAX_RANGES_PER_SHOW = 30
MAX_UNNUMBERED_PER_SHOW = 10

# The only Plex server paths this script may request. Details are read for 1 to 100 titles at once.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
    re.compile(r"^/library/metadata/\d+(?:,\d+){0,99}$"),
    re.compile(r"^/:/prefs$"),
]

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
TYPE_MOVIE, TYPE_SHOW, TYPE_EPISODE = 1, 2, 4

# Plex stream types.
AUDIO, SUBTITLE = 2, 3

FINDINGS = ("foreign_no_subtitles", "no_subtitles", "unknown_language")
# Findings that need the user's language. They are null for a library with no language to go by.
LANGUAGE_FINDINGS = ("foreign_no_subtitles", "no_subtitles")

# Codes that mean "no particular language": undetermined, unknown, several, uncoded, no speech.
NO_LANGUAGE = {"und", "unk", "mul", "mis", "zxx"}
# Plex's code for a library with no metadata language.
NO_LIBRARY_LANGUAGE = "xn"
# Three-letter codes people sometimes type (bibliographic) -> the ones Plex uses (terminology).
BIBLIOGRAPHIC = {
    "alb": "sqi", "arm": "hye", "baq": "eus", "bur": "mya", "chi": "zho", "cze": "ces", "dut": "nld",
    "fre": "fra", "geo": "kat", "ger": "deu", "gre": "ell", "ice": "isl", "mac": "mkd", "mao": "mri",
    "may": "msa", "per": "fas", "rum": "ron", "slo": "slk", "tib": "bod", "wel": "cym",
}

LIMITS = (
    "This goes by the language labels on each track, which can be wrong or missing. Forced subtitle "
    "tracks usually only cover signs or a few lines, so they aren't counted as full subtitles. A film "
    "mostly in your language can still have short scenes in another language, which this can't see."
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
            "X-Plex-Client-Identifier": "cinemetric-subtitles-and-languages",
        }
        if start is not None:
            headers["X-Plex-Container-Start"] = str(start)
            headers["X-Plex-Container-Size"] = str(size)
        request = urllib.request.Request(url, headers=headers, method="GET")
        data = fetch_json(self._opener, request, f"the Plex server ({path})", self._token)
        return data.get("MediaContainer", {}) if isinstance(data, dict) else {}


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
    return str(value).strip().lower() in ("1", "true", "yes")


def ranges(numbers):
    """[3, 5, 6, 7] -> [[3, 3], [5, 7]]."""
    result = []
    for n in sorted(numbers):
        if result and n == result[-1][1] + 1:
            result[-1][1] = n
        else:
            result.append([n, n])
    return result


# ---------------------------------------------------------------- libraries

def need_plex(config):
    if not config["plex"]:
        raise ReportError(
            "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN)."
        )
    return PlexClient(*config["plex"])


def choose_sections(sections, wanted):
    if wanted:
        names = {name.lower() for name in wanted}
        sections = [s for s in sections if str(s.get("title", "")).lower() in names]
        if not sections:
            raise ReportError("No library matched --library. Run without it to see all names.")
        if not any(s.get("type") in ("movie", "show") for s in sections):
            raise ReportError("Only movie and TV libraries are checked for languages.")
    checked = [s for s in sections if s.get("type") in ("movie", "show")]
    skipped = [{"name": clean(s.get("title")), "type": s.get("type")}
               for s in sections if s.get("type") not in ("movie", "show")]
    return checked, skipped


def get_all(client, section_id, type_number, extra=None):
    """Every item of one type in a section, fetched in pages."""
    path = f"/library/sections/{section_id}/all"
    params = {"type": type_number, **(extra or {})}
    items, start = [], 0
    while True:
        page = client.get(path, params, start=start, size=LIBRARY_PAGE_SIZE)
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


# ---------------------------------------------------------------- languages

def primary(value):
    """The language part of a tag or code in lower case ("en-US" -> "en"), or None."""
    code = re.split(r"[-_]", str(value or "").strip().lower(), maxsplit=1)[0]
    return code if re.fullmatch(r"[a-z]{2,8}", code) and code not in NO_LANGUAGE else None


def track_language(stream):
    """A track's language: the first part of its languageTag, otherwise its languageCode."""
    tag = str(stream.get("languageTag") or "").strip()
    return primary(tag) if tag else primary(stream.get("languageCode"))


def matches(stream, wanted):
    """Whether a track is in one of the wanted languages (by its language or its three-letter code)."""
    code = primary(stream.get("languageCode"))
    return track_language(stream) in wanted or (code is not None and code in wanted)


def parse_languages(values):
    """The --language values as Plex codes, in the order given, without repeats."""
    if len(values) > MAX_LANGUAGES:
        raise ReportError(f"At most {MAX_LANGUAGES} languages can be given with --language.")
    codes = []
    for value in values:
        code = re.split(r"[-_]", str(value).strip().lower(), maxsplit=1)[0]
        if not re.fullmatch(r"[a-z]{2,3}", code):
            raise ReportError(
                f"--language needs a 2 or 3 letter language code such as en, es or eng, not "
                f"{clean(value)!r}.")
        code = BIBLIOGRAPHIC.get(code, code)
        if code not in codes:
            codes.append(code)
    return codes


def library_language(section):
    """The library's metadata language as a code, or None when it has none to go by."""
    code = primary(section.get("language"))
    return code if code and len(code) <= 3 and code != NO_LIBRARY_LANGUAGE else None


def main_audio(tracks):
    """The audio track marked selected, otherwise the one marked default, otherwise the first.
    The same rule as playback-check's main audio track."""
    return (next((s for s in tracks if as_bool(s.get("selected"))), None)
            or next((s for s in tracks if as_bool(s.get("default"))), None)
            or (tracks[0] if tracks else None))


def unique(values):
    return list(dict.fromkeys(values))


def check_file(media, wanted, names):
    """The findings for one media version, plus the details shown for it. wanted is None when the
    library has no language to go by. names collects the language names Plex gives."""
    streams = [s for part in media.get("Part", []) or [] for s in part.get("Stream", []) or []]
    audio = [s for s in streams if as_int(s.get("streamType")) == AUDIO]
    subtitles = [s for s in streams if as_int(s.get("streamType")) == SUBTITLE]
    full = [s for s in subtitles if not as_bool(s.get("forced"))]
    forced = [s for s in subtitles if as_bool(s.get("forced"))]
    for stream in audio + subtitles:
        code, name = track_language(stream), clean(stream.get("language"))
        if code and name and not names.get(code):
            names[code] = name

    findings, forced_only = [], False
    if wanted is not None:
        has_full = any(matches(s, wanted) for s in full)
        if (any(track_language(s) for s in audio) and not any(matches(s, wanted) for s in audio)
                and not has_full):
            findings.append("foreign_no_subtitles")
        if not has_full:
            findings.append("no_subtitles")
            forced_only = any(matches(s, wanted) for s in forced)
    unknown_audio = sum(track_language(s) is None for s in audio)
    unknown_subtitles = sum(track_language(s) is None for s in subtitles)
    if unknown_audio or unknown_subtitles:
        findings.append("unknown_language")

    main = main_audio(audio)
    return {
        "findings": findings,
        "forced_only": forced_only,
        "resolution": media.get("videoResolution"),
        "main_audio_language": (track_language(main) or "unknown") if main is not None else None,
        "audio_languages": unique(track_language(s) or "unknown" for s in audio),
        "subtitle_languages": sorted({track_language(s) or "unknown" for s in full}),
        "forced_subtitle_languages": sorted({track_language(s) or "unknown" for s in forced}),
        "unknown_audio_tracks": unknown_audio,
        "unknown_subtitle_tracks": unknown_subtitles,
    }


def summary(counter):
    """The most common languages (at most 15), most files first, with the rest under "other"."""
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    result = dict(ranked[:SUMMARY_LANGUAGES])
    rest = sum(n for _, n in ranked[SUMMARY_LANGUAGES:])
    if rest:
        result["other"] = rest
    return result


# ---------------------------------------------------------------- libraries checked

def episode_number(value):
    """A season or episode number as a whole number, or None when it's missing or not a number."""
    text = str(value if value is not None else "").strip()
    return int(text) if text.isdigit() else None


def note_episode(entry, item, some_versions):
    """Record one flagged episode on its show's entry: by season and episode number, or by title and
    air date when Plex has no number for it. Repeats of the same number count once."""
    season, number = episode_number(item.get("parentIndex")), episode_number(item.get("index"))
    if season is not None and number is not None:
        key = (season, number)
        entry["numbered"][key] = entry["numbered"].get(key, False) or some_versions
    else:
        aired = str(item.get("originallyAvailableAt") or "").strip()
        entry["unnumbered"].append({
            "title": clean(item.get("title")),
            "aired": aired if re.fullmatch(r"\d{4}-\d{2}-\d{2}", aired) else None,
            "some_versions": some_versions,
        })


def episode_numbers(numbered, unnumbered):
    """A show's flagged episodes as ranges per season (at most 30 ranges) and its unnumbered ones
    (at most 10), with how many episodes each cap left out."""
    seasons, given, left_out = [], 0, 0
    for season in sorted({s for s, _ in numbered}):
        numbers = sorted(n for s, n in numbered if s == season)
        kept = ranges(numbers)[:max(0, MAX_RANGES_PER_SHOW - given)]
        given += len(kept)
        shown = [n for n in numbers if any(a <= n <= b for a, b in kept)]
        left_out += len(numbers) - len(shown)
        if kept:
            seasons.append({"season": season, "episodes": kept,
                            "some_versions": [n for n in shown if numbered[(season, n)]]})
    return {"seasons": seasons, "ranges_more": left_out,
            "unnumbered": unnumbered[:MAX_UNNUMBERED_PER_SHOW],
            "unnumbered_more": max(0, len(unnumbered) - MAX_UNNUMBERED_PER_SHOW)}


FILE_FIELDS = ("resolution", "main_audio_language", "audio_languages", "subtitle_languages",
               "forced_subtitle_languages", "unknown_audio_tracks", "unknown_subtitle_tracks")


def check_library(client, section, codes, list_limit, names):
    is_show = section.get("type") == "show"
    key = section.get("key")
    language, problem = None, None
    if codes:
        language = {"codes": codes, "source": "option"}
    elif library_language(section):
        language = {"codes": [library_language(section)], "source": "library"}
    else:
        problem = ("This library has no metadata language to go by, so files couldn't be checked "
                   "against your language. Run again with --language, for example --language en.")
    wanted = set(language["codes"]) if language else None

    items = get_all(client, key, TYPE_EPISODE if is_show else TYPE_MOVIE)
    details = get_details(client, [str(item.get("ratingKey")) for item in items])
    counts = {"titles": 0, "files": 0, "unavailable": 0, "details_missing": 0,
              **{finding: 0 for finding in FINDINGS}, "forced_only": 0}
    audio_languages, subtitle_languages = collections.Counter(), collections.Counter()
    groups = {finding: collections.OrderedDict() for finding in FINDINGS}
    shows, episodes = {}, collections.Counter()
    if is_show:
        for show in get_all(client, key, TYPE_SHOW):
            shows[str(show.get("ratingKey"))] = show
        for item in items:
            episodes[str(item.get("grandparentRatingKey"))] += 1

    for item in items:
        counts["titles"] += 1
        detail = details.get(str(item.get("ratingKey")))
        if detail is None:
            counts["details_missing"] += 1
            continue
        flagged, checked = {finding: [] for finding in FINDINGS}, 0
        for media in detail.get("Media", []) or []:
            if media.get("deletedAt"):
                counts["unavailable"] += 1
                continue
            counts["files"] += 1
            checked += 1
            result = check_file(media, wanted, names)
            counts["forced_only"] += result["forced_only"]
            if result["main_audio_language"] is not None:
                audio_languages[result["main_audio_language"]] += 1
            subtitle_languages.update(result["subtitle_languages"])
            for finding in result["findings"]:
                counts[finding] += 1
                flagged[finding].append(result)

        for finding, results in flagged.items():
            if not results:
                continue
            if is_show:
                show_key = str(item.get("grandparentRatingKey"))
                show = shows.get(show_key, {})
                entry = groups[finding].setdefault(show_key, {
                    "title": clean(show.get("title") or item.get("grandparentTitle")),
                    "year": as_int(show.get("year")) or None,
                    "episodes": episodes[show_key], "episodes_flagged": 0,
                    "audio_languages": collections.Counter(), "numbered": {}, "unnumbered": [],
                })
                entry["episodes_flagged"] += 1
                entry["audio_languages"][results[0]["main_audio_language"] or "unknown"] += 1
                note_episode(entry, item, some_versions=len(results) < checked)
            else:
                groups[finding][str(item.get("ratingKey"))] = {
                    "title": clean(item.get("title")), "year": as_int(item.get("year")) or None,
                    "files": [{field: r[field] for field in FILE_FIELDS} for r in results],
                }

    listed, more = {}, {}
    for finding, entries in groups.items():
        entries = list(entries.values())
        if is_show:
            entries.sort(key=lambda e: (-e["episodes_flagged"], e["title"].lower()))
            for entry in entries:
                entry["audio_languages"] = summary(entry["audio_languages"])
                entry.update(episode_numbers(entry.pop("numbered"), entry.pop("unnumbered")))
        else:
            entries.sort(key=lambda e: e["title"].lower())
        listed[finding] = entries[:list_limit]
        more[finding] = max(0, len(entries) - list_limit)
    if wanted is None:
        for finding in LANGUAGE_FINDINGS + ("forced_only",):
            counts[finding] = None
        for finding in LANGUAGE_FINDINGS:
            listed[finding] = more[finding] = None

    report = {"name": clean(section.get("title")), "type": section.get("type"), "language": language}
    if problem:
        report["language_problem"] = problem
    report.update(counts)
    report.update(audio_languages=summary(audio_languages), subtitle_languages=summary(subtitle_languages),
                  listed=listed, more=more)
    return report


def codes_in(libraries):
    """Every language code that appears in the libraries' reports."""
    codes = set()
    for lib in libraries:
        codes.update((lib["language"] or {}).get("codes", []))
        codes.update(lib["audio_languages"])
        codes.update(lib["subtitle_languages"])
        for entries in lib["listed"].values():
            for entry in entries or []:
                codes.update(entry.get("audio_languages", []))
                for f in entry.get("files", []):
                    codes.add(f["main_audio_language"])
                    codes.update(f["audio_languages"] + f["subtitle_languages"] + f["forced_subtitle_languages"])
    return sorted(c for c in codes if c and c not in ("unknown", "other"))


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

TOTAL_FIELDS = ("titles", "files", "unavailable", "details_missing") + FINDINGS + ("forced_only",)


def build_report(config, args, now=None):
    now = time.time() if now is None else now
    codes = parse_languages(args.language or [])
    client = need_plex(config)
    root = client.get("/")
    sections = client.get("/library/sections").get("Directory", []) or []
    checked, skipped = choose_sections(sections, args.library)

    names, libraries = {}, []
    for section in checked:
        print(f"checking library: {clean(section.get('title'))}", file=sys.stderr)
        libraries.append(check_library(client, section, codes, args.limit, names))

    return {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(now)),
        "server": {"name": clean(root.get("friendlyName")), "version": clean(root.get("version"))},
        "limits": LIMITS,
        "libraries": libraries,
        "skipped_libraries": skipped,
        "language_names": {code: names.get(code) or None for code in codes_in(libraries)},
        "totals": {field: sum(lib[field] or 0 for lib in libraries) for field in TOTAL_FIELDS},
        "media_deletion_allowed": media_deletion_allowed(lambda: client.get("/:/prefs")),
    }


def check(config):
    root = need_plex(config).get("/")
    return {"ok": True, "plex": {"server": clean(root.get("friendlyName")), "version": root.get("version")}}


def main():
    parser = argparse.ArgumentParser(
        description="Read-only check of the audio and subtitle languages on your Plex server (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connection")
    parser.add_argument("--language", action="append",
                        help="your language as a 2 or 3 letter code, such as en or spa (repeatable, up to 5; "
                             "default: each library's own language)")
    parser.add_argument("--library", action="append", help="limit to a library by name (repeatable)")
    parser.add_argument("--limit", type=int, default=25,
                        help="titles listed per finding in each library (default 25)")
    args = parser.parse_args()
    args.limit = max(0, min(args.limit, 500))

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
