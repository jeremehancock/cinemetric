#!/usr/bin/env python3
"""Cinemetric episode-gaps: read-only list of gaps in the TV episodes on a Plex server.

Finds episode numbers missing between the ones on the server, seasons that start late, seasons
missing between others, and episodes whose files Plex can't find. Uses only what the server has: it
never asks an online service how many episodes a show should have, so episodes after the last one on
the server can't be seen. Uses only the Python standard library. Prints one JSON document to stdout;
errors go to stderr.

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

VERSION = "0.21.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
LIBRARY_PAGE_SIZE = 500

# The only Plex server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
]

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
SHOW_TYPE = 2
EPISODE_TYPE = 4
# Seasons or episodes numbered above this are numbered by date (season 2023, episode 20231005).
HIGHEST_NUMBER_CHECKED = 999
# A file holding several episodes: "S01E01-E02", "S01E01-02", "S01E01E02", "S01E01-E02-E03".
# A number running into p or i is a resolution ("S01E01-1080p"), not an episode.
EPISODE_RANGE = re.compile(r"[Ss](\d{1,4})[Ee](\d{1,3})((?:-?[Ee]\d{1,3}|-\d{1,3})+)(?![\dpPiI])")
LIMITS = (
    "Only gaps between the episodes on the server can be found. Episodes after the last one on the "
    "server, and seasons after the last season, can't be seen, because Cinemetric doesn't ask any "
    "online service how many episodes a show should have."
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
            "X-Plex-Client-Identifier": "cinemetric-episode-gaps",
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
        if not any(s.get("type") == "show" for s in sections):
            raise ReportError("Only TV libraries are checked for episode gaps.")
    checked = [s for s in sections if s.get("type") == "show"]
    skipped = [{"name": clean(s.get("title")), "type": s.get("type")}
               for s in sections if s.get("type") != "show"]
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


# ---------------------------------------------------------------- gaps

def file_numbers(episode, season, number):
    """Episode numbers a multi-episode file covers, from its file name. Paths are never output."""
    found = set()
    for media in episode.get("Media", []) or []:
        if media.get("deletedAt"):
            continue
        for part in media.get("Part", []) or []:
            name = re.split(r"[\\/]", str(part.get("file") or ""))[-1]
            match = EPISODE_RANGE.search(name)
            if not match or int(match.group(1)) != season:
                continue
            numbers = [int(match.group(2))] + [int(n) for n in re.findall(r"\d+", match.group(3))]
            if numbers[0] == number and numbers == sorted(numbers):
                found.update(range(numbers[0], numbers[-1] + 1))
    return found


def ranges(numbers):
    """[3, 5, 6, 7] -> [[3, 3], [5, 7]]."""
    result = []
    for n in sorted(numbers):
        if result and n == result[-1][1] + 1:
            result[-1][1] = n
        else:
            result.append([n, n])
    return result


def numbered(value):
    return as_int(value, None) if value is not None and str(value).strip() != "" else None


def check_show(title, year, episodes):
    """Gaps for one show. Returns a dict with the show's counts and details."""
    seasons, unnumbered = {}, 0
    for episode in episodes:
        season, number = numbered(episode.get("parentIndex")), numbered(episode.get("index"))
        if season is None or number is None:
            unnumbered += 1
            continue
        entry = seasons.setdefault(season, {"there": set(), "unavailable": set()})
        media = episode.get("Media", []) or []
        if any(not m.get("deletedAt") for m in media):
            entry["there"].add(number)
            entry["there"].update(file_numbers(episode, season, number))
        else:
            entry["unavailable"].add(number)

    def in_range(n):
        return 1 <= n <= HIGHEST_NUMBER_CHECKED

    result = {"title": title, "year": year, "first_season": None, "missing_seasons": [],
              "missing_episodes": 0, "unavailable_episodes": 0, "unnumbered": unnumbered,
              "seasons": [], "seasons_not_checked": 0}
    season_numbers = sorted(s for s in seasons if in_range(s))
    if season_numbers:
        result["first_season"] = season_numbers[0]
        result["missing_seasons"] = [s for s in range(season_numbers[0], season_numbers[-1] + 1)
                                     if s not in seasons]
    previous_highest = None
    for season in sorted(seasons):
        if season == 0:
            continue
        entry = seasons[season]
        unavailable = entry["unavailable"] - entry["there"]
        numbers = entry["there"] | unavailable
        if not in_range(season) or max(numbers) > HIGHEST_NUMBER_CHECKED:
            result["seasons_not_checked"] += 1
            continue
        lowest, highest = min(numbers), max(numbers)
        continues = lowest > 1 and previous_highest is not None and lowest == previous_highest + 1
        missing = [n for n in range(lowest if continues else 1, highest + 1) if n not in numbers]
        previous_highest = highest
        result["missing_episodes"] += len(missing)
        result["unavailable_episodes"] += len(unavailable)
        if missing or unavailable or continues:
            result["seasons"].append({
                "season": season, "episodes": len(entry["there"]), "highest": highest,
                "missing": ranges(missing), "unavailable": sorted(unavailable),
                "continues_numbering": continues,
            })
    result["has_gaps"] = bool(result["missing_episodes"] or result["unavailable_episodes"]
                              or result["missing_seasons"])
    return result


def check_library(client, section, show_filter, limit):
    shows = {str(s.get("ratingKey")): s for s in get_all(client, section.get("key"), SHOW_TYPE)}
    grouped = {}
    for episode in get_all(client, section.get("key"), EPISODE_TYPE):
        key = str(episode.get("grandparentRatingKey") or episode.get("grandparentTitle") or "")
        grouped.setdefault(key, []).append(episode)

    counts = {"shows": 0, "episodes": 0, "shows_with_gaps": 0, "missing_episodes": 0,
              "unavailable_episodes": 0, "missing_seasons": 0, "shows_starting_later": 0,
              "seasons_not_checked": 0, "unnumbered": 0}
    with_gaps = []
    for key, episodes in grouped.items():
        show = shows.get(key, {})
        title = clean(show.get("title") or episodes[0].get("grandparentTitle"))
        if show_filter and show_filter.lower() not in title.lower():
            continue
        result = check_show(title, numbered(show.get("year")), episodes)
        counts["shows"] += 1
        counts["episodes"] += len(episodes)
        counts["missing_episodes"] += result["missing_episodes"]
        counts["unavailable_episodes"] += result["unavailable_episodes"]
        counts["missing_seasons"] += len(result["missing_seasons"])
        counts["shows_starting_later"] += (result["first_season"] or 1) > 1
        counts["seasons_not_checked"] += result.pop("seasons_not_checked")
        counts["unnumbered"] += result["unnumbered"]
        if result.pop("has_gaps"):
            counts["shows_with_gaps"] += 1
            with_gaps.append(result)

    with_gaps.sort(key=lambda s: (-(s["missing_episodes"] + s["unavailable_episodes"]),
                                  -len(s["missing_seasons"]), s["title"].lower()))
    return dict({"name": clean(section.get("title"))}, **counts,
                listed=with_gaps[:limit], more_shows=max(0, len(with_gaps) - limit))


# ---------------------------------------------------------------- report

TOTAL_FIELDS = ("shows", "episodes", "shows_with_gaps", "missing_episodes", "unavailable_episodes",
                "missing_seasons", "shows_starting_later")


def build_report(config, args, now=None):
    now = time.time() if now is None else now
    client = need_plex(config)
    root = client.get("/")
    sections = client.get("/library/sections").get("Directory", []) or []
    checked, skipped = choose_sections(sections, args.library)
    show_filter = (args.show or "").strip() or None
    libraries = [check_library(client, s, show_filter, args.limit) for s in checked]
    return {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
        "server": {"name": clean(root.get("friendlyName")), "version": clean(root.get("version"))},
        "show_filter": clean(show_filter) if show_filter else None,
        "limits": LIMITS,
        "libraries": libraries,
        "skipped_libraries": skipped,
        "totals": {field: sum(lib[field] for lib in libraries) for field in TOTAL_FIELDS},
    }


def check(config):
    root = need_plex(config).get("/")
    return {"ok": True, "plex": {"server": clean(root.get("friendlyName")), "version": root.get("version")}}


def main():
    parser = argparse.ArgumentParser(
        description="Read-only list of gaps in the TV episodes on your Plex server (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connection")
    parser.add_argument("--library", action="append", help="limit to a library by name (repeatable)")
    parser.add_argument("--show", help="only shows whose title contains this text")
    parser.add_argument("--limit", type=int, default=25, help="shows listed per library (default 25)")
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
