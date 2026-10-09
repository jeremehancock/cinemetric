#!/usr/bin/env python3
"""Cinemetric unwatched: read-only list of titles nobody has finished in a while.

Joins the Plex library (added dates and file sizes) with watch history from every account:
Tautulli's when it is configured, otherwise the Plex server's own. Only finished plays count.
Uses only the Python standard library. Prints one JSON document to stdout; errors go to stderr.

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

VERSION = "0.30.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
LIBRARY_PAGE_SIZE = 500
PLEX_HISTORY_PAGE_SIZE = 1000
TAUTULLI_PAGE_SIZE = 1000
HISTORY_CAP = 100000

# The only Plex server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
    re.compile(r"^/status/sessions/history/all$"),
    re.compile(r"^/:/prefs$"),
]

# The only Tautulli API commands this script may run. Both only read data.
TAUTULLI_COMMANDS = {
    "get_tautulli_info",
    "get_history",
}

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
TYPE_MOVIE, TYPE_EPISODE = 1, 4


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
            "X-Plex-Client-Identifier": "cinemetric-unwatched",
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


def gb(size):
    return round(size / 1e9, 1)


def pct(part, whole):
    return round(100 * part / whole, 1) if whole else 0.0


def months_before(now, months):
    """The same date and time `months` calendar months before `now`, clamped to the month's end."""
    t = time.localtime(now)
    year, month = divmod(t.tm_year * 12 + t.tm_mon - 1 - months, 12)
    month += 1
    mday = min(t.tm_mday, calendar.monthrange(year, month)[1])
    return time.mktime((year, month, mday, t.tm_hour, t.tm_min, t.tm_sec, 0, 0, -1))


def size_on_disk(item):
    """Every part of every version Plex can still find. Optimized versions use space too."""
    return sum(
        as_int(part.get("size"))
        for media in item.get("Media", []) or []
        if not media.get("deletedAt")
        for part in media.get("Part", []) or []
    )


# ---------------------------------------------------------------- library

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


def movie_titles(client, section_id):
    titles = []
    for item in get_all(client, section_id, TYPE_MOVIE):
        year = item.get("year")
        titles.append({
            "key": str(item.get("ratingKey")),
            "title": clean(f"{item.get('title')} ({year})" if year else item.get("title")),
            "added": as_int(item.get("addedAt")),
            "bytes": size_on_disk(item),
        })
    return titles


def show_titles(client, section_id):
    """One title per show, built from its episodes. A show's added date is its newest episode."""
    shows = {}
    for episode in get_all(client, section_id, TYPE_EPISODE):
        key = episode.get("grandparentRatingKey")
        if key in (None, ""):
            continue
        show = shows.setdefault(str(key), {
            "key": str(key), "title": clean(episode.get("grandparentTitle")),
            "added": 0, "bytes": 0, "episodes": 0,
        })
        show["added"] = max(show["added"], as_int(episode.get("addedAt")))
        show["bytes"] += size_on_disk(episode)
        show["episodes"] += 1
    return list(shows.values())


# ---------------------------------------------------------------- plays

class History:
    """Finished plays by every account: rating key -> newest finished play time.

    Episode plays are recorded under their show's rating key.
    """

    def __init__(self):
        self.last_finished = {}
        self.rows = 0
        self.oldest = None

    def saw(self, epoch):
        self.rows += 1
        if epoch > 0 and (self.oldest is None or epoch < self.oldest):
            self.oldest = epoch

    def finished(self, key, epoch):
        if key not in (None, "", "None"):
            key = str(key)
            self.last_finished[key] = max(self.last_finished.get(key, 0), epoch)

    @property
    def capped(self):
        return self.rows >= HISTORY_CAP


def plex_history(client):
    # Plex's history only holds plays that were finished or nearly finished, so every entry counts.
    history, start = History(), 0
    while history.rows < HISTORY_CAP:
        size = min(PLEX_HISTORY_PAGE_SIZE, HISTORY_CAP - history.rows)
        page = client.get("/status/sessions/history/all", {"sort": "viewedAt:desc"},
                          start=start, size=size)
        batch = page.get("Metadata", []) or []
        for view in batch:
            epoch = as_int(view.get("viewedAt"))
            history.saw(epoch)
            if view.get("type") == "movie":
                history.finished(view.get("ratingKey"), epoch)
            elif view.get("type") == "episode":
                # Plex history has no grandparentRatingKey, only "/library/metadata/<key>".
                history.finished(str(view.get("grandparentKey") or "").rsplit("/", 1)[-1], epoch)
        start += len(batch)
        if len(batch) < size:
            break
    return history


def tautulli_history(client):
    history = History()
    for media_type in ("movie", "episode"):
        start = 0
        while history.rows < HISTORY_CAP:
            size = min(TAUTULLI_PAGE_SIZE, HISTORY_CAP - history.rows)
            # grouping=1 merges a play that was paused and resumed later into one row.
            page = client.call("get_history", grouping=1, media_type=media_type,
                               order_column="date", order_dir="desc", start=start, length=size) or {}
            batch = page.get("data", []) or []
            for row in batch:
                if as_int(row.get("live")):
                    continue
                epoch = as_int(row.get("stopped") or row.get("date") or row.get("started"))
                history.saw(epoch)
                # Tautulli gives 1 for watched and 0, 0.25, 0.5 or 0.75 for partly watched.
                if as_float(row.get("watched_status")) < 1:
                    continue
                key = row.get("rating_key") if media_type == "movie" else row.get("grandparent_rating_key")
                history.finished(key, epoch)
            start += len(batch)
            if len(batch) < size:
                break
    return history


def read_history(config, args):
    """Returns (source, history, fallback_reason)."""
    fallback_reason = None
    if args.source in ("auto", "tautulli"):
        if config["tautulli"]:
            print("reading watch history from Tautulli", file=sys.stderr)
            try:
                try:
                    return "tautulli", tautulli_history(TautulliClient(*config["tautulli"])), None
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

    print("reading watch history from Plex", file=sys.stderr)
    try:
        return "plex", plex_history(PlexClient(*config["plex"])), fallback_reason
    except ReportError as exc:
        if "401" not in str(exc) and "403" not in str(exc):
            raise
        raise ReportError(
            "OWNER_ONLY: Plex only shares everyone's plays with the server owner's account. "
            "Connect with the owner's account, or set up Tautulli."
        ) from None


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
            raise ReportError("Only movie and TV libraries are checked for unwatched titles.")
    checked = [s for s in sections if s.get("type") in ("movie", "show")]
    skipped = [{"name": clean(s.get("title")), "type": s.get("type")}
               for s in sections if s.get("type") not in ("movie", "show")]
    return checked, skipped


def summarise(section, titles, history, cutoff, limit):
    library_bytes = sum(t["bytes"] for t in titles)
    listed = []
    for t in titles:
        last = history.last_finished.get(t["key"], 0)
        if 0 < t["added"] < cutoff and t["bytes"] > 0 and last < cutoff:
            listed.append(dict(t, last=last))
    listed.sort(key=lambda t: (-t["bytes"], t["title"].lower()))
    never = [t for t in listed if not t["last"]]
    unwatched_bytes = sum(t["bytes"] for t in listed)
    is_show = section.get("type") == "show"

    def entry(t):
        out = {"title": t["title"], "added": day(t["added"]), "gb": gb(t["bytes"]),
               "last_finished": day(t["last"])}
        if is_show:
            out["episodes"] = t["episodes"]
        return out

    return {
        "name": clean(section.get("title")),
        "type": section.get("type"),
        "items": len(titles),
        "library_gb": gb(library_bytes),
        "unwatched": len(listed),
        "unwatched_gb": gb(unwatched_bytes),
        "unwatched_pct": pct(unwatched_bytes, library_bytes),
        "never_finished": len(never),
        "never_finished_gb": gb(sum(t["bytes"] for t in never)),
        "titles": [entry(t) for t in listed[:limit]],
        # Kept for the totals; removed before printing.
        "_bytes": (library_bytes, unwatched_bytes, sum(t["bytes"] for t in never)),
    }


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

    library_titles = []
    for section in checked:
        print(f"reading library: {clean(section.get('title'))}", file=sys.stderr)
        read = show_titles if section.get("type") == "show" else movie_titles
        library_titles.append((section, read(client, section.get("key"))))

    source, history, fallback_reason = read_history(config, args)
    cutoff = months_before(now, args.months)
    libraries = [summarise(s, titles, history, cutoff, args.limit) for s, titles in library_titles]

    library_bytes = sum(lib["_bytes"][0] for lib in libraries)
    unwatched_bytes = sum(lib["_bytes"][1] for lib in libraries)
    never_bytes = sum(lib["_bytes"][2] for lib in libraries)
    totals = {
        "unwatched": sum(lib["unwatched"] for lib in libraries),
        "unwatched_gb": gb(unwatched_bytes),
        "library_gb": gb(library_bytes),
        "unwatched_pct": pct(unwatched_bytes, library_bytes),
        "never_finished": sum(lib["never_finished"] for lib in libraries),
        "never_finished_gb": gb(never_bytes),
    }
    for lib in libraries:
        del lib["_bytes"]

    return {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z", time.localtime(now)),
        "server": {"name": clean(root.get("friendlyName")), "version": root.get("version")},
        "months": args.months,
        "cutoff": day(cutoff),
        "source": source,
        "fallback_reason": fallback_reason,
        "history_since": day(history.oldest) if history.oldest else None,
        "history_capped": history.capped,
        "libraries": libraries,
        "skipped_libraries": skipped,
        "totals": totals,
        "media_deletion_allowed": media_deletion_allowed(lambda: client.get("/:/prefs")),
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
        description="Read-only list of Plex titles nobody has finished in a while (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connections")
    parser.add_argument("--months", type=int, default=6,
                        help="added more than this many months ago and not finished since (default 6)")
    parser.add_argument("--library", action="append", help="limit to a library by name (repeatable)")
    parser.add_argument("--limit", type=int, default=25, help="titles listed per library")
    parser.add_argument("--source", choices=["auto", "tautulli", "plex"], default="auto",
                        help="where to read plays from (default: Tautulli if set up, else Plex)")
    args = parser.parse_args()
    args.months = max(1, min(args.months, 120))
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
