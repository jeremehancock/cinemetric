#!/usr/bin/env python3
"""Cinemetric users and shares: read-only overview of who can reach a Plex server.

Lists the people the server is shared with (friends, Plex Home members, managed users and pending
invites), which libraries each one can see, whether they can download, and when they last played
something. Who a server is shared with is only stored in the owner's plex.tv account, so this script
also sends read-only GET requests to three plex.tv addresses. Last played dates come from Tautulli
when it is set up, otherwise from the server's own watch history. Recent watch history is also
read to see which of the people each library is shared with played anything from it.

Uses only the Python standard library. Prints one JSON document to stdout; errors go to stderr.

Safety rules: see openspec/specs/security/spec.md in the Cinemetric repository.
"""

import argparse
import datetime
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
import xml.etree.ElementTree as ET

VERSION = "0.28.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
MAX_PLEX_TV_BYTES = 5 * 1024 * 1024
OLD_INVITE_DAYS = 30
DAY = 86400
HISTORY_PAGE_SIZE = 1000
HISTORY_CAP = 100000

# The only Plex server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/status/sessions/history/all$"),
    re.compile(r"^/:/prefs$"),
]

# The only plex.tv addresses this script may request, and how. All of them only read data.
PLEX_TV_RULES = [
    ("GET", re.compile(r"^https://plex\.tv/api/users$")),
    ("GET", re.compile(r"^https://plex\.tv/api/servers/[A-Za-z0-9]+/shared_servers$")),
    ("GET", re.compile(r"^https://plex\.tv/api/invites/requested$")),
]

# The only Tautulli API commands this script may run. Both only read data.
TAUTULLI_COMMANDS = {"get_users_table", "get_history"}

KIND_ORDER = {"home": 0, "managed": 1, "friend": 2}
FILTER_FIELDS = ("filterAll", "filterMovies", "filterMusic", "filterPhotos", "filterTelevision")


class ReportError(Exception):
    """An error with a message that is safe to show the user."""


class PlexTvRefused(ReportError):
    """plex.tv answered 401 or 403."""


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
    if not config["plex"]:
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
            "X-Plex-Client-Identifier": "cinemetric-users-and-shares",
        }
        if start is not None:
            headers["X-Plex-Container-Start"] = str(start)
            headers["X-Plex-Container-Size"] = str(size)
        request = urllib.request.Request(url, headers=headers, method="GET")
        data = fetch_json(self._opener, request, f"the Plex server ({path})", self._token)
        return data.get("MediaContainer", {}) if isinstance(data, dict) else {}


class PlexTvClient:
    """GET-only access to the plex.tv addresses in PLEX_TV_RULES. Answers are parsed as XML.

    plex.tv always has a real certificate, so it is always checked, whatever verify_tls says.
    """

    def __init__(self, token):
        self._token = token
        self._opener = build_opener("https://plex.tv", True)

    def get(self, url):
        if not any(m == "GET" and rule.match(url) for m, rule in PLEX_TV_RULES):
            raise ReportError(f"Blocked plex.tv request outside the allowlist: GET {url}")
        what = "plex.tv"
        headers = {
            "Accept": "application/xml",
            "X-Plex-Token": self._token,
            "X-Plex-Product": "Cinemetric",
            "X-Plex-Version": VERSION,
            "X-Plex-Client-Identifier": "cinemetric-users-and-shares",
        }
        request = urllib.request.Request(url, headers=headers, method="GET")

        def scrub(text):
            return str(text).replace(self._token, "[hidden]") if self._token else str(text)

        try:
            with self._opener.open(request, timeout=TIMEOUT_SECONDS) as resp:
                body = resp.read(MAX_PLEX_TV_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise PlexTvRefused(f"{what} refused the request (HTTP {exc.code}).") from None
            raise ReportError(f"{what} returned HTTP {exc.code}.") from None
        except urllib.error.URLError as exc:
            raise ReportError(f"Could not reach {what}: {scrub(exc.reason)}") from None
        except (TimeoutError, OSError) as exc:
            raise ReportError(f"Network error talking to {what}: {scrub(exc)}") from None
        if len(body) > MAX_PLEX_TV_BYTES:
            raise ReportError(f"{what} sent a response larger than 5 MB; it was not read.")
        if b"<!DOCTYPE" in body or b"<!ENTITY" in body:
            raise ReportError(f"{what} sent a response with a DOCTYPE or ENTITY; it was not read.")
        try:
            return ET.fromstring(body)
        except ET.ParseError:
            raise ReportError(f"{what} sent a response that was not XML.") from None


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


# ---------------------------------------------------------------- snapshots
#
# Shared helper: the same code is in library_report.py, server_health.py, users_and_shares.py and
# changes.py. Keep every copy in step. Snapshot files are untrusted data: anything odd is skipped,
# and every text value is cleaned again on the way in.

SNAPSHOT_FORMAT = 1
SNAPSHOT_MAX_BYTES = 50 * 1000 * 1000
SNAPSHOT_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json$")
SERVER_ID = re.compile(r"^[A-Za-z0-9]{1,128}$")


def data_dir():
    if os.environ.get("CINEMETRIC_DATA_DIR"):
        return os.environ["CINEMETRIC_DATA_DIR"]
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "cinemetric")


def snapshots_dir():
    return os.path.join(data_dir(), "snapshots")


def snapshot_files(server_id):
    """(date, path) of each snapshot file for a server, newest first. Other names are ignored."""
    if not SERVER_ID.match(str(server_id or "")):
        return []
    folder = os.path.join(snapshots_dir(), server_id)
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    found = []
    for name in names:
        match = SNAPSHOT_NAME.match(name)
        if not match:
            continue
        try:
            found.append((datetime.date.fromisoformat(match.group(1)), os.path.join(folder, name)))
        except ValueError:
            continue
    return sorted(found, reverse=True)


def clean_tree(value):
    if isinstance(value, dict):
        return {clean(k): clean_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_tree(v) for v in value]
    if isinstance(value, str):
        return clean(value)
    return value


def load_snapshot(path):
    """A snapshot's contents as saved (text not cleaned yet), or None if it isn't a sound format 1
    snapshot. Clean any text taken from it before showing it; read_snapshot does that for all of it."""
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > SNAPSHOT_MAX_BYTES:
            return None
        with open(path, encoding="utf-8") as fh:
            data = json.loads(fh.read(SNAPSHOT_MAX_BYTES + 1))
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or data.get("format") != SNAPSHOT_FORMAT:
        return None
    return data


def read_snapshot(path):
    """A snapshot's contents with text cleaned, or None if it isn't a sound format 1 snapshot."""
    data = load_snapshot(path)
    return clean_tree(data) if data is not None else None


def choose_snapshot(server_id, area, since_days=None, today=None):
    """The snapshot area to compare with, and {"snapshot_date", "days_ago"}; or None.

    The newest snapshot from before today that has this area. With since_days, the newest that is
    at least that old, or the oldest one when none is.
    """
    today = today or datetime.date.today()
    earlier = [(day, path) for day, path in snapshot_files(server_id) if day < today]
    if since_days:
        old_enough = [f for f in earlier if (today - f[0]).days >= since_days]
        younger = [f for f in earlier if (today - f[0]).days < since_days]
        earlier = old_enough + younger[::-1]  # newest old-enough first, then oldest younger first
    for day, path in earlier:
        data = read_snapshot(path)
        if data and isinstance(data.get(area), dict):
            return data[area], {"snapshot_date": day.isoformat(), "days_ago": (today - day).days}
    return None


def as_count(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def epoch(value):
    """A plex.tv or Tautulli timestamp as an int, or None when missing or not a number."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def day(seconds):
    return time.strftime("%Y-%m-%d", time.localtime(seconds)) if seconds else None


def flag(value):
    """plex.tv's "1"/"0" attributes as True/False, or None when missing."""
    if value in ("1", "true"):
        return True
    if value in ("0", "false"):
        return False
    return None


def has_filters(element):
    return any((element.get(name) or "").strip() for name in FILTER_FIELDS)


# ---------------------------------------------------------------- reading plex.tv
# Each element is turned into a small dict holding only the allowed details as soon as it is read.
# Email addresses, access tokens, avatars and filter text are never copied out of the XML.

def read_users(root, machine_id):
    """https://plex.tv/api/users -> {user id: details}."""
    users = {}
    for user in root.findall("User"):
        here = [s for s in user.findall("Server") if s.get("machineIdentifier") == machine_id]
        users[user.get("id")] = {
            "username": clean(user.get("username")),
            "title": clean(user.get("title")),
            "home": flag(user.get("home")) is True,
            "restricted": flag(user.get("restricted")) is True,
            "pending_here": any(flag(s.get("pending")) for s in here),
            "filters": has_filters(user),
        }
    return users


def read_shared_servers(root):
    """https://plex.tv/api/servers/<id>/shared_servers -> list of shares on this server."""
    shares = []
    for share in root.findall("SharedServer"):
        shares.append({
            "user_id": share.get("userID"),
            "username": clean(share.get("username")),
            "name": clean(share.get("name")),
            "all_libraries": flag(share.get("allLibraries")) is True,
            "section_keys": [s.get("key") for s in share.findall("Section") if flag(s.get("shared"))],
            "allow_downloads": flag(share.get("allowSync")),
            "filters": has_filters(share),
            "invited": epoch(share.get("invitedAt")),
            "accepted": epoch(share.get("acceptedAt")),
        })
    return shares


def read_invites(root, machine_id):
    """https://plex.tv/api/invites/requested -> invites that share this server.

    Plain friend requests (server="0") give no access to the server and are left out. An invite
    that names its servers must name this one.
    """
    invites = []
    for invite in root.findall("Invite"):
        if not flag(invite.get("server")):
            continue
        servers = [s.get("machineIdentifier") for s in invite.iter("Server")]
        if servers and machine_id not in servers:
            continue
        invites.append({
            "user_id": invite.get("id"),
            "username": clean(invite.get("username")),
            "home": flag(invite.get("home")) is True,
            "invited": epoch(invite.get("createdAt")),
        })
    return invites


# ---------------------------------------------------------------- building the report

def build_people(shares, users, invites, section_titles):
    people = []
    for share in shares:
        user = users.get(share["user_id"], {})
        if user.get("restricted"):
            kind = "managed"
        elif user.get("home"):
            kind = "home"
        else:
            kind = "friend"
        pending = not share["accepted"] or user.get("pending_here", False)
        keys = {k for k in share["section_keys"] if k in section_titles}
        libraries = "all" if share["all_libraries"] else sorted(section_titles[k] for k in keys)
        people.append({
            "name": share["username"] or user.get("title") or share["name"] or "unknown",
            "kind": kind,
            "status": "pending" if pending else "accepted",
            "libraries": libraries,
            "allow_downloads": share["allow_downloads"],
            "content_restrictions": share["filters"] or user.get("filters", False),
            "invited": share["invited"],
            "_user_id": share["user_id"],
            "_keys": keys,
        })

    listed_ids = {s["user_id"] for s in shares}
    listed_names = {p["name"] for p in people}
    for invite in invites:
        if invite["user_id"] in listed_ids or (invite["username"] and invite["username"] in listed_names):
            continue
        people.append({
            "name": invite["username"] or "invited by email",
            "kind": "home" if invite["home"] else "friend",
            "status": "pending",
            "libraries": None,
            "allow_downloads": None,
            "content_restrictions": None,
            "invited": invite["invited"],
            "_user_id": invite["user_id"],
            "_keys": set(),
        })
    return people


def tautulli_last_seen(client):
    """{Plex user id: last seen epoch} from Tautulli's users table."""
    data = client.call("get_users_table", length=10000)
    rows = data.get("data", []) if isinstance(data, dict) else []
    return {str(row.get("user_id")): epoch(row.get("last_seen")) for row in rows if isinstance(row, dict)}


def add_last_played(people, plex, config, unavailable):
    """Give each accepted person last_played and last_played_source; pending people get None."""
    tautulli = {}
    if config["tautulli"]:
        print("reading last played dates from Tautulli", file=sys.stderr)
        try:
            try:
                tautulli = tautulli_last_seen(TautulliClient(*config["tautulli"]))
            except (AttributeError, KeyError, TypeError, ValueError):
                raise ReportError("Tautulli sent data in a shape Cinemetric didn't expect.") from None
        except ReportError as exc:
            unavailable.append({"part": "Tautulli last played dates", "reason": str(exc)})
    elif config["tautulli_problem"]:
        unavailable.append({"part": "Tautulli last played dates", "reason": config["tautulli_problem"]})

    history_failed = None
    for person in people:
        person["last_played"] = person["last_played_source"] = None
        person["_played"] = None
        person["_played_known"] = False
        if person["status"] != "accepted":
            continue
        seen = tautulli.get(str(person["_user_id"]))
        if seen:
            person["_played"], person["last_played_source"] = seen, "tautulli"
            person["_played_known"] = True
            continue
        if not person["_user_id"]:
            continue
        try:
            page = plex.get("/status/sessions/history/all",
                            {"accountID": person["_user_id"], "sort": "viewedAt:desc"}, start=0, size=1)
            views = page.get("Metadata") or []
            viewed = epoch(views[0].get("viewedAt")) if views else None
        except ReportError as exc:
            history_failed = history_failed or str(exc)
            continue
        except (AttributeError, TypeError):
            history_failed = history_failed or "Plex sent watch history in an unexpected shape."
            continue
        person["_played_known"] = True
        if viewed:
            person["_played"], person["last_played_source"] = viewed, "plex"
    if history_failed:
        unavailable.append({"part": "Plex watch history", "reason": history_failed})
    for person in people:
        person["last_played"] = day(person["_played"])


def plex_library_plays(plex, cutoff):
    """({(account id, section key)}, complete) from Plex's history since cutoff, newest first."""
    plays, rows, start = set(), 0, 0
    while rows < HISTORY_CAP:
        size = min(HISTORY_PAGE_SIZE, HISTORY_CAP - rows)
        page = plex.get("/status/sessions/history/all", {"sort": "viewedAt:desc"}, start=start, size=size)
        batch = page.get("Metadata") or []
        rows += len(batch)
        start += len(batch)
        for view in batch:
            if (epoch(view.get("viewedAt")) or 0) >= cutoff:
                plays.add((str(view.get("accountID")), str(view.get("librarySectionID") or "")))
        if len(batch) < size or (epoch(batch[-1].get("viewedAt")) or 0) < cutoff:
            return plays, True
    return plays, False


def tautulli_library_plays(client, cutoff, section_keys):
    """({(user id, section key)}, complete) from Tautulli's history since cutoff. Unfinished plays count.

    Tautulli's history rows don't say which library a play came from, so each library is read on its
    own with Tautulli's section_id filter.
    """
    plays, rows = set(), 0
    for key in section_keys:
        start = 0
        while True:
            if rows >= HISTORY_CAP:
                return plays, False
            size = min(HISTORY_PAGE_SIZE, HISTORY_CAP - rows)
            page = client.call("get_history", after=day(cutoff), section_id=key, order_column="date",
                               order_dir="desc", start=start, length=size) or {}
            batch = page.get("data") or []
            rows += len(batch)
            start += len(batch)
            for row in batch:
                if (epoch(row.get("date")) or 0) >= cutoff:
                    plays.add((str(row.get("user_id")), key))
            if len(batch) < size or (epoch(batch[-1].get("date")) or 0) < cutoff:
                break
    return plays, True


def read_library_plays(plex, config, cutoff, section_keys, unavailable):
    """(plays, activity): who played from which library since cutoff, and where that came from."""
    if config["tautulli"]:
        print("reading library activity from Tautulli", file=sys.stderr)
        try:
            try:
                plays, complete = tautulli_library_plays(TautulliClient(*config["tautulli"]), cutoff, section_keys)
            except (AttributeError, KeyError, TypeError, ValueError):
                raise ReportError("Tautulli sent data in a shape Cinemetric didn't expect.") from None
            return plays, {"source": "tautulli", "complete": complete}
        except ReportError as exc:
            unavailable.append({"part": "Tautulli library activity", "reason": str(exc)})
    print("reading library activity from Plex", file=sys.stderr)
    try:
        try:
            plays, complete = plex_library_plays(plex, cutoff)
        except (AttributeError, KeyError, TypeError, ValueError):
            raise ReportError("Plex sent watch history in an unexpected shape.") from None
        return plays, {"source": "plex", "complete": complete}
    except ReportError as exc:
        unavailable.append({"part": "library activity", "reason": str(exc)})
    return None, {"source": None, "complete": False}


def worth_a_look(people, inactive_days, now):
    items = []

    def add(kind, chosen, **extra):
        if chosen:
            items.append({"kind": kind, "people": sorted(p["name"] for p in chosen), **extra})

    add("old_pending_invite", [
        p for p in people
        if p["status"] == "pending" and p["invited"] and now - p["invited"] > OLD_INVITE_DAYS * DAY
    ], days=OLD_INVITE_DAYS)

    def inactive(p):
        if p["status"] != "accepted" or not p["_played_known"]:
            return False
        since = p["_played"] or p["invited"]
        return bool(since) and now - since > inactive_days * DAY
    add("inactive", [p for p in people if inactive(p)], days=inactive_days)

    add("all_libraries", [p for p in people if p["libraries"] == "all"])
    add("downloads_allowed", [p for p in people if p["kind"] == "friend" and p["allow_downloads"]])
    return items


# ---------------------------------------------------------------- since the last snapshot

SNAPSHOT_FIELDS = ("name", "kind", "status", "libraries", "allow_downloads")
EMAIL_INVITE = "invited by email"


def sharing_area(people):
    """This run's part of a snapshot: only the details the report already shows about each person."""
    return {"people": [{k: p[k] for k in SNAPSHOT_FIELDS} for p in people]}


def known_libraries(value):
    """A person's libraries from a snapshot: "all", a sorted list of names, or None when unknown."""
    if value == "all":
        return value
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return sorted(value)
    return None


def by_person(area):
    """{(name, kind): person} for everyone except the email invites, plus the email invite count."""
    people, email_invites = {}, 0
    for p in area.get("people") or []:
        if not isinstance(p, dict) or not isinstance(p.get("name"), str):
            continue
        if p["name"] == EMAIL_INVITE:
            email_invites += 1
        else:
            people[(p["name"], p.get("kind"))] = p
    return people, email_invites


def sharing_changes(old_area, new_area):
    old, old_invites = by_person(old_area)
    new, new_invites = by_person(new_area)
    brief = lambda p: {"name": p["name"], "kind": p.get("kind"), "status": p.get("status")}
    out = {
        "added": [brief(p) for key, p in new.items() if key not in old],
        "removed": [brief(p) for key, p in old.items() if key not in new],
        "accepted": [], "libraries_changed": [], "downloads_changed": [],
        "email_invites_change": new_invites - old_invites,
    }
    for key, now in new.items():
        before = old.get(key)
        if before is None:
            continue
        if before.get("status") == "pending" and now["status"] == "accepted":
            out["accepted"].append(now["name"])
        was, is_ = known_libraries(before.get("libraries")), known_libraries(now["libraries"])
        if was is not None and is_ is not None and was != is_:
            if isinstance(was, list) and isinstance(is_, list):
                out["libraries_changed"].append({"name": now["name"], "gained": sorted(set(is_) - set(was)),
                                                 "lost": sorted(set(was) - set(is_))})
            else:
                out["libraries_changed"].append({"name": now["name"], "from": was, "to": is_})
        if isinstance(before.get("allow_downloads"), bool) and isinstance(now["allow_downloads"], bool) \
                and before["allow_downloads"] != now["allow_downloads"]:
            out["downloads_changed"].append({"name": now["name"], "to": now["allow_downloads"]})
    for name in ("added", "removed"):
        out[name].sort(key=lambda p: p["name"].lower())
    out["accepted"].sort(key=str.lower)
    return out


def since_snapshot(server_id, area, args):
    try:
        found = choose_snapshot(server_id, "sharing", args.since)
        if not found:
            return None
        old, when = found
        return dict(when, **sharing_changes(old, area))
    except Exception:  # a bad snapshot never stops the report
        return None


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


def build_report(config, args):
    plex = PlexClient(*config["plex"])
    root = plex.get("/")
    machine_id = str(root.get("machineIdentifier") or "")
    if not re.fullmatch(r"[A-Za-z0-9]+", machine_id):
        raise ReportError("The Plex server reported a machine id Cinemetric doesn't recognise.")
    sections = plex.get("/library/sections").get("Directory", []) or []
    section_titles = {str(s.get("key")): clean(s.get("title")) for s in sections}

    plex_tv = PlexTvClient(config["plex"][1])
    print("reading who the server is shared with from plex.tv", file=sys.stderr)
    try:
        shares = read_shared_servers(
            plex_tv.get(f"https://plex.tv/api/servers/{machine_id}/shared_servers"))
    except PlexTvRefused:
        raise ReportError(
            "OWNER_ONLY: only the server owner's Plex account can see who a server is shared with. "
            "Connect Cinemetric with the owner's account to use this report."
        ) from None
    users = read_users(plex_tv.get("https://plex.tv/api/users"), machine_id)

    unavailable = []
    try:
        invites = read_invites(plex_tv.get("https://plex.tv/api/invites/requested"), machine_id)
    except ReportError as exc:
        invites = []
        unavailable.append({"part": "pending invites", "reason": str(exc)})

    people = build_people(shares, users, invites, section_titles)
    add_last_played(people, plex, config, unavailable)
    now = time.time()
    plays, activity = read_library_plays(plex, config, now - args.inactive_days * DAY,
                                          list(section_titles), unavailable)
    activity = {"source": activity["source"], "days": args.inactive_days, "complete": activity["complete"]}
    flags = worth_a_look(people, args.inactive_days, now)
    people.sort(key=lambda p: (KIND_ORDER[p["kind"]], p["name"].lower()))

    libraries, unused = [], []
    for s in sections:
        key = str(s.get("key"))
        can_see = [p for p in people
                   if p["status"] == "accepted" and (p["libraries"] == "all" or key in p["_keys"])]
        names = sorted(p["name"] for p in can_see)
        played = None
        if plays is not None:
            played = sorted(p["name"] for p in can_see if (str(p["_user_id"]), key) in plays)
        libraries.append({"title": section_titles[key], "type": clean(s.get("type")),
                          "shared_with": names, "shared_with_count": len(names),
                          "played_by": played, "played_by_count": None if played is None else len(played)})
        # Only flag a library when the whole window was read and someone who can see it has had
        # the full window to use it (invited before it started, or invite date unknown).
        if activity["complete"] and can_see and played == [] and any(
                not p["invited"] or now - p["invited"] > args.inactive_days * DAY for p in can_see):
            unused.append(section_titles[key])
    if unused:
        flags.append({"kind": "unused_library", "libraries": sorted(unused), "days": args.inactive_days})

    totals = {"people": len(people), "by_kind": {}, "by_status": {}}
    for p in people:
        totals["by_kind"][p["kind"]] = totals["by_kind"].get(p["kind"], 0) + 1
        totals["by_status"][p["status"]] = totals["by_status"].get(p["status"], 0) + 1

    area = sharing_area(people)
    report = {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z"),
        "inactive_days": args.inactive_days,
        "server": {"name": clean(root.get("friendlyName")), "version": clean(root.get("version")),
                   "libraries": len(sections)},
        "people": [
            {key: (day(value) if key == "invited" else value)
             for key, value in p.items() if not key.startswith("_")}
            for p in people
        ],
        "libraries": libraries,
        "library_activity": activity,
        "totals": totals,
        "worth_a_look": flags,
        "unavailable": unavailable,
        "since_snapshot": since_snapshot(machine_id, area, args),
        "media_deletion_allowed": media_deletion_allowed(lambda: plex.get("/:/prefs")),
    }
    if args.snapshot_items:
        report["snapshot"] = {"server_id": machine_id, "area": area}
    return report


def check(config):
    root = PlexClient(*config["plex"]).get("/")
    PlexTvClient(config["plex"][1]).get("https://plex.tv/api/users")
    return {"ok": True, "plex": {"server": clean(root.get("friendlyName")), "version": clean(root.get("version"))},
            "plex_tv": {"ok": True}}


def main():
    parser = argparse.ArgumentParser(description="Read-only report of who a Plex server is shared with (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connections")
    parser.add_argument("--inactive-days", type=int, default=90,
                        help="days without a play that count as inactive (default 90)")
    parser.add_argument("--since", type=int, help="compare with a snapshot at least this many days old (1-90)")
    parser.add_argument("--snapshot-items", action="store_true",
                        help="add this run's part of a snapshot (used by the changes skill and dashboard)")
    args = parser.parse_args()
    if args.since is not None:
        args.since = max(1, min(args.since, 90))
    args.inactive_days = max(1, args.inactive_days)

    try:
        config = load_config()
        if args.check:
            result = check(config)
        else:
            try:
                result = build_report(config, args)
            except (AttributeError, KeyError, TypeError, ValueError):
                raise ReportError("Plex or plex.tv sent data in a shape Cinemetric didn't expect.") from None
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
