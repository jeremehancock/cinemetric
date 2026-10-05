#!/usr/bin/env python3
"""Cinemetric watch activity: read-only summary of what's been watched on a Plex server.

Uses Tautulli when it is configured (full history, watch time, platforms) and falls back
to Plex's own watch history otherwise (play counts only). Uses only the Python standard
library. Prints one JSON document to stdout; errors go to stderr.

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

VERSION = "0.9.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
PLEX_PAGE_SIZE = 200
PLEX_HISTORY_CAP = 20000

# The only Plex server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/accounts$"),
    re.compile(r"^/status/sessions/history/all$"),
]

# The only Tautulli API commands this script may run. All of them only read data.
TAUTULLI_COMMANDS = {
    "get_tautulli_info",
    "get_home_stats",
    "get_history",
    "get_plays_by_date",
}


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
            "X-Plex-Client-Identifier": "cinemetric-watch-activity",
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


def when(epoch):
    epoch = as_int(epoch)
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch)) if epoch else None


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


def tautulli_report(client, args):
    stats = client.call("get_home_stats", time_range=args.days, stats_count=args.top)
    users = client.call("get_home_stats", time_range=args.days, stats_count=1000, stat_id="top_users")
    by_plays = client.call("get_plays_by_date", time_range=args.days, y_axis="plays") or {}
    by_time = client.call("get_plays_by_date", time_range=args.days, y_axis="duration") or {}
    after = time.strftime("%Y-%m-%d", time.localtime(time.time() - args.days * 86400))
    history = client.call("get_history", length=args.recent, order_column="date",
                          order_dir="desc", after=after) or {}

    def title_rows(stat_id, label):
        return [
            {"title": label(r), "plays": as_int(r.get("total_plays")), "hours": hours(r.get("total_duration"))}
            for r in stat_rows(stats, stat_id)
        ]

    movie_label = lambda r: clean(f"{r.get('title')} ({r['year']})" if r.get("year") else r.get("title"))
    show_label = lambda r: clean(r.get("grandparent_title") or r.get("title"))

    user_rows = [
        {"user": clean(r.get("friendly_name") or r.get("user")), "plays": as_int(r.get("total_plays")),
         "hours": hours(r.get("total_duration"))}
        for r in stat_rows(users, "top_users")
    ]

    dates = by_plays.get("categories", []) or []
    def series(data):
        # Tautulli adds its own "Total" series; leave it out so plays aren't counted twice.
        return {
            s.get("name"): s.get("data", []) or []
            for s in data.get("series", []) or []
            if str(s.get("name")).lower() != "total"
        }

    plays_series = series(by_plays)
    time_series = series(by_time)
    daily = []
    for i, date in enumerate(dates):
        daily.append({
            "date": date,
            "plays": sum(as_int(d[i]) for d in plays_series.values() if i < len(d)),
            "hours": hours(sum(as_int(d[i]) for d in time_series.values() if i < len(d))),
        })
    by_type = {clean(name).lower(): sum(as_int(v) for v in values) for name, values in plays_series.items()}

    # This stat has several rows (all streams, transcodes, direct plays...); use the all-streams one.
    concurrent = stat_rows(stats, "most_concurrent")
    peak = next((r for r in concurrent if r.get("title") == "Concurrent Streams"), None)

    recent = []
    for row in history.get("data", []) or []:
        recent.append({
            "when": when(row.get("date") or row.get("started")),
            "user": clean(row.get("friendly_name") or row.get("user")),
            "title": clean(row.get("full_title") or row.get("title")),
            "type": row.get("media_type"),
            "platform": clean(row.get("platform")) or None,
            "minutes": round(as_int(row.get("play_duration") or row.get("duration")) / 60),
            "percent_complete": as_int(row.get("percent_complete"), None),
            "method": {"copy": "direct stream"}.get(row.get("transcode_decision"), row.get("transcode_decision")),
            "live_tv": bool(as_int(row.get("live"))),
        })

    return {
        "source": "tautulli",
        "totals": {
            "plays": sum(d["plays"] for d in daily),
            "watch_hours": round(sum(d["hours"] for d in daily), 1),
            "active_users": len(user_rows),
        },
        "plays_by_type": by_type,
        "top_movies": title_rows("top_movies", movie_label),
        "top_shows": title_rows("top_tv", show_label),
        "top_music": title_rows("top_music", show_label),
        "top_users": user_rows[: args.top],
        "top_platforms": [
            {"platform": clean(r.get("platform")), "plays": as_int(r.get("total_plays")),
             "hours": hours(r.get("total_duration"))}
            for r in stat_rows(stats, "top_platforms")
        ],
        "most_concurrent_streams": {"streams": as_int(peak.get("count")), "when": when(peak.get("started"))}
        if peak else None,
        "daily": daily,
        "trend": trend(daily),
        "recent_plays": recent,
    }


# ---------------------------------------------------------------- plex fallback

def plex_report(client, args):
    # Start at midnight of the first day so the total matches the per-day counts.
    first_day = time.localtime(time.time() - (args.days - 1) * 86400)
    cutoff = time.mktime((first_day.tm_year, first_day.tm_mon, first_day.tm_mday, 0, 0, 0, 0, 0, -1))
    accounts = {
        str(a.get("id")): clean(a.get("name")) or f"user {a.get('id')}"
        for a in client.get("/accounts").get("Account", []) or []
    }

    views, start = [], 0
    while len(views) < PLEX_HISTORY_CAP:
        page = client.get("/status/sessions/history/all", {"sort": "viewedAt:desc"},
                          start=start, size=PLEX_PAGE_SIZE)
        batch = page.get("Metadata", []) or []
        views.extend(v for v in batch if as_int(v.get("viewedAt")) >= cutoff)
        start += len(batch)
        if not batch or as_int(batch[-1].get("viewedAt")) < cutoff:
            break

    def user_of(v):
        return accounts.get(str(v.get("accountID")), f"user {v.get('accountID')}")

    def label(v):
        kind = v.get("type")
        if kind == "episode":
            return clean(f"{v.get('grandparentTitle')} S{as_int(v.get('parentIndex')):02d}"
                         f"E{as_int(v.get('index')):02d}")
        if kind == "track":
            return clean(f"{v.get('grandparentTitle')} - {v.get('title')}")
        return clean(f"{v.get('title')} ({v['year']})" if v.get("year") else v.get("title"))

    def top(counter, key_name):
        rows = sorted(counter.items(), key=lambda kv: -kv[1])[: args.top]
        return [{key_name: k, "plays": n} for k, n in rows]

    movies, shows, music, users, by_type, by_day = {}, {}, {}, {}, {}, {}
    for v in views:
        kind = v.get("type")
        if kind == "movie":
            movies[label(v)] = movies.get(label(v), 0) + 1
        elif kind == "episode":
            name = clean(v.get("grandparentTitle"))
            shows[name] = shows.get(name, 0) + 1
        elif kind == "track":
            name = clean(v.get("grandparentTitle"))
            music[name] = music.get(name, 0) + 1
        users[user_of(v)] = users.get(user_of(v), 0) + 1
        type_name = {"movie": "movies", "episode": "tv", "track": "music"}.get(kind, str(kind))
        by_type[type_name] = by_type.get(type_name, 0) + 1
        day = time.strftime("%Y-%m-%d", time.localtime(as_int(v.get("viewedAt"))))
        by_day[day] = by_day.get(day, 0) + 1

    daily = []
    for i in range(args.days - 1, -1, -1):
        day = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
        daily.append({"date": day, "plays": by_day.get(day, 0)})

    return {
        "source": "plex",
        "totals": {"plays": len(views), "watch_hours": None, "active_users": len(users)},
        "plays_by_type": by_type,
        "top_movies": top(movies, "title"),
        "top_shows": top(shows, "title"),
        "top_music": top(music, "title"),
        "top_users": top(users, "user"),
        "top_platforms": [],
        "most_concurrent_streams": None,
        "daily": daily,
        "trend": trend(daily),
        "recent_plays": [
            {"when": when(v.get("viewedAt")), "user": user_of(v), "title": label(v), "type": v.get("type")}
            for v in views[: args.recent]
        ],
        "history_capped": len(views) >= PLEX_HISTORY_CAP,
    }


# ---------------------------------------------------------------- main

def build_report(config, args):
    fallback_reason = None
    report = None

    if args.source in ("auto", "tautulli"):
        if config["tautulli"]:
            print("reading watch history from Tautulli", file=sys.stderr)
            try:
                try:
                    report = tautulli_report(TautulliClient(*config["tautulli"]), args)
                except (AttributeError, KeyError, TypeError, IndexError, ValueError):
                    raise ReportError("Tautulli sent data in a shape Cinemetric didn't expect.") from None
            except ReportError as exc:
                if args.source == "tautulli":
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

    if report is None:
        if not config["plex"]:
            raise ReportError(
                "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
                "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN)."
            )
        print("reading watch history from Plex", file=sys.stderr)
        client = PlexClient(*config["plex"])
        try:
            report = plex_report(client, args)
        except ReportError as exc:
            if "401" not in str(exc) and "403" not in str(exc):
                raise
            client.get("/")  # still fails if the token itself is bad
            raise ReportError(
                "OWNER_ONLY: Plex only shares the server's watch history with the server owner's "
                "account. Connect with the owner's account, or set up Tautulli."
            ) from None

    return {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z"),
        "period_days": args.days,
        "fallback_reason": fallback_reason,
        **report,
    }


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


def main():
    parser = argparse.ArgumentParser(description="Read-only Plex watch activity report (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connections")
    parser.add_argument("--days", type=int, default=30, help="how many days of history to cover")
    parser.add_argument("--top", type=int, default=10, help="entries in each top list")
    parser.add_argument("--recent", type=int, default=15, help="recent plays to list")
    parser.add_argument("--source", choices=["auto", "tautulli", "plex"], default="auto",
                        help="where to read history from (default: Tautulli if set up, else Plex)")
    args = parser.parse_args()
    args.days = max(1, min(args.days, 3650))
    args.top = max(1, min(args.top, 50))
    args.recent = max(0, min(args.recent, 100))

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
