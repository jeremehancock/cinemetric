#!/usr/bin/env python3
"""Cinemetric collections-and-playlists: read-only report on a Plex server's collections and playlists.

Lists the collections in each movie and TV library with how many titles each holds and the storage
they use, collections with one title or none, how many titles are in no collection, and the
signed-in account's playlists, including items whose files Plex can no longer find. Plex keeps
playlists per account, so other people's playlists can't be seen. Uses only the Python standard
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

VERSION = "0.31.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
LIBRARY_PAGE_SIZE = 500
DEFAULT_LIMIT = 50
MAX_LIMIT = 500
MAX_EXAMPLES = 15

# The only Plex server paths this script may request. All of them are read with GET.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
    re.compile(r"^/library/sections/\d+/collections$"),
    re.compile(r"^/library/collections/\d+/children$"),
    re.compile(r"^/playlists$"),
    re.compile(r"^/playlists/\d+/items$"),
    re.compile(r"^/:/prefs$"),
]

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
TYPE_MOVIE, TYPE_SHOW, TYPE_EPISODE = 1, 2, 4
CHECKED_TYPES = ("movie", "show")
PLAYLIST_KINDS = ("video", "audio", "photo")
PLAYLISTS_SCOPE = "signed_in_account"


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
            "X-Plex-Client-Identifier": "cinemetric-collections-and-playlists",
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


def gb(size):
    return round(size / 1e9, 1)


def year_of(item):
    return as_int(item.get("year")) or None


# ---------------------------------------------------------------- reading

def need_plex(config):
    if not config["plex"]:
        raise ReportError(
            "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN)."
        )
    return PlexClient(*config["plex"])


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


def get_pages(client, path):
    """Every entry of a collection's or playlist's listing, fetched in pages. These listings don't
    always give totalSize, so a short page also means the end."""
    items, start = [], 0
    while True:
        page = client.get(path, start=start, size=LIBRARY_PAGE_SIZE)
        batch = page.get("Metadata", []) or []
        items.extend(batch)
        start += len(batch)
        total = page.get("totalSize")
        if len(batch) < LIBRARY_PAGE_SIZE or (total is not None and start >= as_int(total)):
            return items


def choose_sections(sections, wanted):
    if wanted:
        names = {name.lower() for name in wanted}
        sections = [s for s in sections if str(s.get("title", "")).lower() in names]
        if not any(s.get("type") in CHECKED_TYPES for s in sections):
            raise ReportError("No movie or TV library matched --library. Run without it to see all "
                              "names; collections are only read from movie and TV libraries.")
    checked = [s for s in sections if s.get("type") in CHECKED_TYPES]
    skipped = [{"name": clean(s.get("title")), "type": clean(s.get("type"))}
               for s in sections if s.get("type") not in CHECKED_TYPES]
    return checked, skipped


def media_size(item):
    """Bytes used by every part of every media version of one item."""
    return sum(as_int(part.get("size")) for media in item.get("Media", []) or []
               for part in media.get("Part", []) or [])


def is_unavailable(item):
    """Plex can't find the item's file: every media version is marked deleted (as library-report
    counts it). One version left means the item still plays."""
    media = item.get("Media", []) or []
    return bool(media) and all(m.get("deletedAt") for m in media)


# ---------------------------------------------------------------- collections

def library_titles(client, section):
    """Returns (sizes, owner, titles): bytes per rating key (movies, shows, seasons and episodes),
    the movie or show each rating key belongs to, and the rating keys of the library's movies or
    shows."""
    sizes, owner = {}, {}
    if section.get("type") == "movie":
        movies = get_all(client, section["key"], TYPE_MOVIE)
        for movie in movies:
            key = str(movie.get("ratingKey"))
            sizes[key] = media_size(movie)
            owner[key] = key
        return sizes, owner, [str(m.get("ratingKey")) for m in movies]
    shows = get_all(client, section["key"], TYPE_SHOW)
    for show in shows:
        key = str(show.get("ratingKey"))
        sizes[key] = 0
        owner[key] = key
    for episode in get_all(client, section["key"], TYPE_EPISODE):
        key, size = str(episode.get("ratingKey")), media_size(episode)
        show = str(episode.get("grandparentRatingKey") or "")
        season = str(episode.get("parentRatingKey") or "")
        sizes[key] = size
        if show:
            owner[key] = show
            sizes[show] = sizes.get(show, 0) + size
            owner.setdefault(show, show)
        if season:
            sizes[season] = sizes.get(season, 0) + size
            if show:
                owner[season] = show
    return sizes, owner, [str(s.get("ratingKey")) for s in shows]


def read_library(client, section, unavailable):
    """One library's collections and its titles-in-a-collection counts."""
    name = clean(section.get("title"))
    entry = {"name": name, "type": clean(section.get("type")), "collections": None, "titles": None,
             "in_a_collection": None, "in_no_collection": None, "in_no_collection_percent": None}
    try:
        sizes, owner, titles = library_titles(client, section)
        listing = get_pages(client, f"/library/sections/{section['key']}/collections")
    except ReportError as exc:
        unavailable.append({"part": f"collections in {name}", "reason": str(exc)})
        return entry, []

    collections, covered = [], set()
    for col in listing:
        title = clean(col.get("title"))
        found = {"title": title, "library": name, "smart": as_bool(col.get("smart")),
                 "titles": as_int(col.get("childCount")), "storage_bytes": None, "storage_gb": None,
                 "rating_key": clean(col.get("ratingKey")), "only_title": None}
        try:
            children = get_pages(client, f"/library/collections/{as_int(col.get('ratingKey'))}/children")
        except ReportError as exc:
            unavailable.append({"part": f"collection {title} in {name}", "reason": str(exc)})
            collections.append(found)
            continue
        keys = {str(child.get("ratingKey")) for child in children}
        found["titles"] = len(children)
        found["storage_bytes"] = sum(sizes.get(key, 0) for key in keys)
        found["storage_gb"] = gb(found["storage_bytes"])
        if len(children) == 1:
            found["only_title"] = {"title": clean(children[0].get("title")), "year": year_of(children[0])}
        covered.update(owner[key] for key in keys if key in owner)
        collections.append(found)

    in_one = len(covered.intersection(titles))
    entry.update({
        "collections": len(collections),
        "titles": len(titles),
        "in_a_collection": in_one,
        "in_no_collection": len(titles) - in_one,
        "in_no_collection_percent": round(100 * (len(titles) - in_one) / len(titles), 1) if titles else None,
    })
    return entry, collections


def read_collections(client, sections, unavailable):
    libraries, collections = [], []
    for section in sections:
        entry, found = read_library(client, section, unavailable)
        libraries.append(entry)
        collections.extend(found)
    return libraries, collections


# ---------------------------------------------------------------- playlists

def example(item):
    found = {"title": clean(item.get("title")), "year": year_of(item)}
    if item.get("type") == "episode":
        found.update({"show_title": clean(item.get("grandparentTitle")),
                      "season": as_int(item.get("parentIndex"), None),
                      "episode": as_int(item.get("index"), None)})
    elif item.get("type") == "track":
        found["artist"] = clean(item.get("grandparentTitle"))
    return found


def read_playlist(client, playlist, unavailable):
    title = clean(playlist.get("title"))
    kind = playlist.get("playlistType")
    found = {"title": title, "kind": kind if kind in PLAYLIST_KINDS else clean(kind),
             "smart": as_bool(playlist.get("smart")),
             "items": None, "duration_ms": as_int(playlist.get("duration")) or None,
             "storage_bytes": None, "storage_gb": None, "unavailable_items": None, "examples": []}
    try:
        items = get_pages(client, f"/playlists/{as_int(playlist.get('ratingKey'))}/items")
    except ReportError as exc:
        unavailable.append({"part": f"playlist {title}", "reason": str(exc)})
        return found
    sizes = {str(item.get("ratingKey")): media_size(item) for item in items}
    missing = [item for item in items if is_unavailable(item)]
    # A smart playlist's own duration and leafCount can be out of date, so count what it returns.
    duration = sum(as_int(item.get("duration")) for item in items)
    found.update({
        "items": len(items),
        "duration_ms": duration or found["duration_ms"],
        "storage_bytes": sum(sizes.values()),
        "storage_gb": gb(sum(sizes.values())),
        "unavailable_items": len(missing),
        "examples": [example(item) for item in missing[:MAX_EXAMPLES]],
    })
    return found


def read_playlists(client, unavailable):
    try:
        listing = client.get("/playlists").get("Metadata", []) or []
    except ReportError as exc:
        unavailable.append({"part": "playlists", "reason": f"Playlists couldn't be read: {exc}"})
        return None
    return [read_playlist(client, playlist, unavailable) for playlist in listing]


# ---------------------------------------------------------------- report

def capped(items, limit):
    return items[:limit], max(0, len(items) - limit)


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
    unavailable = []
    limit = args.limit

    libraries = skipped = collections = single = empty = None
    more_collections = more_single = more_empty = None
    if args.only != "playlists":
        sections = client.get("/library/sections").get("Directory", []) or []
        checked, skipped = choose_sections(sections, args.library)
        libraries, found = read_collections(client, checked, unavailable)
        found.sort(key=lambda c: (-c["titles"], -(c["storage_bytes"] or 0), c["title"].lower()))
        by_place = lambda c: (c["library"].lower(), c["title"].lower())
        singles = sorted((c for c in found if c["titles"] == 1), key=by_place)
        empties = sorted((c for c in found if c["titles"] == 0), key=by_place)
        collections, more_collections = capped(found, limit)
        single, more_single = capped([
            {"title": c["title"], "library": c["library"], "smart": c["smart"],
             "item_title": (c["only_title"] or {}).get("title"), "item_year": (c["only_title"] or {}).get("year")}
            for c in singles], limit)
        empty, more_empty = capped([{"title": c["title"], "library": c["library"], "smart": c["smart"]}
                                    for c in empties], limit)
        for c in collections:
            del c["only_title"]

    playlists = with_missing = None
    more_playlists = more_with_missing = None
    all_playlists = None
    if args.only != "collections":
        all_playlists = read_playlists(client, unavailable)
        if all_playlists is not None:
            ordered = sorted(all_playlists, key=lambda p: (-(p["items"] or 0), -(p["storage_bytes"] or 0),
                                                           p["title"].lower()))
            missing = sorted((p for p in all_playlists if (p["unavailable_items"] or 0) > 0),
                             key=lambda p: (-p["unavailable_items"], p["title"].lower()))
            with_missing, more_with_missing = capped([
                {key: p[key] for key in ("title", "kind", "items", "unavailable_items", "examples")}
                for p in missing], limit)
            playlists, more_playlists = capped([{k: v for k, v in p.items() if k != "examples"}
                                                for p in ordered], limit)

    read_collections_part = collections is not None
    totals = {
        "collections": len(found) if read_collections_part else None,
        "smart_collections": sum(1 for c in found if c["smart"]) if read_collections_part else None,
        "single_title_collections": len(singles) if read_collections_part else None,
        "empty_collections": len(empties) if read_collections_part else None,
        "playlists": len(all_playlists) if all_playlists is not None else None,
        "smart_playlists": sum(1 for p in all_playlists if p["smart"]) if all_playlists is not None else None,
        "playlists_with_missing_items": (sum(1 for p in all_playlists if (p["unavailable_items"] or 0) > 0)
                                         if all_playlists is not None else None),
        "unavailable_playlist_items": (sum(p["unavailable_items"] or 0 for p in all_playlists)
                                       if all_playlists is not None else None),
    }
    return {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
        "server": {"name": clean(root.get("friendlyName")), "version": clean(root.get("version"))},
        "libraries": libraries,
        "skipped_libraries": skipped,
        "collections": collections,
        "more_collections": more_collections,
        "single_title_collections": single,
        "more_single_title": more_single,
        "empty_collections": empty,
        "more_empty": more_empty,
        "playlists_scope": PLAYLISTS_SCOPE,
        "playlists": playlists,
        "more_playlists": more_playlists,
        "playlists_with_missing_items": with_missing,
        "more_playlists_with_missing_items": more_with_missing,
        "unavailable": unavailable,
        "totals": totals,
        "media_deletion_allowed": media_deletion_allowed(lambda: client.get("/:/prefs")),
    }


def check(config):
    root = need_plex(config).get("/")
    return {"ok": True, "plex": {"server": clean(root.get("friendlyName")), "version": root.get("version")}}


def main():
    parser = argparse.ArgumentParser(
        description="Read-only report on the collections and playlists on your Plex server (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connection")
    parser.add_argument("--library", action="append",
                        help="read collections from this library only (repeatable); playlists aren't filtered")
    parser.add_argument("--only", choices=("collections", "playlists"), help="report on just one of the two")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"entries per list (default {DEFAULT_LIMIT})")
    args = parser.parse_args()
    args.limit = max(0, min(args.limit, MAX_LIMIT))

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
