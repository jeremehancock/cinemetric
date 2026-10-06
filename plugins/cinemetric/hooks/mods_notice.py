"""Cinemetric: tell the user when their Claude Code is too old to run Cinemetric's mods.

Runs as a SessionStart settings hook when a session starts. On Claude Code 2.1.260 and newer the
mods run and set CINEMETRIC_MODS_ACTIVE before this script starts, so it shows nothing. On older
versions nothing sets it, so the script shows a short notice, at most once a day. Any problem ends
the script quietly: a missed notice is better than an error at startup.

See openspec/specs/mods/spec.md.
"""

import datetime
import json
import os
import sys

MODS_VERSION = "2.1.260"

NOTICE = (
    "Cinemetric's mods (like the read-only guard) need Claude Code " + MODS_VERSION + " or newer. "
    "Every Cinemetric skill still works. Run `claude update` to get the mods."
)

CONTEXT = (
    "Cinemetric's mods, including the read-only guard and the /cinemetric-mods command, are not "
    "running in this session because this Claude Code is older than " + MODS_VERSION + ". "
    "Cinemetric's skills work normally. Updating Claude Code (claude update) turns the mods on."
)


def data_dir():
    if os.environ.get("CINEMETRIC_DATA_DIR"):
        return os.environ["CINEMETRIC_DATA_DIR"]
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "cinemetric")


def notice_path():
    return os.path.join(data_dir(), "mods-notice.json")


def read_hook_input(stream):
    try:
        data = json.loads(stream.read() or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def shown_today(path, today):
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return False
    return isinstance(saved, dict) and saved.get("last_shown") == today


def remember(path, today):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"last_shown": today}, f)


def notice(stdin, today):
    """The hook's output as a dict, or None when nothing should be shown."""
    if os.environ.get("CINEMETRIC_MODS_ACTIVE"):
        return None
    if read_hook_input(stdin).get("source", "startup") != "startup":
        return None
    path = notice_path()
    if shown_today(path, today):
        return None
    remember(path, today)
    return {
        "systemMessage": NOTICE,
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": CONTEXT},
    }


def main():
    try:
        output = notice(sys.stdin, datetime.date.today().isoformat())
    except Exception:
        return 0
    if output is not None:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
