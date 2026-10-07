"""The mods find Cinemetric's files the same way the scripts do (openspec/specs/testing/spec.md).

The read-only guard (hooks/guard.ts) works out where the settings file is so it can protect it, and
the status line (hooks/status-line.tsx) finds the snapshots the scripts save. Both are TypeScript, so
they can't call the scripts' helpers. These tests run the scripts' own helpers with made-up folders
and check the hooks build each path from the same pieces.

The settings file's full path is never written out here: the guard rightly refuses anything that
names it, so the expected text is built from the scripts' answers.
"""

import os
import re
from unittest import mock

from helpers import ROOT, OfflineTestCase, load_script

HOOKS = os.path.join(ROOT, "plugins", "cinemetric", "hooks")
BASE = os.sep + "made-up-base"

setup = load_script("setup")      # writes the settings file
changes = load_script("changes")  # saves the snapshots


def hook_source(name):
    with open(os.path.join(HOOKS, name), encoding="utf-8") as fh:
        return fh.read()


def function_source(source, name):
    """The text of one TypeScript function, from its name to the closing brace at line start."""
    match = re.search(r"function " + name + r"\(.*?\n}\n", source, re.S)
    assert match, f"no function {name} found"
    return match.group(0)


def tail(path, base):
    """The part of a path after its base folder, with forward slashes like the hooks use."""
    assert path.startswith(base), (path, base)
    return path[len(base):].replace(os.sep, "/")


def answer(helper, env, nt=False):
    """Run a script helper with only the given environment variables (and a made-up home)."""
    env = dict(env)
    env.setdefault("HOME", BASE + "-home")
    with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(os, "name", "nt" if nt else os.name):
        return helper()


def regex_source(source, name):
    match = re.search(r"export const " + name + r" = /(.+)/\n", source)
    assert match, f"no {name} pattern found"
    return match.group(1)


class SettingsFile(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.guard = function_source(hook_source("guard.ts"), "settingsPath")

    def test_config_folder_variable(self):
        path = answer(setup.config_path, {"XDG_CONFIG_HOME": BASE})
        self.assertIn("XDG_CONFIG_HOME", self.guard)
        self.assertIn("${xdg}" + tail(path, BASE), self.guard, "guard.ts")

    def test_home_folder(self):
        home = BASE + "-home"
        path = answer(setup.config_path, {"HOME": home})
        self.assertIn("${home}" + tail(path, home), self.guard, "guard.ts")


class DataFolder(OfflineTestCase):
    def setUp(self):
        super().setUp()
        status_line = hook_source("status-line.tsx")
        self.data = function_source(status_line, "dataFolder")
        self.snapshots = function_source(status_line, "newestSnapshot")

    def test_override(self):
        self.assertEqual(answer(changes.data_dir, {"CINEMETRIC_DATA_DIR": BASE}), BASE)
        self.assertIn("CINEMETRIC_DATA_DIR", self.data)
        self.assertIn("if (override) return override", self.data)

    def test_data_folder_variable(self):
        path = answer(changes.data_dir, {"XDG_DATA_HOME": BASE})
        self.assertIn("XDG_DATA_HOME", self.data)
        self.assertIn("${xdg}" + tail(path, BASE), self.data, "status-line.tsx")

    def test_home_folder(self):
        home = BASE + "-home"
        path = answer(changes.data_dir, {"HOME": home})
        self.assertIn("${home}" + tail(path, home), self.data, "status-line.tsx")

    def test_windows_local_app_data(self):
        path = answer(changes.data_dir, {"LOCALAPPDATA": BASE}, nt=True)
        self.assertIn("LOCALAPPDATA", self.data)
        self.assertIn("${local}" + tail(path, BASE), self.data, "status-line.tsx")

    def test_windows_home_folder(self):
        home = BASE + "-home"
        path = answer(changes.data_dir, {"HOME": home}, nt=True)
        self.assertIn("${home}" + tail(path, home), self.data, "status-line.tsx")

    def test_snapshots_folder(self):
        path = answer(changes.snapshots_dir, {"CINEMETRIC_DATA_DIR": BASE})
        self.assertIn("${data}" + tail(path, BASE), self.snapshots, "status-line.tsx")


class SnapshotNames(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.rules = hook_source("status-line-rules.ts")

    def test_server_folder_pattern(self):
        self.assertEqual(regex_source(self.rules, "SERVER_FOLDER"), changes.SERVER_ID.pattern)

    def test_snapshot_file_pattern(self):
        self.assertEqual(regex_source(self.rules, "SNAPSHOT_FILE"), changes.SNAPSHOT_NAME.pattern)
