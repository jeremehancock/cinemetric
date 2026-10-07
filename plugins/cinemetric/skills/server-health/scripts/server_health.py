#!/usr/bin/env python3
"""Cinemetric server health: read-only snapshot of a Plex Media Server's state.

Covers server basics (version, updates, remote access, resource use), live activity
(who is streaming and how), and background work (running tasks, library scans,
scheduled maintenance). Uses only the Python standard library. Prints one JSON
document to stdout; errors go to stderr.

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

VERSION = "0.25.1"
TIMEOUT_SECONDS = 30
MAX_TITLE_LENGTH = 120

# The only server paths this script may request.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/updater/status$"),
    re.compile(r"^/myplex/account$"),
    re.compile(r"^/statistics/resources$"),
    re.compile(r"^/status/sessions$"),
    re.compile(r"^/activities$"),
    re.compile(r"^/butler$"),
    re.compile(r"^/:/prefs$"),
    re.compile(r"^/library/sections$"),
]

# Maintenance tasks that keep the server healthy. Others are optional and often off by default.
IMPORTANT_TASKS = {"BackupDatabase", "OptimizeDatabase", "CleanOldBundles", "CleanOldCacheFiles"}

# DVR and Live TV tasks follow a recording in real time and wait while it runs, so they aren't
# checked for being stuck.
UNWATCHED_TASK_TYPES = ("provider.subscription.", "grabber.")

# Server settings worth reporting. Everything else in /:/prefs is ignored, since it also holds
# values that must never be printed.
MAINTENANCE_PREFS = {
    "ButlerStartHour": "maintenance_start_hour",
    "ButlerEndHour": "maintenance_end_hour",
    "FSEventLibraryUpdatesEnabled": "scan_on_folder_change",
    "ScheduledLibraryUpdatesEnabled": "scheduled_scans_enabled",
    "ScheduledLibraryUpdateInterval": "scheduled_scan_interval_seconds",
    "autoEmptyTrash": "empty_trash_after_scan",
}
STREAMING_PREFS = {
    "HardwareAcceleratedCodecs": "hardware_acceleration",
    "HardwareAcceleratedEncoders": "hardware_encoding",
    "TranscoderCanOnlyRemuxVideo": "video_transcoding_disabled",
    "WanPerStreamMaxUploadRate": "remote_stream_limit_kbps",
    "WanTotalMaxUploadRate": "remote_total_upload_limit_kbps",
    # Only whether a custom folder is set; the path itself is never kept.
    "TranscoderTempDirectory": "custom_transcoder_temp_folder",
}

# Plex labels remote limits below 8 Mbps as 720p or lower, so remote viewers can't get 1080p.
LOW_REMOTE_LIMIT_KBPS = 8000


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

    def get(self, path, params=None):
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
            "X-Plex-Client-Identifier": "cinemetric-server-health",
        }
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
            data = json.loads(body) if body.strip() else {}
        except ValueError:
            raise ReportError(f"Plex sent a response that was not JSON for {path}.") from None
        if not isinstance(data, dict):
            return {}
        # Most endpoints wrap their data in MediaContainer; a few (like /butler) do not.
        return data.get("MediaContainer", data)


# ---------------------------------------------------------------- helpers

def clean(text):
    """Titles and names are untrusted data: strip control characters and cap the length."""
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


def as_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes")


def when(epoch):
    # Plex uses 0 or -1 for "never" (for example an update check that hasn't run).
    epoch = as_int(epoch)
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch)) if epoch > 0 else None


def days_ago(epoch, now):
    epoch = as_int(epoch)
    return round((now - epoch) / 86400, 1) if epoch > 0 else None


def once(fn):
    """Call fn the first time only, then hand back the same result (or raise the same error)."""
    saved = []

    def wrapper():
        if not saved:
            try:
                saved.append((fn(), None))
            except ReportError as exc:
                saved.append((None, exc))
        result, error = saved[0]
        if error:
            raise error
        return result
    return wrapper


def optional(name, fn, unavailable):
    """Run one optional part of the report; record its name instead of failing the whole run.

    The token already worked for "/", so a 401 or 403 here means this part is limited to the
    server owner (the user may be connected to a server someone shared with them).
    """
    try:
        return fn()
    except ReportError as exc:
        reason = str(exc)
        if "401" in reason or "403" in reason:
            reason = "only available to the server owner's account"
        unavailable.append({"part": name, "reason": reason})
        return None


# ---------------------------------------------------------------- server basics

def server_basics(root):
    return {
        "name": clean(root.get("friendlyName")),
        "version": root.get("version"),
        "platform": clean(f"{root.get('platform') or ''} {root.get('platformVersion') or ''}"),
        "signed_in_to_plex": root.get("myPlexSigninState") == "ok" if "myPlexSigninState" in root else None,
        "plex_pass": as_bool(root.get("myPlexSubscription")) if "myPlexSubscription" in root else None,
        "active_transcodes": as_int(root.get("transcoderActiveVideoSessions")),
    }


def update_status(client):
    data = client.get("/updater/status")
    releases = data.get("Release", []) or []
    newest = releases[0] if releases else None
    return {
        "update_available": bool(newest),
        "available_version": newest.get("version") if newest else None,
        "state": newest.get("state") if newest else None,
        "last_checked": when(data.get("checkedAt")),
        "can_install_from_plex": as_bool(data.get("canInstall")) if "canInstall" in data else None,
    }


def remote_access(client):
    data = client.get("/myplex/account")
    data = data.get("MyPlex", data)
    if not data.get("mappingState") and not data.get("signInState"):
        raise ReportError("Plex did not report remote access details.")
    # The public address is left out on purpose; the user doesn't need it in a report.
    return {
        "state": data.get("mappingState"),
        "error": clean(data.get("mappingError")) or None,
        "error_message": clean(data.get("mappingErrorMessage")) or None,
        "signed_in": data.get("signInState") == "ok" if data.get("signInState") else None,
    }


def resource_use(client):
    data = client.get("/statistics/resources", {"timespan": 6})
    samples = data.get("StatisticsResources", []) or []
    if not samples:
        return None
    samples = sorted(samples, key=lambda s: as_int(s.get("at")))

    def pct(key, rows):
        values = [float(r.get(key)) for r in rows if r.get(key) is not None]
        return round(sum(values) / len(values), 1) if values else None

    latest = samples[-1]
    keys = {
        "host_cpu_pct": "hostCpuUtilization",
        "plex_cpu_pct": "processCpuUtilization",
        "host_memory_pct": "hostMemoryUtilization",
        "plex_memory_pct": "processMemoryUtilization",
    }
    return {
        "latest": {name: pct(key, [latest]) for name, key in keys.items()},
        "average": {name: pct(key, samples) for name, key in keys.items()},
        "sampled_since": when(samples[0].get("at")),
        "samples": len(samples),
    }


# ---------------------------------------------------------------- live activity

def stream_title(item):
    kind = item.get("type")
    if kind == "episode":
        return clean(
            f"{item.get('grandparentTitle')} S{as_int(item.get('parentIndex')):02d}"
            f"E{as_int(item.get('index')):02d}"
        )
    if kind == "track":
        return clean(f"{item.get('grandparentTitle')} - {item.get('title')}")
    year = item.get("year")
    return clean(f"{item.get('title')} ({year})" if year else item.get("title"))


def playback_method(item):
    transcode = item.get("TranscodeSession")
    if not transcode:
        return "direct play"
    if "transcode" in (transcode.get("videoDecision"), transcode.get("audioDecision")):
        return "transcode"
    return "direct stream"


def live_activity(client):
    data = client.get("/status/sessions")
    streams = []
    totals = {"streams": 0, "direct_play": 0, "direct_stream": 0, "transcode": 0,
              "bandwidth_kbps": 0, "lan_kbps": 0, "wan_kbps": 0}
    for item in data.get("Metadata", []) or []:
        method = playback_method(item)
        session = item.get("Session") or {}
        player = item.get("Player") or {}
        transcode = item.get("TranscodeSession") or {}
        media = (item.get("Media") or [{}])[0]
        bandwidth = as_int(session.get("bandwidth"))
        location = session.get("location") or ("lan" if player.get("local") else None)
        duration = as_int(item.get("duration"))

        stream = {
            "user": clean((item.get("User") or {}).get("title")),
            "title": stream_title(item),
            "type": item.get("type"),
            "player": clean(player.get("title") or player.get("product")),
            "platform": clean(player.get("platform")),
            "state": player.get("state"),
            "live_tv": as_bool(item.get("live")),
            "progress_pct": round(100 * as_int(item.get("viewOffset")) / duration) if duration else None,
            "method": method,
            "source_quality": media.get("videoResolution"),
            "bandwidth_kbps": bandwidth or None,
            "location": location,
        }
        if method == "transcode":
            stream["transcode"] = {
                "video": transcode.get("videoDecision"),
                "audio": transcode.get("audioDecision"),
                "hardware": as_bool(transcode.get("transcodeHwFullPipeline"))
                if "transcodeHwFullPipeline" in transcode else None,
                "speed": transcode.get("speed"),
                "throttled": as_bool(transcode.get("throttled")) if "throttled" in transcode else None,
            }
        streams.append(stream)

        totals["streams"] += 1
        totals[method.replace(" ", "_")] += 1
        totals["bandwidth_kbps"] += bandwidth
        if location in ("lan", "wan"):
            totals[f"{location}_kbps"] += bandwidth
    return {"totals": totals, "streams": streams}


# ---------------------------------------------------------------- background work

def pause(seconds):
    """Wait between the two task checks. A separate function so tests can skip the wait."""
    time.sleep(seconds)


def read_activities(client):
    """Plex's raw list of running tasks, kept as-is so two checks can be compared."""
    return client.get("/activities").get("Activity", []) or []


def describe_activity(a):
    return {
        "type": a.get("type"),
        "title": clean(a.get("title")),
        "detail": clean(a.get("subtitle")) or None,
        "progress_pct": as_int(a.get("progress")) if a.get("progress") is not None else None,
    }


def activity_key(a):
    """Match a task across the two checks: by Plex's uuid, or by type and title without one."""
    return a.get("uuid") or (a.get("type"), a.get("title"))


def progress_value(a):
    try:
        return float(a.get("progress"))
    except (TypeError, ValueError):
        return None


def watched(a):
    """Whether a task can be checked for movement: it has progress and isn't a DVR task."""
    return progress_value(a) is not None and not str(a.get("type") or "").startswith(UNWATCHED_TASK_TYPES)


def progress_moved(client, first, wait, unavailable):
    """For each task in the first check, whether it moved by the second check: True, False or None.

    None means it wasn't checked: no progress value, a DVR or Live TV task, finished during the
    wait, no unique match, or no second check (nothing to watch, check turned off, or the second request failed).
    """
    moved = [None] * len(first)
    checked = [i for i, a in enumerate(first) if watched(a)]
    if wait <= 0 or not checked:
        return moved
    pause(wait)
    second = optional("stuck task check", lambda: read_activities(client), unavailable)
    if second is None:
        return moved
    # Two tasks with the same key can't be told apart, so neither is compared.
    first_keys = [activity_key(a) for a in first]
    later = {}
    for b in second:
        later.setdefault(activity_key(b), []).append(b)
    for i in checked:
        key = first_keys[i]
        matches = later.get(key, [])
        if first_keys.count(key) != 1 or len(matches) != 1:
            continue
        a, b = first[i], matches[0]
        moved[i] = progress_value(a) != progress_value(b) or a.get("subtitle") != b.get("subtitle")
    return moved


def running_activities(client, wait, unavailable):
    """Tasks running now, each with whether its progress moved over `wait` seconds."""
    first = read_activities(client)
    moved = progress_moved(client, first, wait, unavailable)
    return [dict(describe_activity(a), progress_moved=m) for a, m in zip(first, moved)]


def task_label(task):
    """Readable task name: 'ButlerTaskGenerateAdMarkers' becomes 'Generate Ad Markers'."""
    if task.get("title"):
        return clean(task["title"])
    name = re.sub(r"^ButlerTask", "", str(task.get("name") or ""))
    return clean(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name))


def maintenance_tasks(client):
    data = client.get("/butler")
    tasks = data.get("ButlerTasks", data)
    if isinstance(tasks, dict):
        tasks = tasks.get("ButlerTask", [])
    tasks = tasks or []
    enabled = [task_label(t) for t in tasks if as_bool(t.get("enabled"))]
    disabled = [task_label(t) for t in tasks if not as_bool(t.get("enabled"))]
    important_off = [
        task_label(t) for t in tasks
        if t.get("name") in IMPORTANT_TASKS and not as_bool(t.get("enabled"))
    ]
    return {"enabled": enabled, "disabled": disabled, "important_disabled": important_off}


def pick_settings(prefs, table):
    """Keep only the settings in table, renamed and converted. Missing settings are left out."""
    found = {}
    for setting in prefs.get("Setting", []) or []:
        name = table.get(setting.get("id"))
        if not name:
            continue
        value = setting.get("value")
        if name == "custom_transcoder_temp_folder":
            value = bool(str(value or "").strip())
        elif isinstance(value, bool) or setting.get("type") == "bool":
            value = as_bool(value)
        elif name.endswith(("_hour", "_seconds", "_kbps")):
            value = as_int(value, None)
        found[name] = value
    return found


def library_scans(client, now):
    data = client.get("/library/sections")
    libraries = []
    for section in data.get("Directory", []) or []:
        age = days_ago(section.get("scannedAt"), now)
        libraries.append({
            "name": clean(section.get("title")),
            "type": section.get("type"),
            "scanning_now": as_bool(section.get("refreshing")),
            "last_scanned": when(section.get("scannedAt")),
            "days_since_scan": age,
        })
    return libraries


# ---------------------------------------------------------------- report

def worth_a_look(report, stale_days, stuck_wait=0):
    """Plain facts the user may want to act on. Claude explains them; the script just flags."""
    notes = []
    update = report["server"].get("update")
    if update and update.get("update_available"):
        notes.append({"kind": "update_available", "version": update.get("available_version")})

    remote = report["server"].get("remote_access")
    if remote and remote.get("state") not in (None, "mapped"):
        notes.append({"kind": "remote_access_not_working", "state": remote.get("state"),
                      "error": remote.get("error_message") or remote.get("error")})

    # Facts about how the server is set up; a setting the server didn't return is never flagged.
    streaming = report["server"].get("streaming_settings") or {}
    if streaming.get("hardware_acceleration") is False:
        notes.append({"kind": "hardware_transcoding_off"})
    if streaming.get("video_transcoding_disabled") is True:
        notes.append({"kind": "video_transcoding_off"})
    limit = streaming.get("remote_stream_limit_kbps")
    if 0 < (limit or 0) < LOW_REMOTE_LIMIT_KBPS:
        notes.append({"kind": "remote_stream_limit_low", "limit_kbps": limit})

    live = report.get("live_activity")
    if live:
        for s in live["streams"]:
            t = s.get("transcode") or {}
            # Below 1x and not throttled means the server can't keep up and the viewer may buffer.
            try:
                speed = float(t.get("speed"))
            except (TypeError, ValueError):
                continue
            if t.get("throttled") is False and speed < 1:
                notes.append({"kind": "transcode_too_slow", "user": s["user"], "title": s["title"],
                              "speed": t["speed"]})

    background = report.get("background") or {}
    scans = background.get("library_scans") or []
    settings = background.get("maintenance_settings") or {}
    if settings.get("scheduled_scans_enabled"):
        # Scheduled full scans update the last-scanned date, so an old date means they aren't running.
        overdue = [
            lib["name"] for lib in scans
            if not lib["scanning_now"] and (lib["days_since_scan"] is None or lib["days_since_scan"] > stale_days)
        ]
        if overdue:
            notes.append({"kind": "scheduled_scans_not_running", "days": stale_days, "libraries": overdue})
    elif settings.get("scan_on_folder_change") is False and "scheduled_scans_enabled" in settings:
        notes.append({"kind": "automatic_scans_off"})
    # With only folder-change scanning, the last-scanned date isn't updated by those small scans,
    # so an old date is normal and isn't flagged.

    tasks = background.get("maintenance_tasks") or {}
    if tasks.get("important_disabled"):
        notes.append({"kind": "important_maintenance_disabled", "tasks": tasks["important_disabled"]})

    stuck = [
        {"title": task["title"], "progress_pct": task["progress_pct"]}
        for task in background.get("running_now") or []
        if task.get("progress_moved") is False
    ]
    if stuck:
        # Not moving over a short wait isn't proof of a problem; Claude words it as "possibly stuck".
        notes.append({"kind": "task_not_progressing", "seconds_between_checks": stuck_wait, "tasks": stuck})

    usage = (report["server"].get("resource_use") or {}).get("average") or {}
    if (usage.get("host_cpu_pct") or 0) >= 85:
        notes.append({"kind": "high_cpu", "average_pct": usage["host_cpu_pct"]})
    if (usage.get("host_memory_pct") or 0) >= 90:
        notes.append({"kind": "high_memory", "average_pct": usage["host_memory_pct"]})
    return notes


# ---------------------------------------------------------------- since the last snapshot

def health_area(server):
    """This run's part of a snapshot. update_version is false when Plex says there's no update and
    null when the update check failed, so an unknown value is never mistaken for a change."""
    update = server.get("update")
    if update is None:
        update_version = None
    elif update.get("update_available"):
        update_version = clean(update.get("available_version")) or None
    else:
        update_version = False
    return {
        "version": clean(server.get("version")) or None,
        "update_version": update_version,
        "remote_access": clean((server.get("remote_access") or {}).get("state")) or None,
    }


def health_changes(old, new):
    changes = []
    for kind in ("version", "update_version", "remote_access"):
        before, after = old.get(kind), new[kind]
        if before is None or after is None or not isinstance(before, (str, bool)) or before == after:
            continue
        changes.append({"kind": kind, "from": before, "to": after})
    return changes


def since_snapshot(server_id, area, args):
    try:
        found = choose_snapshot(server_id, "health", args.since)
        if not found:
            return None
        old, when = found
        return dict(when, changes=health_changes(old, area))
    except Exception:  # a bad snapshot never stops the report
        return None


def build_report(client, args):
    now = int(time.time())
    root = client.get("/")
    unavailable = []
    # One /:/prefs request feeds both settings parts; if it fails, both are listed as unavailable.
    prefs = once(lambda: client.get("/:/prefs"))

    server = server_basics(root)
    server["update"] = optional("update check", lambda: update_status(client), unavailable)
    server["remote_access"] = optional("remote access", lambda: remote_access(client), unavailable)
    server["resource_use"] = optional("CPU and memory", lambda: resource_use(client), unavailable)
    server["streaming_settings"] = optional(
        "streaming settings", lambda: pick_settings(prefs(), STREAMING_PREFS), unavailable
    )

    background = {
        "running_now": optional(
            "running tasks", lambda: running_activities(client, args.stuck_wait, unavailable), unavailable
        ),
        "library_scans": optional(
            "library scans", lambda: library_scans(client, now), unavailable
        ),
        "maintenance_tasks": optional("maintenance tasks", lambda: maintenance_tasks(client), unavailable),
        "maintenance_settings": optional(
            "maintenance settings", lambda: pick_settings(prefs(), MAINTENANCE_PREFS), unavailable
        ),
    }

    report = {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z"),
        "server": server,
        "live_activity": optional("live activity", lambda: live_activity(client), unavailable),
        "background": background,
    }
    report["worth_a_look"] = worth_a_look(report, args.stale_days, args.stuck_wait)
    report["unavailable"] = unavailable
    server_id = str(root.get("machineIdentifier") or "")
    area = health_area(server)
    report["since_snapshot"] = since_snapshot(server_id, area, args)
    if args.snapshot_items:
        report["snapshot"] = {"server_id": clean(server_id), "area": area}
    return report


def now_playing(client):
    """Only the current streams, for the Now Playing mod: one request, no snapshots."""
    return {
        "cinemetric_version": VERSION,
        "checked_at": int(time.time()),
        "live_activity": live_activity(client),
    }


def main():
    parser = argparse.ArgumentParser(description="Read-only Plex server health snapshot (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connection and token")
    parser.add_argument("--stale-days", type=float, default=7.0,
                        help="flag libraries not scanned in this many days")
    parser.add_argument("--stuck-wait", type=int, default=15,
                        help="seconds to wait before checking running tasks again (0 turns it off)")
    parser.add_argument("--since", type=int, help="compare with a snapshot at least this many days old (1-90)")
    parser.add_argument("--snapshot-items", action="store_true",
                        help="add this run's part of a snapshot (used by the changes skill and dashboard)")
    parser.add_argument("--now-playing", action="store_true",
                        help="only the current streams (used by the Now Playing mod)")
    args = parser.parse_args()
    if args.since is not None:
        args.since = max(1, min(args.since, 90))
    args.stale_days = max(1.0, args.stale_days)
    args.stuck_wait = min(300, max(0, args.stuck_wait))

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
        elif args.now_playing:
            result = now_playing(client)
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
