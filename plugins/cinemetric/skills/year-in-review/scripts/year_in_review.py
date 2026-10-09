#!/usr/bin/env python3
"""Cinemetric year in review: a recap page of one calendar year of watching on a Plex server.

Reads watch history from Tautulli when it is configured (watch time per play) and from Plex's own
history otherwise (finished plays only). Writes a self-contained HTML page by fixed rules (no
scripts, no outside requests) and prints a JSON summary. Uses only the Python standard library.

A whole-server recap names no one: people appear only as a count, and a title is listed only when
enough different people played it. See openspec/specs/year-in-review/spec.md.

It never publishes anything: when the user wants recaps online, Claude publishes the page as a
private claude.ai page. This script only remembers that choice and each recap's link.

  year_in_review.py [--year YYYY] [--me | --user NAME] [...]    build a recap
  year_in_review.py destination local|online|both                save where recaps go
  year_in_review.py online-page --recap ID --url LINK | --forget  save or forget a recap's page link

Safety rules: see openspec/specs/security/spec.md in the Cinemetric repository.
"""

import argparse
import hashlib
import html
import ipaddress
import json
import os
import re
import ssl
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.30.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
MAX_NAMES_LISTED = 30
PAGE_SIZE = 1000
HISTORY_CAP = 100000
FIRST_YEAR = 2000
# Tautulli's date filters leave out the named day itself and use Tautulli's own time zone, so the
# request covers a couple of extra days each side and rows are kept by their exact start time.
TAUTULLI_MARGIN_DAYS = 2
PLEX_OWNER_ACCOUNT = "1"
KINDS = (("movie", "movies"), ("episode", "tv"), ("track", "music"))

# The only Plex server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
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


class ReportError(Exception):
    """An error with a message that is safe to show the user."""


class PersonError(ReportError):
    """--user matched nobody or several people. Never a reason to fall back to another source."""


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
            "X-Plex-Client-Identifier": "cinemetric-year-in-review",
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


def hours(seconds):
    return round(as_int(seconds) / 3600, 1)


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


def person_key(account_id, is_owner):
    """What a person's recap file and saved link are keyed on, the same whichever source is used.

    Tautulli's user ids are the people's Plex account ids, so they match Plex's /accounts, except
    for the server owner: Plex's server calls the owner account 1, Tautulli uses their plex.tv id.
    """
    return "owner" if is_owner else str(account_id)


def tautulli_person(client, wanted):
    people = []
    for u in client.call("get_users") or []:
        names = [n for n in (clean(u.get("friendly_name")), clean(u.get("username"))) if n]
        if names and u.get("user_id") is not None:
            people.append({"name": names[0], "names": names, "id": u.get("user_id"),
                           "key": person_key(u.get("user_id"), as_int(u.get("is_admin")))})
    return pick_person(wanted, people, "Tautulli")


# ---------------------------------------------------------------- the year and its plays

KIND_NAMES = dict(KINDS)


def year_window(year, now=None):
    """(start, end, partial): local midnight on 1 January up to the next 1 January, or up to now."""
    now = time.time() if now is None else now
    start = time.mktime((year, 1, 1, 0, 0, 0, 0, 0, -1))
    end = time.mktime((year + 1, 1, 1, 0, 0, 0, 0, 0, -1))
    return (start, now, True) if now < end else (start, end, False)


def label(kind, title, year, grandparent):
    """Movies by title and year; episodes count toward their show and tracks toward their artist."""
    if kind == "movie":
        title = clean(title)
        return clean(f"{title} ({as_int(year)})") if title and as_int(year) else title
    return clean(grandparent)


def play(person, kind, title, started, seconds):
    return {"person": str(person), "kind": kind, "title": title, "started": started, "seconds": seconds}


def tautulli_plays(client, args, start, end):
    """Return (plays, capped, person). Plays have watch time with pauses left out."""
    person, only = None, {}
    if args.me:
        owners = [u for u in client.call("get_users") or []
                  if as_int(u.get("is_admin")) and u.get("user_id") is not None]
        if not owners:
            raise PersonError("USER_NOT_FOUND: Tautulli doesn't say which of its users is the server "
                              "owner, so a recap of your own year can't be made from it.")
        person = {"id": owners[0]["user_id"], "name": None}
    elif args.user:
        person = tautulli_person(client, args.user)
    if person:
        only = {"user_id": person["id"]}

    margin = TAUTULLI_MARGIN_DAYS * 86400
    after = time.strftime("%Y-%m-%d", time.localtime(start - margin))
    before = time.strftime("%Y-%m-%d", time.localtime(end + margin))
    plays, offset = [], 0
    while len(plays) < HISTORY_CAP:
        # grouping=1 merges a play that was paused and resumed later into one row.
        page = client.call("get_history", after=after, before=before, grouping=1, order_column="date",
                           order_dir="desc", start=offset, length=PAGE_SIZE, **only) or {}
        batch = page.get("data", []) or []
        for row in batch:
            kind, started = row.get("media_type"), as_int(row.get("started") or row.get("date"))
            if kind not in KIND_NAMES or as_int(row.get("live")) or not start <= started < end:
                continue
            # play_duration already leaves out paused time; older Tautulli only has duration.
            seconds = row.get("play_duration")
            if seconds is None:
                seconds = row.get("duration")
            plays.append(play(row.get("user_id"), kind,
                              label(kind, row.get("title"), row.get("year"), row.get("grandparent_title")),
                              started, max(0, as_int(seconds))))
            if len(plays) >= HISTORY_CAP:
                break
        offset += len(batch)
        if len(batch) < PAGE_SIZE:
            break
    return plays, len(plays) >= HISTORY_CAP, person


def plex_plays(client, args, start, end):
    """Return (plays, capped, person). Plex records finished plays only, with no watch time."""
    person = None
    if args.me or args.user:
        accounts = client.get("/accounts").get("Account", []) or []
        if args.me:
            if not any(str(a.get("id")) == PLEX_OWNER_ACCOUNT for a in accounts):
                raise PersonError("USER_NOT_FOUND: Plex didn't list the server owner's account, so a "
                                  "recap of your own year can't be made from it.")
            person = {"id": PLEX_OWNER_ACCOUNT, "name": None}
        else:
            people = [{"name": clean(a.get("name")), "names": [clean(a.get("name"))], "id": str(a.get("id")),
                       "key": person_key(a.get("id"), str(a.get("id")) == PLEX_OWNER_ACCOUNT)}
                      for a in accounts if clean(a.get("name"))]
            person = pick_person(args.user, people, "Plex")

    plays, offset = [], 0
    while len(plays) < HISTORY_CAP:
        page = client.get("/status/sessions/history/all", {"sort": "viewedAt:desc"},
                          start=offset, size=PAGE_SIZE)
        batch = page.get("Metadata", []) or []
        for v in batch:
            kind, started = v.get("type"), as_int(v.get("viewedAt"))
            if kind not in KIND_NAMES or not start <= started < end:
                continue
            if person and str(v.get("accountID")) != str(person["id"]):
                continue
            plays.append(play(v.get("accountID"), kind,
                              label(kind, v.get("title"), v.get("year"), v.get("grandparentTitle")),
                              started, None))
            if len(plays) >= HISTORY_CAP:
                break
        offset += len(batch)
        if not batch or as_int(batch[-1].get("viewedAt")) < start:
            break
    return plays, len(plays) >= HISTORY_CAP, person


# ---------------------------------------------------------------- counting

def summarize(plays, args, scope, has_hours, year, end, partial):
    """Everything the recap shows. Built from counts only: no name, id, device or play time is kept."""
    def bucket():
        return {"plays": 0, "seconds": 0}

    def metric(b):
        return b["seconds"] if has_hours else b["plays"]

    def hrs(seconds):
        return hours(seconds) if has_hours else None

    by_type = {name: bucket() for _, name in KINDS}
    months = [bucket() for _ in range(12)]
    days, titles, people = {}, {}, set()
    for p in plays:
        t = time.localtime(p["started"])
        day = days.setdefault(time.strftime("%Y-%m-%d", t), bucket())
        for b in (by_type[KIND_NAMES[p["kind"]]], months[t.tm_mon - 1], day):
            b["plays"] += 1
            b["seconds"] += p["seconds"] or 0
        people.add(p["person"])
        if p["title"]:
            g = titles.setdefault((p["kind"], p["title"]), dict(bucket(), viewers=set()))
            g["plays"] += 1
            g["seconds"] += p["seconds"] or 0
            g["viewers"].add(p["person"])

    busiest_month = None
    for i, m in enumerate(months):
        # Strictly greater, so the earlier month wins a tie.
        if m["plays"] and (busiest_month is None or metric(m) > metric(months[busiest_month])):
            busiest_month = i
    busiest_day = None
    for date in sorted(days):
        if busiest_day is None or metric(days[date]) > metric(days[busiest_day]):
            busiest_day = date

    def top(kind):
        rows = sorted(((title, g) for (k, title), g in titles.items() if k == kind),
                      key=lambda r: (-metric(r[1]), r[0].lower(), r[0]))
        held_back = 0
        if scope == "server":
            # A title only one person played says what that person watched, so it stays off the list.
            held_back = sum(1 for _, g in rows[:args.top] if len(g["viewers"]) < args.min_viewers)
            rows = [r for r in rows if len(r[1]["viewers"]) >= args.min_viewers]
        entries = []
        for title, g in rows[:args.top]:
            entry = {"title": title, "plays": g["plays"], "hours": hrs(g["seconds"])}
            if scope == "server":
                entry["viewers"] = len(g["viewers"])
            entries.append(entry)
        return {"entries": entries, "held_back": held_back}

    return {
        "totals": {
            "plays": len(plays),
            "hours": hrs(sum(p["seconds"] or 0 for p in plays)),
            "titles": len(titles),
            "active_days": len(days),
        },
        "people": len(people) if scope == "server" else None,
        "by_type": {name: {"plays": b["plays"], "hours": hrs(b["seconds"])} for name, b in by_type.items()},
        "months": [
            {"month": i + 1, "plays": m["plays"], "hours": hrs(m["seconds"]),
             "future": partial and time.mktime((year, i + 1, 1, 0, 0, 0, 0, 0, -1)) > end}
            for i, m in enumerate(months)
        ],
        "busiest_month": None if busiest_month is None else {
            "month": busiest_month + 1, "plays": months[busiest_month]["plays"],
            "hours": hrs(months[busiest_month]["seconds"])},
        "busiest_day": None if busiest_day is None else {
            "date": busiest_day, "plays": days[busiest_day]["plays"], "hours": hrs(days[busiest_day]["seconds"])},
        "top_movies": top("movie"),
        "top_shows": top("episode"),
        "top_artists": top("track"),
    }


# ---------------------------------------------------------------- reading the history

def read_history(config, args, start, end):
    """Return (plays, capped, person, source, fallback_reason), choosing a source like watch-activity."""
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

    if not config["plex"]:
        raise ReportError(
            "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN)."
        )
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
            "OWNER_ONLY: Plex only shares the server's watch history with the server owner's "
            "account. Connect with the owner's account, or set up Tautulli."
        ) from None
    return plays, capped, person, "plex", fallback_reason


def recap_id(year, scope, person):
    """The recap's name in file names and saved links. A hash stands in for a person, never a name."""
    if scope == "me":
        return f"{year}-me"
    if scope == "user":
        return f"{year}-person-" + hashlib.sha256(person["key"].encode("utf-8")).hexdigest()[:8]
    return str(year)


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


def build(config, args):
    start, end, partial = year_window(args.year)
    plays, capped, person, source, fallback_reason = read_history(config, args, start, end)
    scope = "me" if args.me else "user" if args.user else "server"
    has_hours = source == "tautulli"
    rid = recap_id(args.year, scope, person)
    report = {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z"),
        "year": args.year,
        "partial_year": partial,
        "scope": scope,
        "user": person["name"] if scope == "user" else None,
        "source": source,
        "fallback_reason": fallback_reason,
        "history_capped": capped,
        "min_viewers": args.min_viewers if scope == "server" else None,
        "hours_unavailable": None if has_hours else
            "Plex's own history records finished plays only, not how long anyone watched.",
        **summarize(plays, args, scope, has_hours, args.year, end, partial),
    }

    output = None
    if not args.json_only:
        output = os.path.abspath(os.path.expanduser(args.output or default_output(rid)))
        title, body = render(report)
        write_page(output, full_page(title, body))

    state = load_state()
    destination = saved_destination(state)
    report.update({
        "output": output,
        "recap_id": rid,
        "destination": destination,
        "online_page": saved_online_page(state, rid),
        "ask": [] if destination else ["destination"],
        "media_deletion_allowed": media_deletion_allowed(
            lambda: PlexClient(*config["plex"]).get("/:/prefs")) if config["plex"] else None,
    })
    return report


def check(config):
    result = {"ok": True, "plex": None, "tautulli": None}
    if config["plex"]:
        root = PlexClient(*config["plex"]).get("/")
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


# ---------------------------------------------------------------- page helpers

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")
NOUNS = {"top_movies": ("movie", "movies"), "top_shows": ("show", "shows"),
         "top_artists": ("artist", "artists")}


def e(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def num(value):
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return "–"


def hours_text(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "–"
    if value <= 0:
        return "0 min"
    if value < 1:
        return f"{max(1, round(value * 60))} min"
    if value < 10:
        return f"{value:.1f}".rstrip("0").rstrip(".") + " h"
    return f"{num(value)} h"


def plural(n, one, many=None):
    return f"{num(n)} {one if n == 1 else (many or one + 's')}"


def amount(b, has_hours):
    """How much a month, day or title holds: hours and plays with Tautulli, plays with Plex."""
    if not b["plays"]:
        return "nothing played"
    plays = plural(b["plays"], "play")
    return f"{hours_text(b['hours'])}, {plays}" if has_hours else plays


def long_date(iso):
    t = time.strptime(iso, "%Y-%m-%d")
    return f"{time.strftime('%A', t)}, {MONTHS[t.tm_mon - 1]} {t.tm_mday}"


def tile(label_text, value, note=""):
    note_html = f'<span class="tile-note">{note}</span>' if note else ""
    return (f'<div class="tile"><span class="tile-label">{e(label_text)}</span>'
            f'<span class="tile-value">{value}</span>{note_html}</div>')


def card(title, body, aside=""):
    aside_html = f'<span class="card-aside">{aside}</span>' if aside else ""
    return (f'<section class="card"><header class="card-head"><h2>{e(title)}</h2>'
            f'{aside_html}</header>{body}</section>')


def nice_step(peak, ticks=4):
    """A round tick step (1, 2, 5, 10, 20, 50...) so every axis label is a whole, round number."""
    raw = max(peak, 1) / ticks
    magnitude = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 1
    for step in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        value = step * magnitude
        if value >= raw and value == int(value):
            return int(value)
    return 10 * magnitude


def bar_chart(bars, w, h, css_class, aria, left=40):
    """An inline SVG bar chart. Each bar has a value, an axis label and a tooltip; the tallest is marked."""
    bottom, top = 24, 10
    plot_w, plot_h = w - left - 8, h - bottom - top
    peak = max(b["value"] for b in bars)
    step = nice_step(peak)
    ymax = step * 4
    slot = plot_w / len(bars)
    bar_w = max(slot - 4, 1)
    parts = [f'<svg class="{css_class}" viewBox="0 0 {w} {h}" role="img" aria-label="{e(aria)}">']
    for i in range(5):
        y = top + plot_h - plot_h * i / 4
        parts.append(f'<line class="{"baseline" if i == 0 else "grid"}" x1="{left}" x2="{w - 8}" '
                     f'y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{num(step * i)}</text>')
    for i, b in enumerate(bars):
        x = left + i * slot + 2
        bh = plot_h * b["value"] / ymax
        y = top + plot_h - bh
        if bh > 0:
            r = min(4, bar_w / 2, bh)
            path = (f"M{x:.1f},{top + plot_h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
                    f"H{x + bar_w - r:.1f} Q{x + bar_w:.1f},{y:.1f} {x + bar_w:.1f},{y + r:.1f} "
                    f"V{top + plot_h:.1f} Z")
            peak_cls = " bar-peak" if b["peak"] else ""
            parts.append(f'<path class="bar{peak_cls}" d="{path}"><title>{e(b["tip"])}</title></path>')
        # A full-height, invisible hit area so short or empty bars still show their tooltip.
        parts.append(f'<rect class="hit" x="{x - 2:.1f}" y="{top}" width="{slot:.1f}" height="{plot_h}">'
                     f'<title>{e(b["tip"])}</title></rect>')
        parts.append(f'<text class="tick" x="{x + bar_w / 2:.1f}" y="{h - 6}" text-anchor="middle">'
                     f'{e(b["label"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------- page sections

def who_line(report):
    year = f"{report['year']} so far" if report["partial_year"] else str(report["year"])
    if report["scope"] == "me":
        return "Your year", year
    if report["scope"] == "user":
        return report["user"], year
    return "Everyone's year", year


def tiles(report, has_hours):
    t = report["totals"]
    items = []
    if has_hours:
        days = round(t["hours"] / 24)
        items.append(tile("Hours watched", num(t["hours"]), f"about {plural(days, 'day')} of viewing" if days >= 2 else ""))
    items.append(tile("Plays", num(t["plays"]), "finished plays" if not has_hours else ""))
    items.append(tile("Titles", num(t["titles"]), "movies, shows and artists"))
    items.append(tile("Days watched", num(t["active_days"])))
    if report["scope"] == "server":
        items.append(tile("People", num(report["people"]), "watched something"))
    return f'<section class="tiles" aria-label="Totals">{"".join(items)}</section>'


def months_card(report, has_hours):
    busiest = report["busiest_month"]
    bars = []
    for m in report["months"]:
        name = MONTHS[m["month"] - 1]
        value = (m["hours"] or 0) if has_hours else m["plays"]
        tip = f"{name}: still to come" if m["future"] else f"{name}: {amount(m, has_hours)}"
        bars.append({"value": value, "label": name[:3], "tip": tip,
                     "peak": bool(busiest) and m["month"] == busiest["month"]})
    unit = "Hours" if has_hours else "Plays"
    aria = f"{unit} watched each month of {report['year']}"
    chart = (bar_chart(bars, 720, 220, "chart chart-wide", aria)
             + bar_chart([dict(b, label=b["label"][0]) for b in bars], 360, 200, "chart chart-narrow", aria))
    aside = f"Busiest: {e(MONTHS[busiest['month'] - 1])}, {e(amount(busiest, has_hours))}" if busiest else ""
    day = report["busiest_day"]
    day_html = (f'<p class="busiest-day"><span class="muted">Busiest day</span> '
                f'<strong>{e(long_date(day["date"]))}</strong> · {e(amount(day, has_hours))}</p>') if day else ""
    return card(f"{unit} by month", chart + day_html, aside)


def split_card(report, has_hours):
    names = (("movies", "Movies"), ("tv", "TV"), ("music", "Music"))
    values = {key: (report["by_type"][key]["hours"] or 0) if has_hours else report["by_type"][key]["plays"]
              for key, _ in names}
    total = sum(values.values()) or 1
    rows = "".join(
        f'<li><div class="rank-line"><span>{text}</span><span class="mono">{round(100 * values[key] / total)}% · '
        f'{e(amount(report["by_type"][key], has_hours))}</span></div>'
        f'<div class="rank-track"><div class="rank-bar" style="width:{100 * values[key] / total:.1f}%"></div></div></li>'
        for key, text in names)
    return card("Movies, TV and music", f'<ol class="split">{rows}</ol>')


def ranked(title, top, has_hours, server, min_viewers=None):
    entries = top["entries"]
    if not entries:
        empty = (f"None played by at least {plural(min_viewers, 'person', 'people')}." if top["held_back"]
                 else "Nothing to list.")
        return f'<div class="ranked"><h3>{e(title)}</h3><p class="muted small">{e(empty)}</p></div>'
    key = "hours" if has_hours else "plays"
    best = max(r[key] or 0 for r in entries) or 1
    items = []
    for r in entries:
        value = hours_text(r["hours"]) if has_hours else plural(r["plays"], "play")
        detail = [plural(r["plays"], "play")] if has_hours else []
        if server:
            detail.append(plural(r["viewers"], "person", "people"))
        detail_html = f'<span class="rank-detail">{e(" · ".join(detail))}</span>' if detail else ""
        items.append(
            f'<li><div class="rank-line"><span class="rank-name">{e(r["title"])}</span>'
            f'<span class="mono">{e(value)}</span></div>'
            f'<div class="rank-track"><div class="rank-bar" style="width:{100 * (r[key] or 0) / best:.1f}%"></div></div>'
            f'{detail_html}</li>')
    return f'<div class="ranked"><h3>{e(title)}</h3><ol>{"".join(items)}</ol></div>'


def held_back_note(report):
    parts = []
    for key in ("top_movies", "top_shows", "top_artists"):
        n = report[key]["held_back"]
        if n:
            parts.append(plural(n, *NOUNS[key]))
    if not parts:
        return ""
    things = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    total = sum(report[k]["held_back"] for k in NOUNS)
    who = "only one person" if report["min_viewers"] == 2 else f"fewer than {report['min_viewers']} people"
    verb = "was" if total == 1 else "were"
    return (f'<p class="note">{e(things)} watched by {e(who)} {verb} left out to keep each person\'s '
            f'viewing private.</p>')


def top_card(report, has_hours):
    server = report["scope"] == "server"
    if server and report["people"] < report["min_viewers"]:
        body = (f'<p class="note">Fewer than {num(report["min_viewers"])} people watched anything this year, '
                f'so there are no top lists: they would show what one person watched. A recap of your own '
                f'year shows your favorites.</p>')
        return card("Most watched", body)
    lists = "".join(ranked(title, report[key], has_hours, server, report["min_viewers"])
                    for title, key in (("Movies", "top_movies"), ("TV shows", "top_shows"),
                                       ("Music artists", "top_artists")))
    aside = "by hours watched" if has_hours else "by plays"
    if server:
        aside += f", played by at least {plural(report['min_viewers'], 'person', 'people')}"
    return card("Most watched", f'<div class="lists">{lists}</div>' + (held_back_note(report) if server else ""),
                aside)


def notes(report):
    items = []
    if report["hours_unavailable"]:
        items.append("Plex's own history counts finished plays only and doesn't record watch time, so this "
                     "recap counts plays.")
    if report["history_capped"]:
        items.append(f"This year has more than {num(HISTORY_CAP)} plays; the first {num(HISTORY_CAP)} "
                     f"found are counted.")
    return "".join(f'<p class="muted small">{e(text)}</p>' for text in items)


def render(report):
    has_hours = report["hours_unavailable"] is None
    who, year = who_line(report)
    if report["totals"]["plays"]:
        sections = (tiles(report, has_hours) + months_card(report, has_hours) + split_card(report, has_hours)
                    + top_card(report, has_hours))
    else:
        sections = card("Nothing played", f'<p>Nothing was played in {e(report["year"])}.</p>')
    sub = {"server": "Everyone on the server, together. Nobody is named.",
           "me": "Only what you watched.",
           "user": "Only what this person watched."}[report["scope"]]
    body = f"""<main class="page">
<header class="masthead">
 <div><span class="eyebrow">Cinemetric · Year in review</span><h1>{e(who)}: {e(year)}</h1></div>
 <div class="masthead-meta"><span>{e(sub)}</span></div>
</header>
{sections}
{notes(report)}
<footer class="foot"><span>Made by Cinemetric {e(VERSION)} from your server's watch history on {e(report["generated_at"])}.</span>
<span>Numbers come from your server; written notes are rule-based, not AI.</span></footer>
</main>"""
    return f"<title>{e(who)}: {e(year)} in review</title>", body


CSS = """
:root {
  --bg: #eef0f2; --panel: #ffffff; --ink: #14171a; --ink-2: #4a525a; --muted: #7b838b;
  --line: #dde1e5; --grid: #e6e9ec; --axis: #c2c8ce; --accent: #2a78d6; --accent-soft: #cde2fb; --peak: #184f95;
  /* Installed fonts only (nothing is downloaded). */
  --font-display: "Big Shoulders Display", "Arial Narrow", "Roboto Condensed", "Avenir Next Condensed",
    Bahnschrift, "Nimbus Sans Narrow", "Liberation Sans Narrow", "DejaVu Sans Condensed", sans-serif;
  --font-body: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0f1113; --panel: #181b1e; --ink: #eef1f3; --ink-2: #b8c0c7; --muted: #8a939b;
  --line: #2a2f34; --grid: #23272b; --axis: #3a4046; --accent: #3987e5; --accent-soft: #1c3a5e; --peak: #86b6ef;
  color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #0f1113; --panel: #181b1e; --ink: #eef1f3; --ink-2: #b8c0c7; --muted: #8a939b;
  --line: #2a2f34; --grid: #23272b; --axis: #3a4046; --accent: #3987e5; --accent-soft: #1c3a5e; --peak: #86b6ef;
  color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 var(--font-body); }
.page { max-width: 64rem; margin: 0 auto; padding-inline: 16px; padding-block: 20px 40px; display: grid; gap: 16px; }
h1, h2, h3 { margin: 0; text-wrap: balance; }
.muted { color: var(--muted); }
.small { font-size: 13px; margin: 0; }
.mono { font-family: var(--font-mono); font-size: 13px; font-variant-numeric: tabular-nums; }
.masthead { display: flex; flex-wrap: wrap; align-items: end; justify-content: space-between; gap: 8px 16px;
  padding-block: 4px 12px; border-bottom: 2px solid var(--ink); }
.masthead h1 { font-family: var(--font-display); font-weight: 800; font-size: 40px; line-height: 1;
  letter-spacing: .01em; text-transform: uppercase; font-stretch: condensed; overflow-wrap: anywhere; }
.masthead .eyebrow { display: block; font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
  color: var(--muted); margin-bottom: 4px; }
.masthead-meta { color: var(--ink-2); font-size: 13px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr)); gap: 12px; }
.tile { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px;
  display: grid; gap: 2px; align-content: start; }
.tile-label { font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.tile-value { font-family: var(--font-display); font-weight: 700; font-size: 38px; line-height: 1.05; font-stretch: condensed; }
.tile-note { font-size: 13px; color: var(--ink-2); }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 16px;
  min-width: 0; display: grid; gap: 12px; align-content: start; }
.card-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 4px 12px; }
.card-head h2 { font-family: var(--font-display); font-weight: 700; font-size: 22px; letter-spacing: .02em;
  text-transform: uppercase; font-stretch: condensed; }
.card-aside { font-size: 13px; color: var(--muted); }
.card h3 { font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); font-weight: 600;
  margin-bottom: 6px; }
ul, ol { list-style: none; margin: 0; padding: 0; }
.chart { width: 100%; height: auto; display: block; }
.chart-narrow { display: none; }
@media (max-width: 36rem) { .chart-wide { display: none; } .chart-narrow { display: block; } }
.chart .grid { stroke: var(--grid); stroke-width: 1; }
.chart .baseline { stroke: var(--axis); stroke-width: 1; }
.chart .tick { fill: var(--muted); font: 11px var(--font-mono); }
.chart .bar { fill: var(--accent); }
.chart .bar-peak { fill: var(--peak); }
.chart .hit { fill: transparent; }
.chart .hit:hover { fill: var(--accent-soft); fill-opacity: .35; }
.busiest-day { margin: 0; display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: baseline; }
.lists { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr)); gap: 20px 24px; }
.ranked { min-width: 0; }
.ranked ol, .split { display: grid; gap: 8px; }
.rank-line { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; font-size: 14px; }
.rank-line .mono { white-space: nowrap; }
.rank-name { min-width: 0; overflow-wrap: anywhere; }
.rank-track { height: 6px; margin-top: 3px; }
.rank-bar { height: 100%; background: var(--accent); border-radius: 0 3px 3px 0; min-width: 2px; }
.rank-detail { display: block; font-size: 12px; color: var(--muted); margin-top: 2px; }
.note { margin: 0; padding: 10px 12px; border-left: 3px solid var(--line); color: var(--ink-2); font-size: 14px; }
.foot { font-size: 12px; color: var(--muted); display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; }
@media (max-width: 30rem) { .masthead h1 { font-size: 32px; } .tile-value { font-size: 32px; }
  .rank-line { flex-wrap: wrap; } }
"""

# The page loads nothing from outside itself; the browser enforces this. Text uses installed fonts.
CSP = ('<meta http-equiv="Content-Security-Policy" '
       'content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:">')


def full_page(title, body):
    return (f'<!doctype html>\n<html lang="en"><head>{CSP}\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'{title}\n<style>{CSS}</style>\n</head><body>\n{body}\n</body></html>\n')


# ---------------------------------------------------------------- files and saved choices

def data_dir():
    if os.environ.get("CINEMETRIC_DATA_DIR"):
        return os.environ["CINEMETRIC_DATA_DIR"]
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "cinemetric")


def default_output(rid):
    return os.path.join(data_dir(), f"year-in-review-{rid}.html")


def ensure_private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    if os.name == "posix":
        os.chmod(path, 0o700)


def write_page(path, content):
    """Write a file atomically, readable only by the user."""
    folder = os.path.dirname(os.path.abspath(path))
    ensure_private_dir(folder)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".cinemetric-", suffix=".tmp")
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


DESTINATIONS = ("local", "online", "both")
# Saved links are handed back to Claude as pages to update, so only accept the exact shape of a
# claude.ai page link, and only recap ids this script makes.
ONLINE_PAGE_RE = re.compile(r"https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9-]{1,100}")
RECAP_ID_RE = re.compile(r"\d{4}(?:-me|-person-[0-9a-f]{8})?")


def state_path():
    return os.path.join(data_dir(), "year-in-review-state.json")


def load_state():
    try:
        with open(state_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state):
    write_page(state_path(), json.dumps(state, indent=1))


def saved_destination(state):
    value = state.get("destination")
    return value if value in DESTINATIONS else None


def saved_pages(state):
    pages = state.get("online_pages")
    return pages if isinstance(pages, dict) else {}


def saved_online_page(state, rid):
    value = saved_pages(state).get(rid)
    return value if isinstance(value, str) and ONLINE_PAGE_RE.fullmatch(value) else None


def cmd_destination(args):
    state = load_state()
    state["destination"] = args.choice
    save_state(state)
    return {"destination": args.choice}


def cmd_online_page(args):
    rid = args.recap.strip()
    if not RECAP_ID_RE.fullmatch(rid):
        raise ReportError("That isn't a recap id. Use the recap_id a recap build printed, such as 2025, "
                          "2025-me or 2025-person-1a2b3c4d.")
    state = load_state()
    pages = dict(saved_pages(state))
    if args.forget:
        pages.pop(rid, None)
    else:
        url = args.url.strip()
        if not ONLINE_PAGE_RE.fullmatch(url):
            raise ReportError("That isn't a claude.ai page link. It should look like "
                              "https://claude.ai/artifact/... or https://claude.ai/code/artifact/...")
        pages[rid] = url
    state["online_pages"] = pages
    save_state(state)
    return {"recap_id": rid, "destination": saved_destination(state), "online_page": saved_online_page(state, rid)}


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Build a Plex year-in-review recap page (JSON summary on stdout).")
    parser.add_argument("--check", action="store_true", help="only test the connections")
    parser.add_argument("--year", type=int, default=time.localtime().tm_year, help="the calendar year (default: this year)")
    parser.add_argument("--me", action="store_true", help="only the server owner's own viewing")
    parser.add_argument("--user", help="only one person's viewing (name or part of a name)")
    parser.add_argument("--min-viewers", type=int, default=2,
                        help="in a whole-server recap, list a title only when this many people played it")
    parser.add_argument("--top", type=int, default=10, help="entries in each top list")
    parser.add_argument("--source", choices=["auto", "tautulli", "plex"], default="auto",
                        help="where to read history from (default: Tautulli if set up, else Plex)")
    parser.add_argument("--output", help="where to write the page (default: Cinemetric's data folder)")
    parser.add_argument("--json-only", action="store_true", help="print the summary without writing a page")
    sub = parser.add_subparsers(dest="command")
    dest = sub.add_parser("destination", help="save where recaps go")
    dest.add_argument("choice", choices=DESTINATIONS)
    page = sub.add_parser("online-page", help="save or forget a recap's claude.ai page link")
    page.add_argument("--recap", required=True, help="the recap_id a build printed")
    which = page.add_mutually_exclusive_group(required=True)
    which.add_argument("--url", help="the claude.ai page link")
    which.add_argument("--forget", action="store_true", help="forget the saved link")
    args = parser.parse_args()
    args.min_viewers = max(1, min(args.min_viewers, 10))
    args.top = max(1, min(args.top, 25))

    try:
        if args.command == "destination":
            result = cmd_destination(args)
        elif args.command == "online-page":
            result = cmd_online_page(args)
        else:
            this_year = time.localtime().tm_year
            if not args.check:
                if not FIRST_YEAR <= args.year <= this_year:
                    raise ReportError(f"The year must be from {FIRST_YEAR} to {this_year}.")
                if args.me and args.user:
                    raise ReportError("Choose either --me (your own year) or --user (one person's year), not both.")
            config = load_config()
            result = check(config) if args.check else build(config, args)
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
