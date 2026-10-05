#!/usr/bin/env python3
"""Cinemetric library report: read-only summary of a Plex Media Server's libraries.

Talks to the server over its normal HTTP API using a token. Uses only the Python
standard library. Prints one JSON document to stdout; errors go to stderr.

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

VERSION = "0.12.0"
PAGE_SIZE = 500
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120

# The only server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
]

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
TYPE_MOVIE, TYPE_SHOW, TYPE_SEASON, TYPE_EPISODE = 1, 2, 3, 4
TYPE_ARTIST, TYPE_ALBUM, TYPE_TRACK = 8, 9, 10
TYPE_PHOTO = 13


class ReportError(Exception):
    """An error with a message that is safe to show the user."""


# ---------------------------------------------------------------- config

def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "cinemetric", "config.json")


def load_config():
    """Return (url, token, verify_tls). Environment variables win over the config file."""
    url = os.environ.get("PLEX_URL")
    token = os.environ.get("PLEX_TOKEN")
    verify_tls = True
    path = config_path()

    if not (url and token) and os.path.exists(path):
        info = os.stat(path)
        if os.name == "posix":
            if info.st_uid != os.getuid():
                raise ReportError(f"Refusing to read {path}: it is owned by another user.")
            if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
                raise ReportError(
                    f"Refusing to read {path}: other users can access it. "
                    f"Fix with: chmod 600 {path}"
                )
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as exc:
            raise ReportError(f"Could not read {path}: {exc.__class__.__name__}") from None
        if not isinstance(data, dict):
            raise ReportError(f"{path} must contain a JSON object.")
        url = url or data.get("plex_url")
        token = token or data.get("plex_token")
        verify_tls = data.get("verify_tls", True) is not False

    if not url or not token:
        raise ReportError(
            "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN)."
        )
    return validate_url(url), str(token).strip(), verify_tls


def validate_url(url):
    parts = urllib.parse.urlsplit(str(url).strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ReportError("plex_url must look like http://host:32400 or https://host")
    if parts.username or parts.password:
        raise ReportError("plex_url must not contain a username or password.")
    if parts.query or parts.fragment:
        raise ReportError("plex_url must not contain ? or # parts.")
    if parts.scheme == "http" and not looks_local(parts.hostname):
        print(
            "warning: plex_url uses plain http to a non-local address, so your token travels "
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
            "redirects so your token stays with your server. Use the final address as plex_url."
        )


class PlexClient:
    def __init__(self, base_url, token, verify_tls):
        self.base_url = base_url
        self._token = token
        if base_url.startswith("https://") and not verify_tls:
            print("warning: TLS certificate checking is OFF (verify_tls: false).", file=sys.stderr)
            context = ssl._create_unverified_context()
        else:
            context = ssl.create_default_context()
        self._opener = urllib.request.build_opener(
            _NoRedirect(), urllib.request.HTTPSHandler(context=context)
        )

    def _scrub(self, text):
        return str(text).replace(self._token, "[token hidden]") if self._token else str(text)

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
            "X-Plex-Client-Identifier": "cinemetric-library-report",
        }
        if start is not None:
            headers["X-Plex-Container-Start"] = str(start)
            headers["X-Plex-Container-Size"] = str(size)
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self._opener.open(request, timeout=TIMEOUT_SECONDS) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise ReportError("Plex rejected the token (HTTP 401 Unauthorized).") from None
            raise ReportError(f"Plex returned HTTP {exc.code} for {path}.") from None
        except urllib.error.URLError as exc:
            raise ReportError(
                f"Could not reach the Plex server at {self.base_url}: {self._scrub(exc.reason)}"
            ) from None
        except (TimeoutError, OSError) as exc:
            raise ReportError(f"Network error talking to Plex: {self._scrub(exc)}") from None
        try:
            return json.loads(body).get("MediaContainer", {})
        except ValueError:
            raise ReportError(f"Plex sent a response that was not JSON for {path}.") from None

    def get_all(self, section_id, type_number):
        """Every item of one type in a section, fetched in pages."""
        path = f"/library/sections/{section_id}/all"
        items, start = [], 0
        while True:
            page = self.get(path, {"type": type_number}, start=start, size=PAGE_SIZE)
            batch = page.get("Metadata", []) or []
            items.extend(batch)
            total = page.get("totalSize", page.get("size", len(items)))
            start += len(batch)
            if not batch or start >= total:
                return items

    def count(self, section_id, type_number):
        page = self.get(f"/library/sections/{section_id}/all", {"type": type_number}, start=0, size=0)
        return int(page.get("totalSize", page.get("size", 0)) or 0)


# ---------------------------------------------------------------- summarising

def clean(text):
    """Titles are untrusted data: strip control characters and cap the length."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text or "")).strip()
    return text[:MAX_TITLE_LENGTH]


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


def is_ten_bit(media):
    # The library listing has no HDR flag; a 10-bit profile is the closest signal it offers.
    return "10" in str(media.get("videoProfile") or "")


def bump(counter, key, amount=1):
    counter[key] = counter.get(key, 0) + amount


def is_unmatched(item):
    guid = str(item.get("guid") or "")
    return not guid or guid.startswith("local://")


class Tally:
    """Collects file sizes and video/audio breakdowns across media files."""

    def __init__(self, large_bytes):
        self.large_bytes = large_bytes
        self.files = 0
        self.bytes = 0
        self.resolution, self.video_codec, self.audio_codec = {}, {}, {}
        self.ten_bit = 0
        self.large = []
        self.unavailable = []

    def add(self, item, label):
        for media in item.get("Media", []) or []:
            if media.get("deletedAt"):
                self.unavailable.append(label)
            if media.get("videoResolution") or media.get("videoCodec"):
                bump(self.resolution, resolution_bucket(media.get("videoResolution")))
                bump(self.video_codec, str(media.get("videoCodec") or "unknown").lower())
                if is_ten_bit(media):
                    self.ten_bit += 1
            if media.get("audioCodec"):
                bump(self.audio_codec, str(media.get("audioCodec")).lower())
            for part in media.get("Part", []) or []:
                size = int(part.get("size") or 0)
                self.files += 1
                self.bytes += size
                if size >= self.large_bytes:
                    self.large.append({"title": label, "gb": round(size / 1e9, 1)})

    def as_dict(self, video=True):
        out = {"files": self.files, "size_gb": round(self.bytes / 1e9, 1)}
        if video:
            out["resolution"] = self.resolution
            out["video_codec"] = self.video_codec
            out["ten_bit_files"] = self.ten_bit
            out["large_files"] = sorted(self.large, key=lambda x: -x["gb"])[:15]
            out["large_files_total"] = len(self.large)
        out["audio_codec"] = self.audio_codec
        out["unavailable_files"] = len(self.unavailable)
        out["unavailable_examples"] = self.unavailable[:15]
        return out


def recent(items, n, label_fn):
    items = sorted(items, key=lambda i: int(i.get("addedAt") or 0), reverse=True)[:n]
    return [
        {"title": label_fn(i), "added": time.strftime("%Y-%m-%d", time.localtime(int(i.get("addedAt") or 0)))}
        for i in items
    ]


def housekeeping(items, label_fn, poster_field="thumb"):
    missing = [label_fn(i) for i in items if not i.get(poster_field)]
    unmatched = [label_fn(i) for i in items if is_unmatched(i)]
    return {
        "missing_poster_count": len(missing),
        "missing_poster_examples": missing[:15],
        "unmatched_count": len(unmatched),
        "unmatched_examples": unmatched[:15],
    }


def copies(item):
    """An item's versions that count as copies: found on disk and not a Plex optimized version.

    A version split across several files (parts) is still one copy.
    """
    out = []
    for media in item.get("Media", []) or []:
        if media.get("deletedAt") or media.get("proxyType"):
            continue
        out.append({
            "resolution": resolution_bucket(media.get("videoResolution")),
            "video_codec": str(media.get("videoCodec") or "unknown").lower(),
            "bytes": sum(int(p.get("size") or 0) for p in media.get("Part", []) or []),
        })
    return sorted(out, key=lambda c: -c["bytes"])


def gb(size):
    return round(size / 1e9, 1)


def top_examples(rows, limit):
    """Largest extra space first; swaps the internal byte count for extra_gb."""
    rows = sorted(rows, key=lambda r: -r["bytes"])[:limit]
    return [dict({k: v for k, v in r.items() if k != "bytes"}, extra_gb=gb(r["bytes"])) for r in rows]


def library_duplicates(items, label_fn, limit, by_show=False):
    """Items in one library with two or more copies. Extra space is every copy except the largest."""
    titles = extra_copies = extra = 0
    rows = {}
    for item in items:
        found = copies(item)
        if len(found) < 2:
            continue
        spare = sum(c["bytes"] for c in found[1:])
        titles += 1
        extra_copies += len(found) - 1
        extra += spare
        if by_show:
            row = rows.setdefault(item.get("grandparentRatingKey") or item.get("grandparentTitle"), {
                "title": clean(item.get("grandparentTitle")), "episodes": 0, "bytes": 0})
            row["episodes"] += 1
            row["bytes"] += spare
        else:
            rows[len(rows)] = {
                "title": label_fn(item),
                "bytes": spare,
                "copies": [{"resolution": c["resolution"], "video_codec": c["video_codec"], "gb": gb(c["bytes"])}
                           for c in found],
            }
    return {
        "titles": titles,
        "extra_copies": extra_copies,
        "extra_gb": gb(extra),
        "examples": top_examples(rows.values(), limit),
    }


def remember_guids(guids, items, library, label_fn, show=False):
    """Record each matched item's largest copy by guid, for finding the same title in other libraries."""
    for item in items:
        if is_unmatched(item):
            continue
        found = copies(item)
        if not found:
            continue
        per_library = guids.setdefault(str(item.get("guid")), {})
        best = per_library.get(library)
        if best and best["bytes"] >= found[0]["bytes"]:
            continue
        per_library[library] = {
            "title": clean(item.get("grandparentTitle")) if show else label_fn(item),
            "show": show,
            "resolution": found[0]["resolution"],
            "bytes": found[0]["bytes"],
        }


def cross_library_duplicates(guids, limit):
    """Titles whose guid is in two or more libraries. Each library counts once, by its largest copy."""
    titles = extra = 0
    rows = {}
    for guid, per_library in guids.items():
        if len(per_library) < 2:
            continue
        entries = sorted(per_library.items(), key=lambda kv: -kv[1]["bytes"])
        spare = sum(entry["bytes"] for _, entry in entries[1:])
        titles += 1
        extra += spare
        first = entries[0][1]
        if first["show"]:
            libraries = sorted(per_library)
            row = rows.setdefault((first["title"], tuple(libraries)), {
                "title": first["title"], "episodes": 0, "bytes": 0, "libraries": libraries})
            row["episodes"] += 1
            row["bytes"] += spare
        else:
            rows[guid] = {
                "title": first["title"],
                "bytes": spare,
                "libraries": [{"library": name, "resolution": entry["resolution"], "gb": gb(entry["bytes"])}
                              for name, entry in entries],
            }
    return {"titles": titles, "extra_gb": gb(extra), "examples": top_examples(rows.values(), limit)}


# Resolutions in quality order. Anything else (unknown, 8k, ...) can't be judged and is left out.
RESOLUTION_RANK = {"SD": 0, "720p": 1, "1080p": 2, "2K": 3, "4K": 4}
UPGRADE_BELOW = RESOLUTION_RANK["1080p"]


def best_copy(item):
    """The copy with the highest known resolution (the largest, if several share it), or None."""
    ranked = [c for c in copies(item) if c["resolution"] in RESOLUTION_RANK]
    if not ranked:
        return None
    return max(ranked, key=lambda c: (RESOLUTION_RANK[c["resolution"]], c["bytes"]))


def upgrade_candidates(items, label_fn, ranks, library):
    """Items whose best copy is below 1080p. Also records each matched item's best rank by guid,
    so build_report can drop candidates another library already has in better quality."""
    found = []
    for item in items:
        best = best_copy(item)
        if not best:
            continue
        rank = RESOLUTION_RANK[best["resolution"]]
        guid = None if is_unmatched(item) else str(item.get("guid"))
        if guid:
            per_library = ranks.setdefault(guid, {})
            per_library[library] = max(rank, per_library.get(library, -1))
        if rank < UPGRADE_BELOW:
            found.append({"guid": guid, "label": label_fn(item), "copy": best,
                          "show": clean(item.get("grandparentTitle")),
                          "show_key": item.get("grandparentRatingKey") or item.get("grandparentTitle")})
    return found


def library_upgrades(candidates, ranks, library, limit, by_show=False):
    """Finish one library's upgrades section once every library has been read."""
    titles = covered = 0
    by_resolution = {"SD": 0, "720p": 0}
    rows = {}
    for cand in candidates:
        elsewhere = ranks.get(cand["guid"], {}) if cand["guid"] else {}
        if any(rank >= UPGRADE_BELOW for name, rank in elsewhere.items() if name != library):
            covered += 1
            continue
        resolution = cand["copy"]["resolution"]
        titles += 1
        by_resolution[resolution] += 1
        if by_show:
            row = rows.setdefault(cand["show_key"], {
                "title": cand["show"], "episodes": 0, "by_resolution": {"SD": 0, "720p": 0}})
            row["episodes"] += 1
            row["by_resolution"][resolution] += 1
        else:
            rows[len(rows)] = {
                "title": cand["label"],
                "resolution": resolution,
                "video_codec": cand["copy"]["video_codec"],
                "gb": gb(cand["copy"]["bytes"]),
            }
    if by_show:
        order = lambda r: (-r["episodes"], r["title"].lower())
    else:
        order = lambda r: (RESOLUTION_RANK[r["resolution"]], r["title"].lower())
    return {
        "titles": titles,
        "by_resolution": by_resolution,
        "covered_elsewhere": covered,
        "examples": sorted(rows.values(), key=order)[:limit],
    }


def movie_label(item):
    year = item.get("year")
    return clean(f"{item.get('title')} ({year})" if year else item.get("title"))


def episode_label(item):
    return clean(
        f"{item.get('grandparentTitle')} S{int(item.get('parentIndex') or 0):02d}"
        f"E{int(item.get('index') or 0):02d}"
    )


def summarise_section(client, section, args, guids, ranks, pending):
    sid, kind = section.get("key"), section.get("type")
    out = {"name": clean(section.get("title")), "type": kind}
    large = int(args.large_gb * 1e9)

    if kind == "movie":
        movies = client.get_all(sid, TYPE_MOVIE)
        tally = Tally(large)
        for m in movies:
            tally.add(m, movie_label(m))
        out["counts"] = {"movies": len(movies)}
        out["media"] = tally.as_dict()
        out["recently_added"] = recent(movies, args.recent, movie_label)
        out["housekeeping"] = housekeeping(movies, movie_label)
        out["duplicates"] = library_duplicates(movies, movie_label, args.duplicate_examples)
        remember_guids(guids, movies, out["name"], movie_label)
        out["upgrades"] = None  # finished in build_report, once every library has been read
        pending.append((out, upgrade_candidates(movies, movie_label, ranks, out["name"]), False))

    elif kind == "show":
        shows = client.get_all(sid, TYPE_SHOW)
        episodes = client.get_all(sid, TYPE_EPISODE)
        tally = Tally(large)
        for e in episodes:
            tally.add(e, episode_label(e))
        out["counts"] = {
            "shows": len(shows),
            "seasons": client.count(sid, TYPE_SEASON),
            "episodes": len(episodes),
        }
        out["media"] = tally.as_dict()
        out["recently_added"] = recent(episodes, args.recent, episode_label)
        out["housekeeping"] = housekeeping(shows, lambda s: clean(s.get("title")))
        out["duplicates"] = library_duplicates(episodes, episode_label, args.duplicate_examples, by_show=True)
        remember_guids(guids, episodes, out["name"], episode_label, show=True)
        out["upgrades"] = None  # finished in build_report, once every library has been read
        pending.append((out, upgrade_candidates(episodes, episode_label, ranks, out["name"]), True))

    elif kind == "artist":
        tracks = client.get_all(sid, TYPE_TRACK)
        albums = client.get_all(sid, TYPE_ALBUM)
        tally = Tally(large)
        for t in tracks:
            tally.add(t, clean(t.get("title")))
        out["counts"] = {
            "artists": client.count(sid, TYPE_ARTIST),
            "albums": len(albums),
            "tracks": len(tracks),
        }
        out["media"] = tally.as_dict(video=False)
        album_label = lambda a: clean(f"{a.get('parentTitle')} - {a.get('title')}")
        out["recently_added"] = recent(albums, args.recent, album_label)
        out["housekeeping"] = housekeeping(albums, album_label)

    elif kind == "photo":
        out["counts"] = {"photos": client.count(sid, TYPE_PHOTO)}

    else:
        out["note"] = "library type not summarised"
    return out


def build_report(client, args):
    root = client.get("/")
    sections = client.get("/library/sections").get("Directory", []) or []
    if args.library:
        wanted = {name.lower() for name in args.library}
        sections = [s for s in sections if str(s.get("title", "")).lower() in wanted]
        if not sections:
            raise ReportError("No library matched --library. Run without it to see all names.")

    libraries, guids, ranks, pending = [], {}, {}, []
    for section in sections:
        print(f"reading library: {clean(section.get('title'))}", file=sys.stderr)
        libraries.append(summarise_section(client, section, args, guids, ranks, pending))
    for lib, candidates, by_show in pending:
        lib["upgrades"] = library_upgrades(candidates, ranks, lib["name"], args.upgrade_examples, by_show)

    totals = {"libraries": len(libraries), "files": 0, "size_gb": 0.0}
    for lib in libraries:
        media = lib.get("media", {})
        totals["files"] += media.get("files", 0)
        totals["size_gb"] = round(totals["size_gb"] + media.get("size_gb", 0), 1)

    return {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z"),
        "server": {
            "name": clean(root.get("friendlyName")),
            "version": root.get("version"),
            "platform": root.get("platform"),
        },
        "totals": totals,
        "cross_library_duplicates": cross_library_duplicates(guids, args.duplicate_examples),
        "libraries": libraries,
    }


def main():
    parser = argparse.ArgumentParser(description="Read-only Plex library report (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connection and token")
    parser.add_argument("--library", action="append", help="limit to a library by name (repeatable)")
    parser.add_argument("--recent", type=int, default=10, help="recently added items per library")
    parser.add_argument("--large-gb", type=float, default=40.0, help="flag files at least this many GB")
    parser.add_argument("--duplicate-examples", type=int, default=15, help="duplicate examples listed per section")
    parser.add_argument("--upgrade-examples", type=int, default=15, help="upgrade examples listed per library")
    args = parser.parse_args()
    args.recent = max(0, min(args.recent, 100))
    args.duplicate_examples = max(0, min(args.duplicate_examples, 500))
    args.upgrade_examples = max(0, min(args.upgrade_examples, 500))

    try:
        client = PlexClient(*load_config())
        if args.check:
            root = client.get("/")
            result = {
                "ok": True,
                "server": clean(root.get("friendlyName")),
                "version": root.get("version"),
                "platform": root.get("platform"),
            }
        else:
            result = build_report(client, args)
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
