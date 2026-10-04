#!/usr/bin/env python3
"""Cinemetric server health: read-only snapshot of a Plex Media Server's state.

Covers server basics (version, updates, remote access, resource use), live activity
(who is streaming and how), and background work (running tasks, library scans,
scheduled maintenance). Uses only the Python standard library. Prints one JSON
document to stdout; errors go to stderr.

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

# Server settings worth reporting. Everything else in /:/prefs is ignored.
PREF_IDS = {
    "ButlerStartHour": "maintenance_start_hour",
    "ButlerEndHour": "maintenance_end_hour",
    "FSEventLibraryUpdatesEnabled": "scan_on_folder_change",
    "ScheduledLibraryUpdatesEnabled": "scheduled_scans_enabled",
    "ScheduledLibraryUpdateInterval": "scheduled_scan_interval_seconds",
}


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


def as_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes")


def when(epoch):
    epoch = as_int(epoch)
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch)) if epoch else None


def days_ago(epoch, now):
    epoch = as_int(epoch)
    return round((now - epoch) / 86400, 1) if epoch else None


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

def running_activities(client):
    data = client.get("/activities")
    return [
        {
            "type": a.get("type"),
            "title": clean(a.get("title")),
            "detail": clean(a.get("subtitle")) or None,
            "progress_pct": as_int(a.get("progress")) if a.get("progress") is not None else None,
        }
        for a in data.get("Activity", []) or []
    ]


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


def maintenance_settings(client):
    data = client.get("/:/prefs")
    found = {}
    for setting in data.get("Setting", []) or []:
        name = PREF_IDS.get(setting.get("id"))
        if not name:
            continue
        value = setting.get("value")
        if isinstance(value, bool) or setting.get("type") == "bool":
            value = as_bool(value)
        elif name.endswith(("_hour", "_seconds")):
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

def worth_a_look(report, stale_days):
    """Plain facts the user may want to act on. Claude explains them; the script just flags."""
    notes = []
    update = report["server"].get("update")
    if update and update.get("update_available"):
        notes.append({"kind": "update_available", "version": update.get("available_version")})

    remote = report["server"].get("remote_access")
    if remote and remote.get("state") not in (None, "mapped"):
        notes.append({"kind": "remote_access_not_working", "state": remote.get("state"),
                      "error": remote.get("error_message") or remote.get("error")})

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

    usage = (report["server"].get("resource_use") or {}).get("average") or {}
    if (usage.get("host_cpu_pct") or 0) >= 85:
        notes.append({"kind": "high_cpu", "average_pct": usage["host_cpu_pct"]})
    if (usage.get("host_memory_pct") or 0) >= 90:
        notes.append({"kind": "high_memory", "average_pct": usage["host_memory_pct"]})
    return notes


def build_report(client, args):
    now = int(time.time())
    root = client.get("/")
    unavailable = []

    server = server_basics(root)
    server["update"] = optional("update check", lambda: update_status(client), unavailable)
    server["remote_access"] = optional("remote access", lambda: remote_access(client), unavailable)
    server["resource_use"] = optional("CPU and memory", lambda: resource_use(client), unavailable)

    background = {
        "running_now": optional("running tasks", lambda: running_activities(client), unavailable),
        "library_scans": optional(
            "library scans", lambda: library_scans(client, now), unavailable
        ),
        "maintenance_tasks": optional("maintenance tasks", lambda: maintenance_tasks(client), unavailable),
        "maintenance_settings": optional(
            "maintenance settings", lambda: maintenance_settings(client), unavailable
        ),
    }

    report = {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M %Z"),
        "server": server,
        "live_activity": optional("live activity", lambda: live_activity(client), unavailable),
        "background": background,
    }
    report["worth_a_look"] = worth_a_look(report, args.stale_days)
    report["unavailable"] = unavailable
    return report


def main():
    parser = argparse.ArgumentParser(description="Read-only Plex server health snapshot (JSON output).")
    parser.add_argument("--check", action="store_true", help="only test the connection and token")
    parser.add_argument("--stale-days", type=float, default=7.0,
                        help="flag libraries not scanned in this many days")
    args = parser.parse_args()
    args.stale_days = max(1.0, args.stale_days)

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
