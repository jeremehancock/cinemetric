#!/usr/bin/env python3
"""Cinemetric watch-mix: read-only comparison of what's on the shelf with what gets watched.

For movies and TV separately, gives each genre's, decade's and resolution's share of the library
(titles and storage) next to its share of plays and watch time. Plays come from Tautulli when it is
configured, otherwise from the Plex server's own history. Uses only the Python standard library.
Prints one JSON document to stdout; errors go to stderr.

Safety rules: see openspec/specs/security/spec.md in the Cinemetric repository.
"""

import argparse
import calendar
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

VERSION = "0.31.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
LIBRARY_PAGE_SIZE = 500
PLEX_HISTORY_PAGE_SIZE = 1000
TAUTULLI_PAGE_SIZE = 1000
HISTORY_CAP = 100000
MAX_NAMES_LISTED = 30
# Tautulli's date filter uses its own time zone and leaves out the named day, so the request starts a
# couple of days early and rows are kept by their exact start time.
TAUTULLI_MARGIN_DAYS = 2
# Groups smaller than this on the shelf stay out of the biggest-differences lists.
MIN_TITLES_FOR_DIFFERENCES = 5
# Fewer matched plays than this and the shares say little.
FEW_PLAYS = 30
UNKNOWN = "unknown"
NO_GENRE = "(no genre)"
QUALITY_ORDER = ["4K", "2K", "1080p", "720p", "SD", UNKNOWN]
LEFT_OUT_OF_DIFFERENCES = {("genre", NO_GENRE), ("decade", UNKNOWN), ("quality", UNKNOWN)}

# The only Plex server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
    re.compile(r"^/library/sections/\d+/genre$"),
    re.compile(r"^/accounts$"),
    re.compile(r"^/status/sessions/history/all$"),
    re.compile(r"^/:/prefs$"),
]

# The only Tautulli API commands this script may run. All of them only read data.
TAUTULLI_COMMANDS = {
    "get_tautulli_info",
    "get_history",
    "get_users",
}

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
TYPE_MOVIE, TYPE_SHOW, TYPE_EPISODE = 1, 2, 4


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
            "X-Plex-Client-Identifier": "cinemetric-watch-mix",
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


def day(epoch):
    epoch = as_int(epoch)
    return time.strftime("%Y-%m-%d", time.localtime(epoch)) if epoch > 0 else None


def gb(size):
    return round(size / 1e9, 1)


def hours(seconds):
    return round(seconds / 3600, 1)


def share(part, whole):
    """A percentage to one decimal place, or None when there's nothing to take a share of."""
    return round(100 * part / whole, 1) if whole else None


def months_before(now, months):
    """The same date and time `months` calendar months before `now`, clamped to the month's end."""
    t = time.localtime(now)
    year, month = divmod(t.tm_year * 12 + t.tm_mon - 1 - months, 12)
    month += 1
    mday = min(t.tm_mday, calendar.monthrange(year, month)[1])
    return time.mktime((year, month, mday, t.tm_hour, t.tm_min, t.tm_sec, 0, 0, -1))


def resolution_bucket(value):
    value = str(value or "").lower()
    if value in ("4k", "2160"):
        return "4K"
    if value == "2k":
        return "2K"
    if value == "1080":
        return "1080p"
    if value == "720":
        return "720p"
    if value in ("480", "576", "sd"):
        return "SD"
    return "unknown" if not value else value


def available_media(item):
    """The media versions Plex can still find. A version with deletedAt has a file that's gone."""
    return [m for m in item.get("Media", []) or [] if isinstance(m, dict) and not m.get("deletedAt")]


def size_on_disk(item):
    """Every part of every version Plex can still find. Optimized versions use space too."""
    return sum(as_int(part.get("size")) for media in available_media(item)
               for part in media.get("Part", []) or [])


def best_quality(item):
    """The resolution of the best version Plex can still find, or "unknown"."""
    buckets = [resolution_bucket(m.get("videoResolution")) for m in available_media(item)]
    known = [b for b in buckets if b in QUALITY_ORDER and b != "unknown"]
    if known:
        return min(known, key=QUALITY_ORDER.index)
    return next((b for b in buckets if b != "unknown"), "unknown")


def release_year(item):
    year = as_int(item.get("year"))
    return year if year > 0 else as_int(str(item.get("originallyAvailableAt") or "")[:4])


def normalize(text):
    """Title text for matching: case, spaces and punctuation ignored."""
    return re.sub(r"[\W_]+", "", str(text or "").casefold())


def key_from(value):
    """A rating key from a field like "123" or "/library/metadata/123"."""
    match = re.search(r"(\d+)$", str(value or ""))
    return match.group(1) if match else None


def decade(item):
    """1987 -> "1980s". The year, else the year of the release date, else "unknown"."""
    year = release_year(item)
    return f"{year // 10 * 10}s" if year > 0 else UNKNOWN


# ---------------------------------------------------------------- the shelf

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


class Shelf:
    """What's on the included libraries of one kind (movies or tv).

    titles: rating key -> {"genres": set of genre ids, "decade", "bytes"} for each movie or show.
    units: rating key -> {"quality", "bytes", "seconds", "title"} for each movie or episode, the
    things that have a file. For movies the two share keys.

    A title's rating key changes when its file is replaced or it's added again, so plays from before
    that are matched by other means: Plex's guid, the title and year, or a show's title and an
    episode's season and number. Those lookups are kept here too.
    """

    def __init__(self):
        self.titles = {}
        self.units = {}
        self.genre_names = {}  # lower-case name -> name as first seen
        self.by_guid = {}  # movie guid -> rating key
        self.by_name = {}  # (normalized title, year or 0) -> set of rating keys
        self.episodes = {}  # (show key, season, episode) -> episode rating key

    def name(self, key, title, year):
        for wanted in ((normalize(title), year), (normalize(title), 0)):
            self.by_name.setdefault(wanted, set()).add(key)

    def find(self, title, year):
        """The one title with this name (and year, when known), or None when none or several match."""
        for wanted in ((normalize(title), as_int(year)), (normalize(title), 0)):
            keys = self.by_name.get(wanted, set()) if wanted[0] else set()
            if keys:
                return next(iter(keys)) if len(keys) == 1 else None
        return None

    def merge(self, other):
        for lower, shown in other.genre_names.items():
            self.genre_names.setdefault(lower, shown)
        self.titles.update(other.titles)
        self.units.update(other.units)
        self.by_guid.update(other.by_guid)
        self.episodes.update(other.episodes)
        for wanted, keys in other.by_name.items():
            self.by_name.setdefault(wanted, set()).update(keys)

    def genre_id(self, name):
        name = clean(name)
        if not name:
            return None
        return self.genre_names.setdefault(name.lower(), name).lower()


def read_genres(client, section_id, type_number, shelf, keys):
    """Add every title's genres from Plex's genre filter. Listings show at most two per title."""
    genres = client.get(f"/library/sections/{section_id}/genre", {"type": type_number}).get("Directory", []) or []
    for genre in genres:
        gid = shelf.genre_id(genre.get("title"))
        if gid is None or genre.get("key") in (None, ""):
            continue
        for item in get_all(client, section_id, type_number, {"genre": genre.get("key")}):
            key = str(item.get("ratingKey"))
            if key in keys:
                shelf.titles[key]["genres"].add(gid)


def read_movies(client, section_id, shelf):
    keys = set()
    for item in get_all(client, section_id, TYPE_MOVIE):
        key = str(item.get("ratingKey"))
        size = size_on_disk(item)
        shelf.titles[key] = {"genres": set(), "decade": decade(item), "bytes": size}
        shelf.units[key] = {"quality": best_quality(item), "bytes": size,
                            "seconds": as_int(item.get("duration")) / 1000, "title": key}
        if item.get("guid"):
            shelf.by_guid[str(item.get("guid"))] = key
        shelf.name(key, item.get("title"), release_year(item))
        keys.add(key)
    read_genres(client, section_id, TYPE_MOVIE, shelf, keys)


def read_shows(client, section_id, shelf):
    keys = set()
    for item in get_all(client, section_id, TYPE_SHOW):
        key = str(item.get("ratingKey"))
        shelf.titles[key] = {"genres": set(), "decade": decade(item), "bytes": 0}
        shelf.name(key, item.get("title"), release_year(item))
        keys.add(key)
    for episode in get_all(client, section_id, TYPE_EPISODE):
        show = str(episode.get("grandparentRatingKey"))
        if show not in keys:
            continue
        size = size_on_disk(episode)
        shelf.titles[show]["bytes"] += size
        key = str(episode.get("ratingKey"))
        shelf.units[key] = {
            "quality": best_quality(episode), "bytes": size,
            "seconds": as_int(episode.get("duration")) / 1000, "title": show}
        if episode.get("parentIndex") is not None and episode.get("index") is not None:
            shelf.episodes.setdefault((show, as_int(episode.get("parentIndex")), as_int(episode.get("index"))), key)
    read_genres(client, section_id, TYPE_SHOW, shelf, keys)


def read_shelf(client, sections):
    """Returns ({"movies": Shelf or None, "tv": Shelf or None}, unavailable).

    A library that can't be read is left out and named in unavailable; the others still count.
    """
    shelves, unavailable = {}, []
    for section in sections:
        kind = "movies" if section.get("type") == "movie" else "tv"
        name = clean(section.get("title"))
        print(f"reading library: {name}", file=sys.stderr)
        part = Shelf()
        try:
            try:
                (read_movies if kind == "movies" else read_shows)(client, section.get("key"), part)
            except (AttributeError, KeyError, TypeError, IndexError, ValueError):
                raise ReportError("Plex sent this library in a shape Cinemetric didn't expect.") from None
        except ReportError as exc:
            unavailable.append({"part": f"library {name}", "reason": str(exc)})
            continue
        shelves.setdefault(kind, Shelf()).merge(part)
    return {"movies": shelves.get("movies"), "tv": shelves.get("tv")}, unavailable


# ---------------------------------------------------------------- plays

class PersonError(ReportError):
    """--user matched nobody or several people. Never a reason to fall back to another source."""


def pick_person(wanted, people, where):
    """Find one person for --user. people: [{"name": shown name, "names": all names, "id": ...}].

    An exact name (ignoring case) wins; otherwise exactly one person must contain the text.
    """
    target = clean(wanted).lower()
    exact = [p for p in people if target in (n.lower() for n in p["names"])]
    if len(exact) == 1:
        return exact[0]
    matches = exact or [p for p in people if any(target in n.lower() for n in p["names"])]
    if len(matches) == 1:
        return matches[0]
    if matches:
        names = ", ".join(sorted((p["name"] for p in matches), key=str.lower)[:MAX_NAMES_LISTED])
        raise PersonError(f'USER_AMBIGUOUS: more than one person in {where} matches "{target}": {names}')
    names = ", ".join(sorted((p["name"] for p in people), key=str.lower)[:MAX_NAMES_LISTED]) or "none"
    raise PersonError(f'USER_NOT_FOUND: no one in {where} is called "{target}". Known names: {names}')


def trend(daily):
    """Compare plays in the earlier and later halves of the period."""
    half = len(daily) // 2
    return {
        "earlier_half_plays": sum(d["plays"] for d in daily[:half]),
        "recent_half_plays": sum(d["plays"] for d in daily[half:]),
    }


# ---------------------------------------------------------------- tautulli

def stat_rows(stats, stat_id):
    # Asking for one stat_id returns that group on its own rather than inside a list.
    if isinstance(stats, dict):
        stats = [stats]
    for group in stats or []:
        if not isinstance(group, dict):
            continue
        if group.get("stat_id") == stat_id:
            return group.get("rows", []) or []
    return []



def tautulli_person(client, wanted):
    people = []
    for u in client.call("get_users") or []:
        names = [n for n in (clean(u.get("friendly_name")), clean(u.get("username"))) if n]
        if names and u.get("user_id") is not None:
            people.append({"name": names[0], "names": names, "id": u.get("user_id")})
    return pick_person(wanted, people, "Tautulli")


def play(kind, started, seconds, key, show=None, guid=None, title=None, year=None, season=None,
         episode=None):
    """One play, keeping only what matching needs: no person or device. The titles are used for
    matching only and never printed."""
    return {"kind": kind, "started": started, "seconds": seconds, "key": key_from(key),
            "show": key_from(show), "guid": str(guid or ""), "title": title, "year": as_int(year),
            "season": None if season in (None, "") else as_int(season),
            "episode": None if episode in (None, "") else as_int(episode)}


def tautulli_plays(client, args, start, end):
    """Return (plays, capped, person). Every grouped play counts, with paused time left out."""
    person = tautulli_person(client, args.user) if args.user else None
    only = {"user_id": person["id"]} if person else {}
    after = time.strftime("%Y-%m-%d", time.localtime(start - TAUTULLI_MARGIN_DAYS * 86400))
    plays, offset = [], 0
    while len(plays) < HISTORY_CAP:
        # grouping=1 merges a play that was paused and resumed later into one row.
        page = client.call("get_history", after=after, grouping=1, order_column="date", order_dir="desc",
                           start=offset, length=TAUTULLI_PAGE_SIZE, **only) or {}
        batch = page.get("data", []) or []
        for row in batch:
            kind, started = row.get("media_type"), as_int(row.get("started") or row.get("date"))
            if kind not in ("movie", "episode") or as_int(row.get("live")) or not start <= started <= end:
                continue
            # play_duration already leaves out paused time; older Tautulli only has duration.
            seconds = row.get("play_duration")
            if seconds is None:
                seconds = row.get("duration")
            if kind == "movie":
                plays.append(play(kind, started, max(0, as_int(seconds)), row.get("rating_key"),
                                  guid=row.get("guid"), title=row.get("title"), year=row.get("year")))
            else:
                plays.append(play(kind, started, max(0, as_int(seconds)), row.get("rating_key"),
                                  show=row.get("grandparent_rating_key"), title=row.get("grandparent_title"),
                                  season=row.get("parent_media_index"), episode=row.get("media_index")))
            if len(plays) >= HISTORY_CAP:
                break
        offset += len(batch)
        if len(batch) < TAUTULLI_PAGE_SIZE:
            break
    return plays, len(plays) >= HISTORY_CAP, person


def plex_plays(client, args, start, end):
    """Return (plays, capped, person). Plex records finished plays only, with no watch time."""
    person = None
    if args.user:
        accounts = client.get("/accounts").get("Account", []) or []
        people = [{"name": clean(a.get("name")), "names": [clean(a.get("name"))], "id": str(a.get("id"))}
                  for a in accounts if clean(a.get("name"))]
        person = pick_person(args.user, people, "Plex")

    plays, offset = [], 0
    while len(plays) < HISTORY_CAP:
        page = client.get("/status/sessions/history/all", {"sort": "viewedAt:desc"},
                          start=offset, size=PLEX_HISTORY_PAGE_SIZE)
        batch = page.get("Metadata", []) or []
        for v in batch:
            kind, started = v.get("type"), as_int(v.get("viewedAt"))
            if kind not in ("movie", "episode") or not start <= started <= end:
                continue
            if person and str(v.get("accountID")) != str(person["id"]):
                continue
            if kind == "movie":
                plays.append(play(kind, started, None, v.get("ratingKey"), title=v.get("title"),
                                  year=str(v.get("originallyAvailableAt") or "")[:4]))
            else:
                # Plex history has no grandparentRatingKey, only "/library/metadata/<key>".
                plays.append(play(kind, started, None, v.get("ratingKey"), show=v.get("grandparentKey"),
                                  title=v.get("grandparentTitle"), season=v.get("parentIndex"),
                                  episode=v.get("index")))
            if len(plays) >= HISTORY_CAP:
                break
        offset += len(batch)
        if not batch or as_int(batch[-1].get("viewedAt")) < start:
            break
    return plays, len(plays) >= HISTORY_CAP, person


def read_history(config, args, start, end):
    """Return (plays, capped, person, source, fallback_reason), choosing a source like unwatched."""
    fallback_reason = None
    if args.source in ("auto", "tautulli"):
        if config["tautulli"]:
            print("reading watch history from Tautulli", file=sys.stderr)
            try:
                try:
                    plays, capped, person = tautulli_plays(TautulliClient(*config["tautulli"]), args, start, end)
                    return plays, capped, person, "tautulli", None
                except (AttributeError, KeyError, TypeError, IndexError, ValueError):
                    raise ReportError("Tautulli sent data in a shape Cinemetric didn't expect.") from None
            except ReportError as exc:
                if args.source == "tautulli" or isinstance(exc, PersonError):
                    raise
                fallback_reason = f"Tautulli is configured but failed: {exc}"
        elif config["tautulli_problem"]:
            fallback_reason = f"Tautulli settings couldn't be read: {config['tautulli_problem']}"
            if args.source == "tautulli":
                raise ReportError(fallback_reason)
        elif args.source == "tautulli":
            raise ReportError("TAUTULLI_NOT_CONFIGURED: no Tautulli address and API key are set up.")
        else:
            fallback_reason = "Tautulli is not set up"

    print("reading watch history from Plex", file=sys.stderr)
    client = PlexClient(*config["plex"])
    try:
        try:
            plays, capped, person = plex_plays(client, args, start, end)
        except (AttributeError, KeyError, TypeError, IndexError, ValueError):
            raise ReportError("Plex sent watch history in a shape Cinemetric didn't expect.") from None
    except ReportError as exc:
        if isinstance(exc, PersonError) or ("401" not in str(exc) and "403" not in str(exc)):
            raise
        client.get("/")  # still fails if the token itself is bad
        raise ReportError(
            "OWNER_ONLY: Plex only shares everyone's plays with the server owner's account. "
            "Connect with the owner's account, or set up Tautulli."
        ) from None
    return plays, capped, person, "plex", fallback_reason


# ---------------------------------------------------------------- shares

class Tally:
    def __init__(self):
        self.titles = 0
        self.bytes = 0
        self.plays = 0
        self.seconds = 0.0


def match(shelf, p):
    """(title, unit) on the shelf for one play. title is None when the play matches nothing.

    A movie matches by its rating key, else its guid, else its title and year. An episode matches
    its show (by rating key, else by title) for genre and decade, and its own episode (by rating
    key, else by season and number) for quality; an episode not found has unknown quality.
    """
    if p["kind"] == "movie":
        key = p["key"] if p["key"] in shelf.titles else shelf.by_guid.get(p["guid"])
        key = key or shelf.find(p["title"], p["year"])
        return (shelf.titles[key], shelf.units.get(key)) if key else (None, None)
    unit = shelf.units.get(p["key"])
    show = p["show"] if p["show"] in shelf.titles else None
    show = show or (unit["title"] if unit else None) or shelf.find(p["title"], 0)
    if show is None:
        return None, None
    if not unit or unit["title"] != show:
        unit = shelf.units.get(shelf.episodes.get((show, p["season"], p["episode"])))
    return shelf.titles[show], unit


def rows(groups, total_titles, total_bytes, total_plays, total_seconds, order):
    out = []
    for name, t in groups.items():
        titles_percent = share(t.titles, total_titles)
        hours_percent = share(t.seconds, total_seconds)
        out.append({
            "name": name,
            "titles": t.titles,
            "titles_percent": titles_percent,
            "storage_bytes": t.bytes,
            "storage_gb": gb(t.bytes),
            "storage_percent": share(t.bytes, total_bytes),
            "plays": t.plays,
            "plays_percent": share(t.plays, total_plays),
            "hours": hours(t.seconds),
            "hours_percent": hours_percent,
            "gap_points": (None if titles_percent is None or hours_percent is None
                           else round(hours_percent - titles_percent, 1)),
        })
    out.sort(key=order)
    return out


def by_titles(row):
    return (-row["titles"], row["name"].lower(), row["name"])


def by_decade(row):
    return (row["name"] == UNKNOWN, row["name"])


def by_quality(row):
    name = row["name"]
    return (QUALITY_ORDER.index(name) if name in QUALITY_ORDER else QUALITY_ORDER.index(UNKNOWN) - 0.5, name)


def differences(groupings, top):
    """The groups watched most above and below their share of the shelf."""
    candidates = []
    for grouping, entries in groupings:
        for row in entries:
            if row["gap_points"] is None or row["titles"] < MIN_TITLES_FOR_DIFFERENCES:
                continue
            if (grouping, row["name"]) in LEFT_OUT_OF_DIFFERENCES:
                continue
            candidates.append(dict(row, grouping=grouping))
    more = sorted((r for r in candidates if r["gap_points"] > 0),
                  key=lambda r: (-r["gap_points"], -r["titles"], r["name"].lower()))
    less = sorted((r for r in candidates if r["gap_points"] < 0),
                  key=lambda r: (r["gap_points"], -r["titles"], r["name"].lower()))
    return more[:top], less[:top]


def summarize(kind, shelf, plays, top, source):
    """The kind's shares, and its unmatched plays as (plays, seconds)."""
    genres, decades, quality = {}, {}, {}
    total_bytes = sum(t["bytes"] for t in shelf.titles.values())
    for t in shelf.titles.values():
        for gid in t["genres"] or {NO_GENRE}:
            g = genres.setdefault(gid, Tally())
            g.titles += 1
            g.bytes += t["bytes"]
        d = decades.setdefault(t["decade"], Tally())
        d.titles += 1
        d.bytes += t["bytes"]
    for u in shelf.units.values():
        q = quality.setdefault(u["quality"], Tally())
        q.titles += 1
        q.bytes += u["bytes"]

    matched, seconds, unmatched, unmatched_seconds = 0, 0.0, 0, 0.0
    for p in plays:
        title, unit = match(shelf, p)
        if source == "tautulli":
            length = p["seconds"]
        else:
            # Plex records only finished plays, so a play lasts as long as the title.
            length = unit["seconds"] if unit else 0
        if title is None:
            unmatched += 1
            unmatched_seconds += length
            continue
        matched += 1
        seconds += length
        touched = [genres.setdefault(gid, Tally()) for gid in title["genres"] or {NO_GENRE}]
        touched.append(decades.setdefault(title["decade"], Tally()))
        touched.append(quality.setdefault(unit["quality"] if unit else UNKNOWN, Tally()))
        for t in touched:
            t.plays += 1
            t.seconds += length

    named = {(shelf.genre_names.get(gid, gid) if gid != NO_GENRE else NO_GENRE): t for gid, t in genres.items()}
    titles, units = len(shelf.titles), len(shelf.units)
    genre_rows = rows(named, titles, total_bytes, matched, seconds, by_titles)
    decade_rows = rows(decades, titles, total_bytes, matched, seconds, by_decade)
    # Quality belongs to files, so for TV its titles are episodes.
    quality_rows = rows(quality, units, total_bytes, matched, seconds, by_quality)
    more, less = differences((("genre", genre_rows), ("decade", decade_rows), ("quality", quality_rows)), top)
    report = {
        "titles": titles,
        "storage_bytes": total_bytes,
        "storage_gb": gb(total_bytes),
        "plays": matched,
        "hours": hours(seconds),
        "few_plays": matched < FEW_PLAYS,
        "genres": genre_rows,
        "decades": decade_rows,
        "quality": quality_rows,
        "watched_more": more,
        "watched_less": less,
    }
    if kind == "tv":
        report["episodes"] = units
    return report, (unmatched, unmatched_seconds)


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
            raise ReportError("Only movie and TV libraries are compared with what gets watched.")
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
    shelves, unavailable = read_shelf(client, checked)

    start = months_before(now, args.months)
    plays, capped, person, source, fallback_reason = read_history(config, args, start, now)

    kinds, unmatched = {}, {}
    for kind, play_kind in (("movies", "movie"), ("tv", "episode")):
        shelf = shelves[kind]
        own = [p for p in plays if p["kind"] == play_kind]
        if shelf is None:
            kinds[kind] = None
            count, seconds = len(own), sum(p["seconds"] or 0 for p in own)
        else:
            kinds[kind], (count, seconds) = summarize(kind, shelf, own, args.top, source)
        unmatched[kind] = {"plays": count, "hours": hours(seconds)}

    return {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(now)),
        "server": {"name": clean(root.get("friendlyName")), "version": root.get("version")},
        "media_deletion_allowed": media_deletion_allowed(lambda: client.get("/:/prefs")),
        "source": source,
        "fallback_reason": fallback_reason,
        "scope": "user" if person else "server",
        "user": person["name"] if person else None,
        "months": args.months,
        "period_start": day(start),
        "history_capped": capped,
        "watch_time_method": "played" if source == "tautulli" else "finished_plays_times_length",
        "genre_note": "A title can have several genres, so genre shares can add up to more than 100%.",
        "quality_note": "Plays are grouped by the quality of the file on the server now, which may "
                        "differ from the one that was played.",
        "libraries": [{"name": clean(s.get("title")), "type": s.get("type")} for s in checked],
        "skipped_libraries": skipped,
        "unavailable": unavailable,
        "unmatched_plays": unmatched,
        "movies": kinds["movies"],
        "tv": kinds["tv"],
    }


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
        description="Read-only comparison of what's on a Plex server with what gets watched (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connections")
    parser.add_argument("--months", type=int, default=12, help="how many months of plays to count (default 12)")
    parser.add_argument("--user", help="only one person's plays (name or part of a name)")
    parser.add_argument("--library", action="append", help="limit to a library by name (repeatable)")
    parser.add_argument("--top", type=int, default=5, help="entries in each biggest-differences list")
    parser.add_argument("--source", choices=["auto", "tautulli", "plex"], default="auto",
                        help="where to read plays from (default: Tautulli if set up, else Plex)")
    args = parser.parse_args()
    args.months = max(1, min(args.months, 120))
    args.top = max(1, min(args.top, 20))

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
