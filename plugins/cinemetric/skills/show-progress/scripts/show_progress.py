#!/usr/bin/env python3
"""Cinemetric show-progress: read-only report of where each person is in each TV show on a Plex server.

Lines up each person's finished episodes (from Tautulli's history when it is set up, otherwise the
Plex server's own) with the episodes on the server, and says whether they're caught up, waiting on
new episodes, in the middle, or stopped. Uses only the Python standard library. Prints one JSON
document to stdout; errors go to stderr.

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

VERSION = "0.29.1"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
LIBRARY_PAGE_SIZE = 500
PLEX_HISTORY_PAGE_SIZE = 1000
TAUTULLI_PAGE_SIZE = 1000
HISTORY_CAP = 100000
MAX_MATCHES = 20
MAX_NAMES_LISTED = 30

# The only Plex server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
    re.compile(r"^/status/sessions/history/all$"),
    re.compile(r"^/accounts$"),
    re.compile(r"^/:/prefs$"),
]

# The only Tautulli API commands this script may run. All of them only read data.
TAUTULLI_COMMANDS = {
    "get_tautulli_info",
    "get_history",
    "get_users",
}

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
TYPE_SHOW, TYPE_EPISODE = 2, 4

STATUSES = ("caught_up", "new_episodes", "in_progress", "stopped")

PLEX_HISTORY_NOTE = (
    "Plex's own history only records episodes that were finished, so a half-watched episode looks "
    "the same as one that wasn't played, and the last play is the last finished episode."
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
            "X-Plex-Client-Identifier": "cinemetric-show-progress",
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


def as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def day(epoch):
    epoch = as_int(epoch)
    return time.strftime("%Y-%m-%d", time.localtime(epoch)) if epoch > 0 else None


def normalize(text):
    """Title text for matching: case, spaces and punctuation ignored."""
    return re.sub(r"[\W_]+", "", str(text or "").casefold())


def key_from(value):
    """A rating key from a field like "123" or "/library/metadata/123"."""
    match = re.search(r"(\d+)$", str(value or ""))
    return match.group(1) if match else None


def months_before(now, months):
    """The same date and time `months` calendar months before `now`, clamped to the month's end."""
    t = time.localtime(now)
    year, month = divmod(t.tm_year * 12 + t.tm_mon - 1 - months, 12)
    month += 1
    mday = min(t.tm_mday, calendar.monthrange(year, month)[1])
    return time.mktime((year, month, mday, t.tm_hour, t.tm_min, t.tm_sec, 0, 0, -1))


# ---------------------------------------------------------------- one person
#
# Copied from watch_activity.py: --user must find the same person in both scripts.

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


def tautulli_person(client, wanted):
    people = []
    for u in client.call("get_users") or []:
        names = [n for n in (clean(u.get("friendly_name")), clean(u.get("username"))) if n]
        if names and u.get("user_id") is not None:
            people.append({"name": names[0], "names": names, "id": u.get("user_id")})
    return pick_person(wanted, people, "Tautulli")


# ---------------------------------------------------------------- episodes on the server

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


def choose_sections(sections, wanted):
    if wanted:
        names = {name.lower() for name in wanted}
        sections = [s for s in sections if str(s.get("title", "")).lower() in names]
        if not any(s.get("type") == "show" for s in sections):
            raise ReportError("No TV library matched --library. Run without it to see all names.")
    checked = [s for s in sections if s.get("type") == "show"]
    skipped = [{"name": clean(s.get("title")), "type": s.get("type")}
               for s in sections if s.get("type") != "show"]
    return checked, skipped


class Show:
    def __init__(self, item, section):
        self.key = str(item.get("ratingKey"))
        self.title = clean(item.get("title"))
        self.year = as_int(item.get("year"), None)
        self.library = clean(section.get("title"))
        self.section = str(section.get("key"))
        self.episodes = {}  # (season, episode) -> {"title": ..., "added": ...}
        self.unmatched_plays = 0
        self.last_played = 0

    def add_episode(self, item):
        season, episode = as_int(item.get("parentIndex"), None), as_int(item.get("index"), None)
        # Specials (season 0) and episodes without numbers have no place in the order.
        if season is None or episode is None or season <= 0:
            return
        # An episode whose every file Plex can't find isn't there to watch.
        if not any(not media.get("deletedAt") for media in item.get("Media", []) or []):
            return
        added = as_int(item.get("addedAt"))
        known = self.episodes.get((season, episode))
        if known is None:
            self.episodes[(season, episode)] = {"title": clean(item.get("title")), "added": added}
        elif added and (not known["added"] or added < known["added"]):
            # Two copies of one episode: it has been on the server since the first arrived.
            known["added"] = added


def read_shows(client, sections):
    shows = {}
    for section in sections:
        for item in get_all(client, section.get("key"), TYPE_SHOW):
            show = Show(item, section)
            shows[show.key] = show
    return shows


def read_episodes(client, sections, shows):
    for section in sections:
        for item in get_all(client, section.get("key"), TYPE_EPISODE):
            show = shows.get(key_from(item.get("grandparentRatingKey")))
            if show is not None:
                show.add_episode(item)


def find_show(shows, query):
    """The one show whose title contains the query. An exact title beats a partial one."""
    wanted = normalize(query)
    found = [s for s in shows.values() if wanted and wanted in normalize(s.title)]
    found = [s for s in found if normalize(s.title) == wanted] or found
    if not found:
        raise ReportError(f'SHOW_NOT_FOUND: no TV show on the server has "{clean(query)}" in its title.')
    if len(found) > 1:
        listed = sorted(found, key=lambda s: (s.title.lower(), s.year or 0, s.library.lower()))
        names = "; ".join(f"{s.title} ({s.year or 'no year'}, {s.library})" for s in listed[:MAX_MATCHES])
        raise ReportError(f'SHOW_AMBIGUOUS: {len(found)} shows match "{clean(query)}": {names}')
    return found[0]


# ---------------------------------------------------------------- plays

class Progress:
    """One person's plays of one show."""

    def __init__(self, name):
        self.name = name
        self.last_played = 0
        self.finished = {}  # (season, episode) -> when it was first finished

    def add(self, number, date, finished):
        self.last_played = max(self.last_played, date)
        if finished and number is not None and number[0] > 0:
            first = self.finished.get(number)
            self.finished[number] = date if first is None else min(first, date)


class History:
    """Plays matched to shows on the server, kept per person and show."""

    def __init__(self, shows):
        self.shows = shows
        self.progress = {}  # (person id, show key) -> Progress
        self.rows = 0
        self.oldest = None

    def saw(self, epoch):
        self.rows += 1
        if epoch > 0 and (self.oldest is None or epoch < self.oldest):
            self.oldest = epoch

    def play(self, person, name, show_key, season, episode, date, finished):
        show = self.shows.get(show_key)
        if show is None:
            return
        show.last_played = max(show.last_played, date)
        # Matched by show, season and episode number: an episode's rating key changes when its
        # file is replaced, but its numbers don't.
        number = (season, episode) if season is not None and episode is not None else None
        if number is None or (season > 0 and number not in show.episodes):
            show.unmatched_plays += 1
        self.progress.setdefault((person, show_key), Progress(name)).add(number, date, finished)

    @property
    def capped(self):
        return self.rows >= HISTORY_CAP


def tautulli_history(client, history, args, show):
    person = tautulli_person(client, args.user) if args.user else None
    filters = {}
    if person:
        filters["user_id"] = person["id"]
    if show:
        filters["grandparent_rating_key"] = show.key
    start = 0
    while history.rows < HISTORY_CAP:
        size = min(TAUTULLI_PAGE_SIZE, HISTORY_CAP - history.rows)
        # grouping=1 merges a play that was paused and resumed later into one row.
        page = client.call("get_history", grouping=1, media_type="episode", order_column="date",
                           order_dir="desc", start=start, length=size, **filters) or {}
        batch = page.get("data", []) or []
        for row in batch:
            if as_int(row.get("live")):
                continue
            epoch = as_int(row.get("stopped") or row.get("date") or row.get("started"))
            history.saw(epoch)
            # Only these fields are read: nothing about IP addresses, devices or players.
            history.play("t:" + str(row.get("user_id")),
                         clean(row.get("friendly_name") or row.get("user")) or "Unknown",
                         key_from(row.get("grandparent_rating_key")),
                         as_int(row.get("parent_media_index"), None), as_int(row.get("media_index"), None),
                         epoch,
                         # Tautulli gives 1 for watched and 0, 0.25, 0.5 or 0.75 for partly watched.
                         as_float(row.get("watched_status")) >= 1)
        start += len(batch)
        if len(batch) < size:
            break
    if filters and not history.capped:
        # The rows read were only this person's or this show's, so the oldest of them isn't how far
        # back the history goes. Ask for the oldest episode row of all.
        page = client.call("get_history", grouping=1, media_type="episode", order_column="date",
                           order_dir="asc", start=0, length=25) or {}
        for row in page.get("data", []) or []:
            epoch = as_int(row.get("stopped") or row.get("date") or row.get("started"))
            if not as_int(row.get("live")) and epoch > 0:
                history.oldest = min(epoch, history.oldest or epoch)
                break
    return person


def plex_history(client, history, args, show):
    # Plex's history only holds plays that were finished or nearly finished, so every entry counts.
    accounts = {str(a.get("id")): clean(a.get("name")) or f"user {a.get('id')}"
                for a in client.get("/accounts").get("Account", []) or []}
    person = None
    if args.user:
        people = [{"name": name, "names": [name], "id": key} for key, name in accounts.items()]
        person = pick_person(args.user, people, "Plex")
    params = {"sort": "viewedAt:desc"}
    if show:
        # Asks Plex for this show's entries only; each one is still checked below.
        params["metadataItemID"] = show.key
    start = 0
    while history.rows < HISTORY_CAP:
        size = min(PLEX_HISTORY_PAGE_SIZE, HISTORY_CAP - history.rows)
        page = client.get("/status/sessions/history/all", params, start=start, size=size)
        batch = page.get("Metadata", []) or []
        for entry in batch:
            epoch = as_int(entry.get("viewedAt"))
            history.saw(epoch)
            # Plex can't filter its history to episodes, so movies and music are skipped here.
            if entry.get("type") != "episode":
                continue
            account = str(entry.get("accountID"))
            if person is not None and account != person["id"]:
                continue
            history.play("p:" + account, accounts.get(account, f"user {account}"),
                         key_from(entry.get("grandparentRatingKey") or entry.get("grandparentKey")),
                         as_int(entry.get("parentIndex"), None), as_int(entry.get("index"), None),
                         epoch, True)
        start += len(batch)
        if len(batch) < size:
            break
    if show and not history.capped:
        # Only this show's entries were read; ask for the oldest entry of all.
        page = client.get("/status/sessions/history/all", {"sort": "viewedAt:asc"}, start=0, size=1)
        for entry in page.get("Metadata", []) or []:
            epoch = as_int(entry.get("viewedAt"))
            if epoch > 0:
                history.oldest = min(epoch, history.oldest or epoch)
    return person


def read_history(config, client, args, shows, show):
    """Returns (source, history, fallback_reason, person)."""
    fallback_reason = None
    if args.source in ("auto", "tautulli"):
        if config["tautulli"]:
            print("reading watch history from Tautulli", file=sys.stderr)
            history = History(shows)
            try:
                try:
                    person = tautulli_history(TautulliClient(*config["tautulli"]), history, args, show)
                    return "tautulli", history, None, person
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
    # A fresh start: nothing a failed Tautulli read collected is kept.
    for one in shows.values():
        one.unmatched_plays = one.last_played = 0
    history = History(shows)
    try:
        try:
            person = plex_history(client, history, args, show)
        except (AttributeError, KeyError, TypeError, IndexError, ValueError):
            raise ReportError("Plex sent history in a shape Cinemetric didn't expect.") from None
    except ReportError as exc:
        if isinstance(exc, PersonError) or ("401" not in str(exc) and "403" not in str(exc)):
            raise
        client.get("/")  # still fails if the token itself is bad
        raise ReportError(
            "OWNER_ONLY: Plex only shares the server's watch history with the server owner's "
            "account. Connect with the owner's account, or set up Tautulli."
        ) from None
    return "plex", history, fallback_reason, person


# ---------------------------------------------------------------- places in shows

def place(show, progress, stopped_cutoff):
    """Where one person is in one show, or None if they never finished a regular episode."""
    if not progress.finished:
        return None
    # The furthest episode finished, by order: rewatching season 1 doesn't move anyone back, and
    # episodes before where someone started aren't counted as left.
    furthest = max(progress.finished)
    left = sorted(number for number in show.episodes if number > furthest)
    new = [number for number in left if show.episodes[number]["added"] > progress.last_played]
    if not left:
        status = "caught_up"
    elif len(new) == len(left):
        status = "new_episodes"
    elif progress.last_played < stopped_cutoff:
        status = "stopped"
    else:
        status = "in_progress"
    upcoming = left[0] if left else None
    return {
        "name": progress.name,
        "status": status,
        "furthest": {"season": furthest[0], "episode": furthest[1]},
        "episodes_finished": sum(1 for number in progress.finished if number in show.episodes),
        "episodes_left": len(left),
        "next_episode": {"season": upcoming[0], "episode": upcoming[1],
                         "title": show.episodes[upcoming]["title"]} if upcoming else None,
        "new_since_last_play": len(new),
        "last_played_at": day(progress.last_played),
        "_last": progress.last_played,
    }


def shows_part(shows, by_show, chosen, stopped_cutoff):
    entries, counts = [], dict.fromkeys(STATUSES, 0)
    for key, show in shows.items():
        people = [p for p in (place(show, prog, stopped_cutoff) for prog in by_show.get(key, [])) if p]
        if not people and show is not chosen:
            continue
        people.sort(key=lambda p: (-p["_last"], p["name"].lower()))
        for person in people:
            counts[person["status"]] += 1
            del person["_last"]
        entries.append({
            "title": show.title,
            "year": show.year,
            "library": show.library,
            "episodes_on_server": len(show.episodes),
            "last_added_at": day(max((ep["added"] for ep in show.episodes.values()), default=0)),
            "last_played_at": day(show.last_played),
            "unmatched_plays": show.unmatched_plays,
            "people": people,
            "_last": show.last_played,
        })
    entries.sort(key=lambda e: (-e["_last"], e["title"].lower()))
    for entry in entries:
        del entry["_last"]
    return entries, counts


def recent_part(shows, by_show, new_start):
    """Shows with episodes added since new_start, and whether the people following them have seen them."""
    recent = []
    for key, show in shows.items():
        new = [number for number, ep in show.episodes.items() if ep["added"] >= new_start]
        if not new:
            continue
        people = []
        for prog in by_show.get(key, []):
            if prog.finished:
                people.append({"name": prog.name,
                               "finished_new": sum(1 for number in new if number in prog.finished),
                               # Following the show: finished one of its episodes before the new
                               # ones started arriving. Nobody follows a show that's new to the server.
                               "was_following": min(prog.finished.values()) < new_start})
        people.sort(key=lambda p: p["name"].lower())
        added = [show.episodes[number]["added"] for number in new]
        recent.append({
            "title": show.title,
            "year": show.year,
            "library": show.library,
            "new_episodes": len(new),
            "added_since": day(min(added)),
            "people": people,
            "nobody_started": not any(p["finished_new"] for p in people),
            "_newest": max(added),
        })
    recent.sort(key=lambda r: (-r["_newest"], r["title"].lower()))
    for entry in recent:
        del entry["_newest"]
    return recent


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
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN). The episode list only "
            "comes from Plex."
        )
    return PlexClient(*config["plex"])


def build_report(config, args, now=None):
    now = time.time() if now is None else now
    client = need_plex(config)
    root = client.get("/")
    sections = client.get("/library/sections").get("Directory", []) or []
    checked, skipped = choose_sections(sections, args.library)

    print("reading the TV libraries", file=sys.stderr)
    shows = read_shows(client, checked)
    chosen = find_show(shows, args.show) if args.show else None
    if chosen:
        shows = {chosen.key: chosen}
        checked = [s for s in checked if str(s.get("key")) == chosen.section]
    read_episodes(client, checked, shows)

    source, history, fallback_reason, person = read_history(config, client, args, shows, chosen)
    by_show = {}
    for (_, show_key), progress in history.progress.items():
        by_show.setdefault(show_key, []).append(progress)
    entries, counts = shows_part(shows, by_show, chosen, months_before(now, args.stopped_months))
    recent = recent_part(shows, by_show, now - args.new_days * 86400)

    report = {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(now)),
        "server": {"name": clean(root.get("friendlyName")), "version": root.get("version")},
        "source": source,
        "fallback_reason": fallback_reason,
    }
    if source == "plex":
        report["plex_history_note"] = PLEX_HISTORY_NOTE
    report.update({
        "history_since": day(history.oldest),
        "history_capped": history.capped,
        "stopped_after_months": args.stopped_months,
        "new_days": args.new_days,
        "user": person["name"] if person else None,
        "show": chosen.title if chosen else None,
        "skipped_libraries": skipped,
        "status_counts": counts,
        "show_count": len(entries),
        "shows": entries[:args.top],
        "recently_added_count": len(recent),
        "recently_added": recent[:args.top],
        "media_deletion_allowed": media_deletion_allowed(lambda: client.get("/:/prefs")),
    })
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
        description="Read-only report of where each person is in each TV show on Plex (JSON output).")
    parser.add_argument("--show", help="only this show (part of its title is enough)")
    parser.add_argument("--user", help="only this person (part of their name is enough)")
    parser.add_argument("--library", action="append", help="only this TV library (repeatable)")
    parser.add_argument("--stopped-months", type=int, default=3,
                        help="partway through with nothing played for this many months counts as "
                             "stopped (default 3)")
    parser.add_argument("--new-days", type=int, default=30,
                        help="episodes added in this many days count as recently added (default 30)")
    parser.add_argument("--top", type=int, default=25, help="how many shows to list (default 25)")
    parser.add_argument("--source", choices=("auto", "tautulli", "plex"), default="auto",
                        help="where watch history comes from (default auto: Tautulli if set up)")
    parser.add_argument("--check", action="store_true", help="only test the connections")
    args = parser.parse_args(argv)
    if args.check:
        return args
    for name in ("stopped_months", "new_days", "top"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be a positive whole number")
    for name in ("show", "user"):
        if getattr(args, name) is not None and not getattr(args, name).strip():
            parser.error(f"--{name} needs a name")
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
