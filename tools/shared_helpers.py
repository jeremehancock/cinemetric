#!/usr/bin/env python3
"""Check and copy the helpers that every skill script keeps its own copy of.

Each skill's script runs on its own, so shared helpers (config loading, address checks, the Plex
client, text cleaning, snapshot reading and so on) are copied into every script that needs them.
This tool keeps those copies the same. The list of shared helpers below is the one place that says
which copies must match; tests/test_shared_helpers.py runs the same check on every test run.

    python3 tools/shared_helpers.py
        Check every copy. Prints each helper whose copies differ, and which scripts differ.

    python3 tools/shared_helpers.py copy NAME --from SKILL
        Copy helper NAME from SKILL's script into every other script that has a copy. Use it after
        changing a shared helper in one script. NAME can be a function, class or constant, or one
        method of a class written as Class.method (for example PlexClient.get).

The only thing allowed to differ between copies is the name a script gives itself in requests to
Plex ("cinemetric-library-report", "cinemetric-unwatched" and so on). Copying fills in each
script's own name.

This is a development tool: it isn't part of the plugin and is never shipped to users.
"""

import argparse
import ast
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "plugins", "cinemetric", "skills")

# Every shared helper whose copies must match, with the scripts whose copy is allowed to be
# different and why. A script that doesn't define the helper at all is simply skipped.
SHARED = {
    # Config and addresses
    "config_path": {"setup": "setup also writes the file, so it builds the path from config_dir()"},
    "read_config_file": {},
    "load_config": {
        "library-report": "Plex only, so it returns just the Plex settings",
        "server-health": "Plex only, so it returns just the Plex settings",
        "users-and-shares": "needs Plex even when Tautulli is set up",
    },
    "validate_url": {},
    "looks_local": {},
    # Requests
    "ReportError": {},
    "_NoRedirect": {"setup": "raises SetupError, and setup talks to plex.tv as well as the server"},
    "build_opener": {},
    "fetch_json": {},
    "PlexClient.__init__": {},
    "PlexClient.get": {
        "server-health": "accepts empty replies and endpoints (like /butler) without MediaContainer",
    },
    "TautulliClient": {},
    "media_deletion_allowed": {},
    "LIBRARY_PAGE_SIZE": {},
    "TAUTULLI_PAGE_SIZE": {},
    "DETAIL_BATCH": {},
    "get_details": {},
    # Text and numbers from the server
    "MAX_TITLE_LENGTH": {},
    "clean": {},
    "clean_tree": {},
    "as_int": {},
    "as_count": {},
    "gb": {},
    "pick_person": {},
    "MAX_NAMES_LISTED": {},
    # Saved files and snapshots
    "data_dir": {},
    "ensure_private_dir": {},
    "SERVER_ID": {},
    "SNAPSHOT_NAME": {},
    "SNAPSHOT_FORMAT": {},
    "SNAPSHOT_MAX_BYTES": {},
    "snapshots_dir": {},
    "snapshot_files": {},
    "load_snapshot": {},
    "read_snapshot": {},
    "choose_snapshot": {},
}

CLIENT_NAME = re.compile(r'"cinemetric-[a-z-]+"')


def scripts():
    """{skill: path of its script} for every skill folder with a script."""
    found = {}
    for path in sorted(glob.glob(os.path.join(SKILLS_DIR, "*", "scripts", "*.py"))):
        found[path.split(os.sep)[-3]] = path
    return found


def find(source, name):
    """(first line, last line) of a top-level definition or Class.method in source, or None."""
    outer, _, method = name.partition(".")
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            found = node.name
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            found = node.targets[0].id
        else:
            continue
        if found != outer:
            continue
        if not method:
            return node.lineno, node.end_lineno
        for child in getattr(node, "body", []):
            if isinstance(child, ast.FunctionDef) and child.name == method:
                return child.lineno, child.end_lineno
    return None


def read_copy(path, name):
    """The helper's source text in one script, or None if the script doesn't have it."""
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    where = find(source, name)
    if where is None:
        return None
    lines = source.splitlines(True)
    return "".join(lines[where[0] - 1:where[1]])


def comparable(text):
    """The copy with the script's own Plex client name taken out, so copies can be compared."""
    return CLIENT_NAME.sub('"cinemetric-<skill>"', text)


def copies(name):
    """{skill: comparable text} for every script that has the helper and must match."""
    allowed_to_differ = SHARED[name]
    found = {}
    for skill, path in scripts().items():
        if skill in allowed_to_differ:
            continue
        text = read_copy(path, name)
        if text is not None:
            found[skill] = comparable(text)
    return found


def problems():
    """One line per shared helper whose copies differ."""
    lines = []
    for name in SHARED:
        groups = {}
        for skill, text in copies(name).items():
            groups.setdefault(text, []).append(skill)
        if len(groups) > 1:
            versions = sorted(groups.values(), key=len, reverse=True)
            described = "; ".join(", ".join(skills) for skills in versions)
            lines.append(f"{name} has {len(groups)} different versions: {described}")
    return lines


def copy(name, source_skill):
    """Copy one helper from source_skill's script into every other script that has a copy."""
    if name not in SHARED:
        raise SystemExit(f"error: {name} isn't in the SHARED list in tools/shared_helpers.py.")
    paths = scripts()
    if source_skill not in paths:
        raise SystemExit(f"error: no skill named {source_skill}.")
    template = read_copy(paths[source_skill], name)
    if template is None:
        raise SystemExit(f"error: {source_skill} has no {name}.")
    template = comparable(template)
    changed = []
    for skill, path in paths.items():
        if skill == source_skill or skill in SHARED[name]:
            continue
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        where = find(source, name)
        if where is None:
            continue
        lines = source.splitlines(True)
        old = "".join(lines[where[0] - 1:where[1]])
        new = template.replace('"cinemetric-<skill>"', f'"cinemetric-{skill}"')
        if old.endswith("\n") and not new.endswith("\n"):
            new += "\n"
        if old == new:
            continue
        lines[where[0] - 1:where[1]] = [new]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("".join(lines))
        changed.append(skill)
    return changed


def main():
    parser = argparse.ArgumentParser(description="Check or copy the helpers shared by the skill scripts.")
    sub = parser.add_subparsers(dest="command")
    copy_parser = sub.add_parser("copy", help="copy one helper from a script into the others")
    copy_parser.add_argument("name", help="the helper, for example clean or PlexClient.get")
    copy_parser.add_argument("--from", dest="source", required=True, metavar="SKILL",
                             help="the skill whose copy is the right one, for example episode-gaps")
    args = parser.parse_args()

    if args.command == "copy":
        changed = copy(args.name, args.source)
        if changed:
            print(f"Copied {args.name} from {args.source} into: {', '.join(changed)}")
        else:
            print(f"Every copy of {args.name} already matches {args.source}.")
        return 0

    found = problems()
    for line in found:
        print(line)
    if found:
        print("\nFix with: python3 tools/shared_helpers.py copy NAME --from SKILL", file=sys.stderr)
        return 1
    print(f"All {len(SHARED)} shared helpers match in every script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
