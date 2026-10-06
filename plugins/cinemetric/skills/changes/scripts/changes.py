#!/usr/bin/env python3
"""Cinemetric changes: what changed on a Plex server since the last snapshot.

It runs the library-report, server-health and users-and-shares scripts (so it has exactly their
read-only behaviour and never contacts anything itself), prints the "since the last snapshot" part of
each, and saves today's snapshot from their output. Each report does its own comparison; this script
only gathers, saves, prunes, lists and deletes snapshots. Uses only the Python standard library.

  changes.py [--since DAYS]   run the reports, save today's snapshot and say what changed
  changes.py save             save a snapshot from reports given as JSON on stdin (no network)
  changes.py list             list saved snapshots
  changes.py forget           delete every saved snapshot
"""

import argparse
import datetime
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

VERSION = "0.19.0"
SCRIPT_TIMEOUT_SECONDS = 1800
KEEP_DAYS = 90
MAX_TITLE_LENGTH = 120

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.normpath(os.path.join(HERE, "..", ".."))
SOURCES = {
    "library": ("library-report", "library_report.py", ["--snapshot-items"]),
    "health": ("server-health", "server_health.py", ["--stuck-wait", "0", "--snapshot-items"]),
    "sharing": ("users-and-shares", "users_and_shares.py", ["--snapshot-items"]),
}


class ChangesError(Exception):
    """An error with a message that is safe to show the user."""


def clean(text):
    """Text from snapshots and reports is untrusted data: strip control characters and cap the length."""
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


def read_snapshot(path):
    """A snapshot's contents with text cleaned, or None if it isn't a sound format 1 snapshot."""
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
    return clean_tree(data)


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


def ensure_private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    if os.name == "posix":
        os.chmod(path, 0o700)


def write_private(path, content):
    """Write a file atomically, readable only by the user."""
    folder = os.path.dirname(path)
    ensure_private_dir(folder)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".cinemetric-", suffix=".tmp")
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# ---------------------------------------------------------------- saving

def save_snapshot(reports, today=None):
    """Save today's snapshot from the reports' snapshot blocks. Returns the date saved, or None."""
    today = today or datetime.date.today()
    blocks = {}
    for area, report in reports.items():
        block = report.get("snapshot") if isinstance(report, dict) else None
        if area in SOURCES and isinstance(block, dict) and isinstance(block.get("area"), dict):
            blocks[area] = block
    server_ids = {str(b.get("server_id") or "") for b in blocks.values()}
    if not blocks or len(server_ids) != 1:
        return None
    server_id = server_ids.pop()
    if not SERVER_ID.match(server_id):
        return None

    path = os.path.join(snapshots_dir(), server_id, f"{today.isoformat()}.json")
    snapshot = read_snapshot(path) or {}  # keep areas from an earlier save today that this one lacks
    snapshot.update({
        "format": SNAPSHOT_FORMAT,
        "cinemetric_version": VERSION,
        "date": today.isoformat(),
        "saved_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "server_name": server_name(reports) or snapshot.get("server_name") or "",
    })
    for area, block in blocks.items():
        snapshot[area] = block["area"]
    for folder in (data_dir(), snapshots_dir()):
        ensure_private_dir(folder)
    write_private(path, json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")))
    prune(today)
    return today.isoformat()


def prune(today=None):
    """Delete snapshot files dated more than KEEP_DAYS days ago, in every server's folder."""
    today = today or datetime.date.today()
    try:
        servers = os.listdir(snapshots_dir())
    except OSError:
        return
    for server_id in servers:
        if not SERVER_ID.match(server_id):
            continue
        for day, path in snapshot_files(server_id):
            if (today - day).days > KEEP_DAYS:
                try:
                    os.remove(path)
                except OSError:
                    pass  # gone already, or not ours to remove


def server_name(reports):
    for area in ("health", "library", "sharing"):
        report = reports.get(area)
        if isinstance(report, dict):
            name = (report.get("server") or {}).get("name") if isinstance(report.get("server"), dict) else None
            if name:
                return clean(name)
    return None


# ---------------------------------------------------------------- running the reports

def run_source(name, since):
    folder, script, extra = SOURCES[name]
    path = os.path.join(SKILLS_DIR, folder, "scripts", script)
    if not os.path.exists(path):
        return name, None, f"the {folder} script is missing"
    command = [sys.executable, path, *extra]
    if since:
        command += ["--since", str(since)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=SCRIPT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return name, None, f"{folder} took longer than {SCRIPT_TIMEOUT_SECONDS // 60} minutes"
    if proc.returncode != 0:
        errors = [line[7:] for line in proc.stderr.splitlines() if line.startswith("error: ")]
        return name, None, errors[-1] if errors else f"{folder} failed"
    try:
        return name, json.loads(proc.stdout), None
    except ValueError:
        return name, None, f"{folder} produced unreadable output"


def collect(since):
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        results = list(pool.map(lambda name: run_source(name, since), SOURCES))
    reports = {name: payload for name, payload, _ in results if payload is not None}
    errors = {name: err for name, _, err in results if err}
    if len(errors) == len(SOURCES):
        raise ChangesError(next(iter(errors.values())))
    return reports, errors


def cmd_changes(args):
    reports, errors = collect(args.since)
    try:
        saved = save_snapshot(reports)
    except OSError as exc:
        saved = None
        print(f"warning: couldn't save today's snapshot: {exc.__class__.__name__}", file=sys.stderr)
    result = {"cinemetric_version": VERSION, "server": server_name(reports), "snapshot_saved": saved}
    for area in SOURCES:
        report = reports.get(area)
        result[area] = report.get("since_snapshot") if isinstance(report, dict) else None
    result["sections_missing"] = errors
    return result


def cmd_save(args):
    raw = sys.stdin.read(SNAPSHOT_MAX_BYTES + 1)
    if len(raw) > SNAPSHOT_MAX_BYTES:
        raise ChangesError("The reports given to save are too large.")
    try:
        reports = json.loads(raw)
    except (ValueError, RecursionError):
        raise ChangesError("The reports given to save weren't valid JSON.") from None
    if not isinstance(reports, dict):
        raise ChangesError("The reports given to save must be a JSON object.")
    try:
        return {"snapshot_saved": save_snapshot(reports)}
    except OSError as exc:
        raise ChangesError(f"Couldn't save the snapshot: {exc.__class__.__name__}") from None


def cmd_list(args):
    servers = []
    try:
        folders = sorted(os.listdir(snapshots_dir()))
    except OSError:
        folders = []
    for server_id in folders:
        files = snapshot_files(server_id)
        if not files:
            continue
        name = next((d.get("server_name") for d in (read_snapshot(p) for _, p in files) if d), None)
        servers.append({"server": name or "unknown server", "snapshots": len(files),
                        "oldest": files[-1][0].isoformat(), "newest": files[0][0].isoformat()})
    return {"folder": snapshots_dir(), "servers": servers}


def cmd_forget(args):
    folder = snapshots_dir()
    count = 0
    for _, _, names in os.walk(folder):
        count += len(names)
    if os.path.lexists(folder):
        if os.path.islink(folder) or not os.path.isdir(folder):
            os.remove(folder)
        else:
            shutil.rmtree(folder)
    return {"files_removed": count}


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="What changed on a Plex server since the last snapshot (JSON output).")
    parser.add_argument("--since", type=int, help="compare with a snapshot at least this many days old (1-90)")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("save", help="save a snapshot from reports given as JSON on stdin")
    sub.add_parser("list", help="list saved snapshots")
    sub.add_parser("forget", help="delete every saved snapshot")
    args = parser.parse_args()
    if args.since is not None:
        args.since = max(1, min(args.since, KEEP_DAYS))

    commands = {"save": cmd_save, "list": cmd_list, "forget": cmd_forget}
    try:
        result = commands.get(args.command, cmd_changes)(args)
    except ChangesError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    json.dump(result, sys.stdout, indent=1, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
