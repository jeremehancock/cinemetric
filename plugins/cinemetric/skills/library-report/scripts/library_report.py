#!/usr/bin/env python3
"""Cinemetric library report: read-only summary of a Plex Media Server's libraries.

Talks to the server over its normal HTTP API using a token. Uses only the Python
standard library. Prints one JSON document to stdout; errors go to stderr.

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

VERSION = "0.22.0"
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


def month_keys(n, now=None):
    """The last n calendar months as YYYY-MM in local time, oldest first, ending with this month."""
    t = time.localtime(now)
    year, month, keys = t.tm_year, t.tm_mon, []
    for _ in range(n):
        keys.append(f"{year:04d}-{month:02d}")
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return keys[::-1]


def growth_counts(items, keys):
    """Items added, and the bytes of all their files now, per month in keys. Undated items are skipped."""
    counts = {k: [0, 0] for k in keys}
    for item in items:
        if not item.get("addedAt"):
            continue
        key = time.strftime("%Y-%m", time.localtime(int(item["addedAt"])))
        if key in counts:
            counts[key][0] += 1
            counts[key][1] += sum(int(p.get("size") or 0)
                                  for m in item.get("Media", []) or [] for p in m.get("Part", []) or [])
    return counts


def growth_section(counts, keys):
    return {
        "added": sum(counts[k][0] for k in keys),
        "gb": gb(sum(counts[k][1] for k in keys)),
        "months": [{"month": k, "added": counts[k][0], "gb": gb(counts[k][1])} for k in keys],
    }


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


# Music codecs by whether they keep every bit of the original audio. Anything else is "other".
LOSSLESS_CODECS = {"flac", "alac", "pcm", "aiff", "ape", "wavpack", "tta", "mlp", "truehd"}
LOSSY_CODECS = {"mp3", "mp2", "aac", "vorbis", "opus", "wma", "wmav1", "wmav2", "wmapro", "ac3", "eac3",
                "dca", "dts", "musepack"}


def codec_group(codec):
    codec = str(codec or "").lower()
    if codec in LOSSLESS_CODECS or codec.startswith("dsd"):
        return "lossless"
    return "lossy" if codec in LOSSY_CODECS else "other"


def bitrate_bucket(kbps):
    if not kbps:
        return "unknown"
    if kbps < 192:
        return "under_192"
    return "192_to_255" if kbps < 256 else "256_and_up"


def classify_track(track):
    """A track's group (the best of its counted copies), total size, and lossy bitrate and codec.

    Returns None when the track has no counted copies (as in copies(): found on disk, not optimized).
    """
    groups, size, kbps, codecs = set(), 0, 0, []
    for media in track.get("Media", []) or []:
        if media.get("deletedAt") or media.get("proxyType"):
            continue
        group = codec_group(media.get("audioCodec"))
        groups.add(group)
        size += sum(int(p.get("size") or 0) for p in media.get("Part", []) or [])
        if group == "lossy":
            kbps = max(kbps, int(media.get("bitrate") or 0))
            codecs.append(str(media.get("audioCodec")).lower())
    if not groups:
        return None
    group = next(g for g in ("lossless", "lossy", "other") if g in groups)
    return {"group": group, "bytes": size, "kbps": kbps, "codec": codecs[0] if codecs else None}


def audio_quality(tracks, limit):
    """Lossless vs lossy across a music library's tracks, by track, storage and album."""
    totals = {g: [0, 0] for g in ("lossless", "lossy", "other")}
    bitrates = {"under_192": 0, "192_to_255": 0, "256_and_up": 0, "unknown": 0}
    albums = {}
    for track in tracks:
        found = classify_track(track)
        if not found:
            continue
        totals[found["group"]][0] += 1
        totals[found["group"]][1] += found["bytes"]
        album = albums.setdefault(track.get("parentRatingKey") or track.get("parentTitle"), {
            "title": clean(f"{track.get('grandparentTitle')} - {track.get('parentTitle')}"),
            "lossless": 0, "lossy": 0, "kbps": [], "codecs": {}})
        if found["group"] == "lossless":
            album["lossless"] += 1
        elif found["group"] == "lossy":
            bitrates[bitrate_bucket(found["kbps"])] += 1
            album["lossy"] += 1
            if found["kbps"]:
                album["kbps"].append(found["kbps"])
            bump(album["codecs"], found["codec"])

    counts = {"lossless": 0, "lossy": 0, "mixed": 0}
    mixed, lossy = [], []
    for album in albums.values():
        if album["lossless"] and album["lossy"]:
            counts["mixed"] += 1
            mixed.append({"title": album["title"], "lossless_tracks": album["lossless"],
                          "lossy_tracks": album["lossy"]})
        elif album["lossless"]:
            counts["lossless"] += 1
        elif album["lossy"]:
            counts["lossy"] += 1
            # Most common codec; ties go to the name that sorts first, so the output is stable.
            codec = min(album["codecs"], key=lambda c: (-album["codecs"][c], c))
            kbps = round(sum(album["kbps"]) / len(album["kbps"])) if album["kbps"] else None
            lossy.append({"title": album["title"], "tracks": album["lossy"], "codec": codec, "kbps": kbps})
    mixed.sort(key=lambda r: (-r["lossy_tracks"], r["title"].lower()))
    lossy.sort(key=lambda r: (r["kbps"] is None, r["kbps"] or 0, r["title"].lower()))
    out = {g: {"tracks": n, "gb": gb(size)} for g, (n, size) in totals.items()}
    out.update({"lossy_bitrate": bitrates, "albums": counts,
                "mixed_examples": mixed[:limit], "lossy_examples": lossy[:limit]})
    return out


def movie_label(item):
    year = item.get("year")
    return clean(f"{item.get('title')} ({year})" if year else item.get("title"))


def episode_label(item):
    return clean(
        f"{item.get('grandparentTitle')} S{int(item.get('parentIndex') or 0):02d}"
        f"E{int(item.get('index') or 0):02d}"
    )


def rating_key(item):
    return clean(item.get("ratingKey"))


def unavailable_items(items, label_fn):
    """{ratingKey: label} of items with a file Plex marks unavailable."""
    return {rating_key(i): label_fn(i) for i in items
            if any(m.get("deletedAt") for m in i.get("Media", []) or [])}


def summarise_section(client, section, args, guids, ranks, pending, keys, growths, snap=None, present=None):
    """Summarise one library. Also fills snap (this library's snapshot area) and adds the
    ratingKey of every movie, episode and track to present."""
    snap = {} if snap is None else snap
    present = set() if present is None else present
    sid, kind = section.get("key"), section.get("type")
    out = {"name": clean(section.get("title")), "type": kind}
    large = int(args.large_gb * 1e9)
    snap.update({"name": out["name"], "type": clean(kind), "items": {}, "unavailable": {}})

    if kind == "movie":
        movies = client.get_all(sid, TYPE_MOVIE)
        tally = Tally(large)
        for m in movies:
            tally.add(m, movie_label(m))
        out["counts"] = {"movies": len(movies)}
        snap["items"] = {rating_key(m): movie_label(m) for m in movies}
        snap["unavailable"] = unavailable_items(movies, movie_label)
        present.update(snap["items"])
        out["media"] = tally.as_dict()
        out["recently_added"] = recent(movies, args.recent, movie_label)
        growths.append(growth_counts(movies, keys))
        out["growth"] = growth_section(growths[-1], keys)
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
        snap["items"] = {rating_key(s): clean(s.get("title")) for s in shows}
        snap["episodes"] = {}
        for e in episodes:
            bump(snap["episodes"], clean(e.get("grandparentRatingKey")))
        snap["unavailable"] = unavailable_items(episodes, episode_label)
        present.update(rating_key(e) for e in episodes)
        out["media"] = tally.as_dict()
        out["recently_added"] = recent(episodes, args.recent, episode_label)
        growths.append(growth_counts(episodes, keys))
        out["growth"] = growth_section(growths[-1], keys)
        out["housekeeping"] = housekeeping(shows, lambda s: clean(s.get("title")))
        out["duplicates"] = library_duplicates(episodes, episode_label, args.duplicate_examples, by_show=True)
        remember_guids(guids, episodes, out["name"], episode_label, show=True)
        out["upgrades"] = None  # finished in build_report, once every library has been read
        pending.append((out, upgrade_candidates(episodes, episode_label, ranks, out["name"]), True))

    elif kind == "artist":
        tracks = client.get_all(sid, TYPE_TRACK)
        albums = client.get_all(sid, TYPE_ALBUM)
        artists = client.get_all(sid, TYPE_ARTIST)
        tally = Tally(large)
        for t in tracks:
            tally.add(t, clean(t.get("title")))
        out["counts"] = {
            "artists": len(artists),
            "albums": len(albums),
            "tracks": len(tracks),
        }
        out["media"] = tally.as_dict(video=False)
        album_label = lambda a: clean(f"{a.get('parentTitle')} - {a.get('title')}")
        snap["items"] = {rating_key(a): album_label(a) for a in albums}
        snap["unavailable"] = unavailable_items(
            tracks, lambda t: clean(f"{t.get('grandparentTitle')} - {t.get('title')}"))
        present.update(rating_key(t) for t in tracks)
        out["recently_added"] = recent(albums, args.recent, album_label)
        growths.append(growth_counts(tracks, keys))
        out["growth"] = growth_section(growths[-1], keys)
        out["audio_quality"] = audio_quality(tracks, args.music_examples)
        out["housekeeping"] = housekeeping(albums, album_label)
        no_photo = [clean(a.get("title")) for a in artists if not a.get("thumb")]
        out["housekeeping"]["missing_artist_image_count"] = len(no_photo)
        out["housekeeping"]["missing_artist_image_examples"] = no_photo[:15]

    elif kind == "photo":
        out["counts"] = {"photos": client.count(sid, TYPE_PHOTO)}

    else:
        out["note"] = "library type not summarised"
    snap["counts"] = out.get("counts", {})
    snap["size_gb"] = out.get("media", {}).get("size_gb", 0.0)
    return out


# ---------------------------------------------------------------- since the last snapshot

EXAMPLES = 25
CHANGE_LISTS = ("added", "removed", "episodes_added", "episodes_removed", "became_unavailable",
                "available_again")


def text_map(value):
    """A {key: text} map from a snapshot, ignoring anything that isn't one."""
    return {k: v for k, v in value.items() if isinstance(v, str)} if isinstance(value, dict) else {}


def size_of(lib):
    size = lib.get("size_gb")
    return float(size) if isinstance(size, (int, float)) and not isinstance(size, bool) else 0.0


def count_map(value):
    return {k: as_count(v) for k, v in value.items()} if isinstance(value, dict) else {}


def put_list(entry, name, names):
    entry[f"{name}_count"] = len(names)
    entry[name] = sorted(names, key=str.lower)[:EXAMPLES]


def put_episodes(entry, name, rows):
    """Shows with the episode difference; the count is the number of episodes."""
    entry[f"{name}_count"] = sum(r["count"] for r in rows)
    entry[name] = sorted(rows, key=lambda r: r["show"].lower())[:EXAMPLES]


def library_change(old, new, present):
    entry = {"name": new["name"], "type": new["type"], "status": "same"}
    if isinstance(old.get("name"), str) and old["name"] != new["name"]:
        entry["renamed_from"] = old["name"]
    old_counts = count_map(old.get("counts"))
    entry["counts_change"] = {k: v - old_counts.get(k, 0) for k, v in new["counts"].items()}
    entry["size_gb_change"] = round(new["size_gb"] - size_of(old), 1)
    old_items, new_items = text_map(old.get("items")), new["items"]
    put_list(entry, "added", [v for k, v in new_items.items() if k not in old_items])
    put_list(entry, "removed", [v for k, v in old_items.items() if k not in new_items])
    if new["type"] == "show":
        old_eps, new_eps = count_map(old.get("episodes")), new["episodes"]
        name = lambda key: new_items.get(key) or old_items.get(key) or "unknown show"
        put_episodes(entry, "episodes_added", [
            {"show": name(k), "count": n - old_eps.get(k, 0)} for k, n in new_eps.items() if n > old_eps.get(k, 0)])
        put_episodes(entry, "episodes_removed", [
            {"show": name(k), "count": n - new_eps.get(k, 0)} for k, n in old_eps.items() if n > new_eps.get(k, 0)])
    old_gone, new_gone = text_map(old.get("unavailable")), new["unavailable"]
    put_list(entry, "became_unavailable", [v for k, v in new_gone.items() if k not in old_gone])
    put_list(entry, "available_again", [v for k, v in old_gone.items()
                                        if k not in new_gone and k in present])
    return entry


def library_changes(old_area, new_area, present, covered_all):
    """Compare this run's libraries with a snapshot's library area."""
    libraries = []
    totals = dict.fromkeys(CHANGE_LISTS, 0)
    totals["size_gb_change"] = 0.0
    for key, lib in new_area.items():
        old = old_area.get(key)
        if isinstance(old, dict):
            entry = library_change(old, lib, present)
            for name in CHANGE_LISTS:
                totals[name] += entry.get(f"{name}_count", 0)
            totals["size_gb_change"] += entry["size_gb_change"]
        else:
            entry = {"name": lib["name"], "type": lib["type"], "status": "new",
                     "counts": lib["counts"], "size_gb": lib["size_gb"]}
            totals["size_gb_change"] += lib["size_gb"]
        libraries.append(entry)
    if covered_all:
        for key, old in old_area.items():
            if key in new_area or not isinstance(old, dict):
                continue
            size = size_of(old)
            libraries.append({"name": old.get("name") if isinstance(old.get("name"), str) else "",
                              "type": old.get("type") if isinstance(old.get("type"), str) else "",
                              "status": "removed", "counts": count_map(old.get("counts")),
                              "size_gb": size})
            totals["size_gb_change"] -= size
    totals["size_gb_change"] = round(totals["size_gb_change"], 1)
    return {"libraries": libraries, "totals": totals}


def since_snapshot(server_id, new_area, present, args):
    try:
        found = choose_snapshot(server_id, "library", args.since)
        if not found:
            return None
        old_area, when = found
        return dict(when, **library_changes(old_area, new_area, present, not args.library))
    except Exception:  # a bad snapshot never stops the report
        return None


def build_report(client, args):
    root = client.get("/")
    sections = client.get("/library/sections").get("Directory", []) or []
    if args.library:
        wanted = {name.lower() for name in args.library}
        sections = [s for s in sections if str(s.get("title", "")).lower() in wanted]
        if not sections:
            raise ReportError("No library matched --library. Run without it to see all names.")

    libraries, guids, ranks, pending, growths = [], {}, {}, [], []
    area, present = {}, set()
    keys = month_keys(args.growth_months)
    for section in sections:
        print(f"reading library: {clean(section.get('title'))}", file=sys.stderr)
        snap = area.setdefault(clean(section.get("key")), {})
        libraries.append(summarise_section(client, section, args, guids, ranks, pending, keys, growths,
                                           snap, present))
    for lib, candidates, by_show in pending:
        lib["upgrades"] = library_upgrades(candidates, ranks, lib["name"], args.upgrade_examples, by_show)

    totals = {"libraries": len(libraries), "files": 0, "size_gb": 0.0}
    for lib in libraries:
        media = lib.get("media", {})
        totals["files"] += media.get("files", 0)
        totals["size_gb"] = round(totals["size_gb"] + media.get("size_gb", 0), 1)
    # Sum bytes across libraries before rounding, so the combined figures don't drift.
    combined = {k: [sum(g[k][0] for g in growths), sum(g[k][1] for g in growths)] for k in keys}

    server_id = str(root.get("machineIdentifier") or "")
    report = {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z"),
        "server": {
            "name": clean(root.get("friendlyName")),
            "version": root.get("version"),
            "platform": root.get("platform"),
        },
        "totals": totals,
        "growth": growth_section(combined, keys),
        "cross_library_duplicates": cross_library_duplicates(guids, args.duplicate_examples),
        "libraries": libraries,
        "since_snapshot": since_snapshot(server_id, area, present, args),
    }
    if args.snapshot_items:
        report["snapshot"] = {"server_id": clean(server_id), "area": area}
    return report


def main():
    parser = argparse.ArgumentParser(description="Read-only Plex library report (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connection and token")
    parser.add_argument("--library", action="append", help="limit to a library by name (repeatable)")
    parser.add_argument("--recent", type=int, default=10, help="recently added items per library")
    parser.add_argument("--large-gb", type=float, default=40.0, help="flag files at least this many GB")
    parser.add_argument("--duplicate-examples", type=int, default=15, help="duplicate examples listed per section")
    parser.add_argument("--upgrade-examples", type=int, default=15, help="upgrade examples listed per library")
    parser.add_argument("--growth-months", type=int, default=12, help="months covered by growth by month")
    parser.add_argument("--music-examples", type=int, default=15, help="mixed and lossy album examples listed")
    parser.add_argument("--since", type=int, help="compare with a snapshot at least this many days old (1-90)")
    parser.add_argument("--snapshot-items", action="store_true",
                        help="add this run's part of a snapshot (used by the changes skill and dashboard)")
    args = parser.parse_args()
    if args.snapshot_items and args.library:
        print("error: --snapshot-items can't be used with --library: a snapshot covers every library.",
              file=sys.stderr)
        return 1
    if args.since is not None:
        args.since = max(1, min(args.since, 90))
    args.recent = max(0, min(args.recent, 100))
    args.duplicate_examples = max(0, min(args.duplicate_examples, 500))
    args.upgrade_examples = max(0, min(args.upgrade_examples, 500))
    args.growth_months = max(0, min(args.growth_months, 120))
    args.music_examples = max(0, min(args.music_examples, 500))

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
