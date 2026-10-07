#!/usr/bin/env python3
"""Cinemetric what-to-watch: read-only shortlist of titles from the user's own Plex library.

Filters the movie and TV libraries by genre, length, year, rating, content rating and the signed-in
account's watched state, or lists what that account is partway through. Uses only the Python
standard library. Prints one JSON document to stdout; errors go to stderr.

Safety rules: see openspec/specs/security/spec.md in the Cinemetric repository.
"""

import argparse
import ipaddress
import json
import os
import random
import re
import ssl
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.24.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
LIBRARY_PAGE_SIZE = 500

# The only Plex server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
    re.compile(r"^/library/sections/\d+/genre$"),
    re.compile(r"^/library/onDeck$"),
]

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
TYPE_NUMBERS = {"movie": 1, "show": 2}


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
            "X-Plex-Client-Identifier": "cinemetric-what-to-watch",
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


def as_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def day(epoch):
    epoch = as_int(epoch)
    return time.strftime("%Y-%m-%d", time.localtime(epoch)) if epoch > 0 else None


def minutes(duration_ms):
    """Plex durations are in milliseconds. Unknown or zero becomes None."""
    ms = as_int(duration_ms)
    return round(ms / 60000) if ms > 0 else None


def shuffle(items):
    """Random order, so asking again gives different titles. Tests replace this."""
    random.shuffle(items)


# ---------------------------------------------------------------- options

def parse_decade(text):
    match = re.fullmatch(r"(\d{3})0s?", str(text).strip().lower())
    if not match:
        raise ReportError("--decade takes a value like 1990s.")
    start = int(match.group(1)) * 10
    return start, start + 9


def check_options(args):
    """Stop with a clear message for option values that can't be understood."""
    if args.continue_watching:
        extra = [name for name, value in (
            ("--genre", args.genre), ("--min-minutes", args.min_minutes),
            ("--max-minutes", args.max_minutes), ("--decade", args.decade),
            ("--year-from", args.year_from), ("--year-to", args.year_to),
            ("--min-rating", args.min_rating), ("--content-rating", args.content_rating),
            ("--unwatched", args.unwatched), ("--sort", args.sort),
        ) if value]
        if extra:
            raise ReportError(
                f"--continue only works with --library, --type and --limit (also given: "
                f"{', '.join(extra)}).")
        return
    if args.decade and (args.year_from is not None or args.year_to is not None):
        raise ReportError("Use --decade or --year-from/--year-to, not both.")
    if args.decade:
        args.year_from, args.year_to = parse_decade(args.decade)
    if args.year_from is not None and args.year_to is not None and args.year_from > args.year_to:
        raise ReportError("--year-from is after --year-to.")
    if args.min_rating is not None and not 0 <= args.min_rating <= 10:
        raise ReportError("--min-rating takes a number from 0 to 10.")
    for name, value in (("--min-minutes", args.min_minutes), ("--max-minutes", args.max_minutes)):
        if value is not None and value < 0:
            raise ReportError(f"{name} can't be negative.")


# ---------------------------------------------------------------- library

def need_plex(config):
    if not config["plex"]:
        raise ReportError(
            "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN)."
        )
    return PlexClient(*config["plex"])


def choose_sections(sections, wanted, kind):
    if wanted:
        names = {name.lower() for name in wanted}
        sections = [s for s in sections if str(s.get("title", "")).lower() in names]
        if not sections:
            raise ReportError("No library matched --library. Run without it to see all names.")
        if not any(s.get("type") in TYPE_NUMBERS for s in sections):
            raise ReportError("Only movie and TV libraries are checked for something to watch.")
    checked = [s for s in sections if s.get("type") in TYPE_NUMBERS and (not kind or s.get("type") == kind)]
    skipped = [{"name": clean(s.get("title")), "type": s.get("type")}
               for s in sections if s.get("type") not in TYPE_NUMBERS]
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


def movie_state(item):
    if as_int(item.get("viewCount")) >= 1:
        return "watched"
    if as_int(item.get("viewOffset")) > 0:
        return "in_progress"
    return "unwatched"


def show_state(item):
    seen, total = as_int(item.get("viewedLeafCount")), as_int(item.get("leafCount"))
    if seen <= 0:
        return "unwatched"
    return "watched" if seen >= total else "started"


def entry(section, item):
    """One title as reported, plus private fields (starting with _) used for matching and sorting."""
    kind = section.get("type")
    year = as_int(item.get("year")) or None
    title = item.get("title")
    rating, audience = as_float(item.get("rating")), as_float(item.get("audienceRating"))
    result = {
        "type": kind,
        "title": clean(f"{title} ({year})" if kind == "movie" and year else title),
        "year": year,
        "libraries": [clean(section.get("title"))],
        "genres": [clean(g.get("tag")) for g in item.get("Genre", []) or [] if g.get("tag")],
        "critic_rating": rating,
        "audience_rating": audience,
        "content_rating": clean(item.get("contentRating")) or None,
        "summary": clean(item.get("summary")) or None,
        "added": day(item.get("addedAt")),
    }
    if kind == "movie":
        result.update(watched=movie_state(item), minutes=minutes(item.get("duration")))
        result["_minutes"] = result["minutes"]
    else:
        result.update(watched=show_state(item), episode_minutes=minutes(item.get("duration")),
                      seasons=as_int(item.get("childCount")) or None,
                      episodes=as_int(item.get("leafCount")),
                      episodes_watched=as_int(item.get("viewedLeafCount")))
        result["_minutes"] = result["episode_minutes"]
    result["_copies"] = {(str(section.get("key")), str(item.get("ratingKey")))}
    result["_guid"] = item.get("guid") or None
    result["_added"] = as_int(item.get("addedAt"))
    result["_rating"] = audience if audience is not None else rating
    return result


WATCHED_ORDER = {"unwatched": 0, "in_progress": 1, "started": 1, "watched": 2}


def merge(entries):
    """The same movie or show in several libraries (same guid) becomes one entry."""
    merged, by_guid = [], {}
    for item in entries:
        key = (item["type"], item["_guid"]) if item["_guid"] else None
        first = by_guid.get(key) if key else None
        if not first:
            merged.append(item)
            if key:
                by_guid[key] = item
            continue
        for name in item["libraries"]:
            if name not in first["libraries"]:
                first["libraries"].append(name)
        first["_copies"] |= item["_copies"]
        first["_added"] = max(first["_added"], item["_added"])
        first["added"] = day(first["_added"])
        if item["type"] == "movie":
            if WATCHED_ORDER[item["watched"]] > WATCHED_ORDER[first["watched"]]:
                first["watched"] = item["watched"]
        elif item["episodes_watched"] > first["episodes_watched"]:
            for field in ("watched", "episodes", "episodes_watched", "seasons"):
                first[field] = item[field]
    return merged


def genre_matches(client, section, genre_list, wanted):
    """(section key, rating key) of every title Plex says has one of the wanted genres.

    Library listings carry at most two genres per title, so Plex's own genre filter is used.
    """
    keys = set()
    by_name = {str(g.get("title", "")).lower(): g.get("key") for g in genre_list}
    for name in wanted:
        genre_key = by_name.get(name.lower())
        if genre_key in (None, ""):
            continue
        for item in get_all(client, section.get("key"), TYPE_NUMBERS[section.get("type")],
                            {"genre": genre_key}):
            keys.add((str(section.get("key")), str(item.get("ratingKey"))))
    return keys


def passes(item, args, genre_keys):
    if args.genre and not (item["_copies"] & genre_keys):
        return False
    if args.min_minutes is not None or args.max_minutes is not None:
        length = item["_minutes"]
        if length is None:
            return False
        if args.min_minutes is not None and length < args.min_minutes:
            return False
        if args.max_minutes is not None and length > args.max_minutes:
            return False
    if args.year_from is not None or args.year_to is not None:
        year = item["year"]
        if year is None:
            return False
        if args.year_from is not None and year < args.year_from:
            return False
        if args.year_to is not None and year > args.year_to:
            return False
    if args.min_rating is not None and (item["_rating"] is None or item["_rating"] < args.min_rating):
        return False
    if args.content_rating:
        wanted = {name.lower() for name in args.content_rating}
        if (item["content_rating"] or "").lower() not in wanted:
            return False
    if args.unwatched and item["watched"] not in ("unwatched", "in_progress"):
        return False
    return True


def order(items, sort):
    items.sort(key=lambda t: t["title"].lower())
    if sort == "random":
        shuffle(items)
        return items
    field = {"rating": "_rating", "added": "_added", "year": "year"}[sort]
    # Stable sort: equal values keep title order. Missing values go last.
    items.sort(key=lambda t: (t[field] is not None, t[field] or 0), reverse=True)
    return items


def public(item):
    return {k: v for k, v in item.items() if not k.startswith("_")}


def applied_filters(args):
    return {
        "type": args.type, "library": args.library, "genre": args.genre,
        "min_minutes": args.min_minutes, "max_minutes": args.max_minutes,
        "year_from": args.year_from, "year_to": args.year_to, "min_rating": args.min_rating,
        "content_rating": args.content_rating, "unwatched": bool(args.unwatched),
        "sort": args.sort or "random", "limit": args.limit,
    }


def pick(client, checked, args):
    entries, genres, genre_keys = [], {}, set()
    for section in checked:
        print(f"reading library: {clean(section.get('title'))}", file=sys.stderr)
        number = TYPE_NUMBERS[section.get("type")]
        genre_list = client.get(f"/library/sections/{section.get('key')}/genre",
                                {"type": number}).get("Directory", []) or []
        for g in genre_list:
            name = clean(g.get("title"))
            if name:
                genres.setdefault(name.lower(), name)
        if args.genre:
            genre_keys |= genre_matches(client, section, genre_list, args.genre)
        entries.extend(entry(section, item) for item in get_all(client, section.get("key"), number))

    entries = merge(entries)
    ratings = sorted({t["content_rating"] for t in entries if t["content_rating"]}, key=lambda r: (r.lower(), r))
    matches = order([t for t in entries if passes(t, args, genre_keys)], args.sort or "random")
    return {
        "matches": len(matches),
        "titles": [public(t) for t in matches[:args.limit]],
        "genres_available": sorted(genres.values(), key=str.lower),
        "content_ratings_available": ratings,
    }


def continue_entry(item):
    kind = item.get("type")
    duration, offset = as_int(item.get("duration")), as_int(item.get("viewOffset"))
    if kind == "episode":
        season, number = item.get("parentIndex"), item.get("index")
        result = {
            "type": "episode",
            "title": clean(item.get("grandparentTitle")),
            "library": clean(item.get("librarySectionTitle")),
            "episode": (f"S{as_int(season):02d}E{as_int(number):02d}"
                        if season is not None and number is not None else None),
            "episode_title": clean(item.get("title")) or None,
        }
    else:
        year = as_int(item.get("year")) or None
        title = item.get("title")
        result = {
            "type": "movie",
            "title": clean(f"{title} ({year})" if year else title),
            "library": clean(item.get("librarySectionTitle")),
        }
    result["progress_pct"] = round(100 * offset / duration, 1) if duration and offset > 0 else 0.0
    result["minutes_left"] = round(max(duration - offset, 0) / 60000) if duration else None
    result["last_viewed"] = day(item.get("lastViewedAt"))
    return result


def continue_watching(client, checked, args):
    keys = {str(s.get("key")) for s in checked}
    items = [item for item in client.get("/library/onDeck").get("Metadata", []) or []
             if str(item.get("librarySectionID")) in keys and item.get("type") in ("movie", "episode")]
    return {"continue_watching": [continue_entry(item) for item in items][:args.limit]}


def build_report(config, args, now=None):
    now = time.time() if now is None else now
    check_options(args)
    client = need_plex(config)
    root = client.get("/")
    sections = client.get("/library/sections").get("Directory", []) or []
    checked, skipped = choose_sections(sections, args.library, args.type)

    report = {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
        "server": {"name": clean(root.get("friendlyName")), "version": clean(root.get("version"))},
        "mode": "continue" if args.continue_watching else "pick",
        "filters": applied_filters(args),
        "libraries_checked": [clean(s.get("title")) for s in checked],
        "skipped_libraries": skipped,
    }
    if args.continue_watching:
        report.update(continue_watching(client, checked, args))
    else:
        report.update(pick(client, checked, args))
    return report


def check(config):
    root = need_plex(config).get("/")
    return {"ok": True, "plex": {"server": clean(root.get("friendlyName")), "version": root.get("version")}}


def main():
    parser = argparse.ArgumentParser(
        description="Read-only shortlist of titles to watch from your own Plex library (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connection")
    parser.add_argument("--type", choices=["movie", "show"], help="only movies or only shows")
    parser.add_argument("--library", action="append", help="limit to a library by name (repeatable)")
    parser.add_argument("--genre", action="append", help="has this genre (repeatable: any of them)")
    parser.add_argument("--min-minutes", type=int, help="runtime (or episode length) at least this")
    parser.add_argument("--max-minutes", type=int, help="runtime (or episode length) at most this")
    parser.add_argument("--decade", help="released in this decade, like 1990s")
    parser.add_argument("--year-from", type=int, help="released in or after this year")
    parser.add_argument("--year-to", type=int, help="released in or before this year")
    parser.add_argument("--min-rating", type=float, help="audience (else critic) rating, 0 to 10")
    parser.add_argument("--content-rating", action="append", help="such as PG-13 (repeatable)")
    parser.add_argument("--unwatched", action="store_true", help="not watched by the signed-in account")
    parser.add_argument("--continue", dest="continue_watching", action="store_true",
                        help="what's in progress and next up, instead of a shortlist")
    parser.add_argument("--sort", choices=["random", "rating", "added", "year"],
                        help="order of matches (default random)")
    parser.add_argument("--limit", type=int, default=20, help="titles returned (default 20)")
    args = parser.parse_args()
    args.limit = max(1, min(args.limit, 100))

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
