"""Cinemetric: tell the user when Cinemetric's mods aren't running in this session.

Runs as a SessionStart settings hook when a session starts. When the mods run they set
CINEMETRIC_MODS_ACTIVE before this script starts, so it shows nothing. Otherwise nothing sets it,
either because Claude Code is older than 2.1.260 or because the session started with the feature
mods use switched off, so the script shows a short notice with both fixes, at most once a day. Any
problem ends the script quietly: a missed notice is better than an error at startup.

See openspec/specs/mods/spec.md.
"""

import datetime
import json
import os
import sys

MODS_VERSION = "2.1.260"

ENABLE_SETTING = "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS"

NOTICE = (
    "Cinemetric's mods (like the read-only guard) aren't running in this session. They need Claude "
    "Code " + MODS_VERSION + " or newer: run `claude update`. Already up to date? Add "
    "\"" + ENABLE_SETTING + "\": \"1\" to the \"env\" section of ~/.claude/settings.json and start a "
    "new session. Every Cinemetric skill still works."
)

CONTEXT = (
    "Cinemetric's mods, including the read-only guard and the /cinemetric-mods command, are not "
    "running in this session. Either this Claude Code is older than " + MODS_VERSION + " (claude "
    "update fixes it), or the session started with the feature mods use switched off (adding "
    "\"" + ENABLE_SETTING + "\": \"1\" to the \"env\" section of ~/.claude/settings.json and "
    "starting a new session fixes it). Cinemetric's skills work normally."
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
