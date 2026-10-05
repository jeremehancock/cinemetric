#!/usr/bin/env python3
"""Cinemetric users and shares: read-only overview of who can reach a Plex server.

Lists the people the server is shared with (friends, Plex Home members, managed users and pending
invites), which libraries each one can see, whether they can download, and when they last played
something. Who a server is shared with is only stored in the owner's plex.tv account, so this script
also sends read-only GET requests to three plex.tv addresses. Last played dates come from Tautulli
when it is set up, otherwise from the server's own watch history.

Uses only the Python standard library. Prints one JSON document to stdout; errors go to stderr.

Safety rules: see openspec/specs/security/spec.md in the Cinemetric repository.
"""

import argparse
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

VERSION = "0.13.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
MAX_PLEX_TV_BYTES = 5 * 1024 * 1024
OLD_INVITE_DAYS = 30
DAY = 86400

# The only Plex server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/status/sessions/history/all$"),
]

# The only plex.tv addresses this script may request, and how. All of them only read data.
PLEX_TV_RULES = [
    ("GET", re.compile(r"^https://plex\.tv/api/users$")),
    ("GET", re.compile(r"^https://plex\.tv/api/servers/[A-Za-z0-9]+/shared_servers$")),
    ("GET", re.compile(r"^https://plex\.tv/api/invites/requested$")),
]

# The only Tautulli API command this script may run. It only reads data.
TAUTULLI_COMMANDS = {"get_users_table"}

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
    flags = worth_a_look(people, args.inactive_days, now)
    people.sort(key=lambda p: (KIND_ORDER[p["kind"]], p["name"].lower()))

    libraries = []
    for s in sections:
        key = str(s.get("key"))
        names = sorted(
            p["name"] for p in people
            if p["status"] == "accepted"
            and (p["libraries"] == "all" or key in p["_keys"])
        )
        libraries.append({"title": section_titles[key], "type": clean(s.get("type")),
                          "shared_with": names, "shared_with_count": len(names)})

    totals = {"people": len(people), "by_kind": {}, "by_status": {}}
    for p in people:
        totals["by_kind"][p["kind"]] = totals["by_kind"].get(p["kind"], 0) + 1
        totals["by_status"][p["status"]] = totals["by_status"].get(p["status"], 0) + 1

    return {
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
        "totals": totals,
        "worth_a_look": flags,
        "unavailable": unavailable,
    }


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
    args = parser.parse_args()
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
