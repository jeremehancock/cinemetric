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

VERSION = "0.3.0"
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


def movie_label(item):
    year = item.get("year")
    return clean(f"{item.get('title')} ({year})" if year else item.get("title"))


def episode_label(item):
    return clean(
        f"{item.get('grandparentTitle')} S{int(item.get('parentIndex') or 0):02d}"
        f"E{int(item.get('index') or 0):02d}"
    )


def summarise_section(client, section, args):
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

    libraries = []
    for section in sections:
        print(f"reading library: {clean(section.get('title'))}", file=sys.stderr)
        libraries.append(summarise_section(client, section, args))

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
        "libraries": libraries,
    }


def main():
    parser = argparse.ArgumentParser(description="Read-only Plex library report (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connection and token")
    parser.add_argument("--library", action="append", help="limit to a library by name (repeatable)")
    parser.add_argument("--recent", type=int, default=10, help="recently added items per library")
    parser.add_argument("--large-gb", type=float, default=40.0, help="flag files at least this many GB")
    args = parser.parse_args()
    args.recent = max(0, min(args.recent, 100))

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
