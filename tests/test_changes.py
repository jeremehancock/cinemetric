"""changes (openspec/specs/changes/spec.md) and the snapshot helper copied into every script that
reads snapshots (openspec/specs/conventions/spec.md "Reading snapshots", security "Snapshots are read
as data")."""

import argparse
import datetime
import io
import json
import os
import stat
import subprocess
import sys
from unittest import mock

from helpers import OfflineTestCase, TEST_SERVER_ID, load_script, snapshot_path, write_snapshot

ch = load_script("changes")
READERS = [("changes", ch), ("library-report", load_script("library-report")),
           ("server-health", load_script("server-health")), ("users-and-shares", load_script("users-and-shares"))]
TODAY = datetime.date.today()


def report(area_name, area, server_id=TEST_SERVER_ID, since=None):
    return {"server": {"name": "Test Server"}, "since_snapshot": since,
            "snapshot": {"server_id": server_id, "area": area}}


def reports(server_id=TEST_SERVER_ID):
    return {"library": report("library", {"1": {"name": "Movies", "items": {"101": "Heat (1995)"}}}, server_id),
            "health": report("health", {"version": "1.41.0"}, server_id),
            "sharing": report("sharing", {"people": []}, server_id)}


def saved(home, days_ago=0):
    with open(snapshot_path(home, TODAY - datetime.timedelta(days=days_ago)), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- the helper, in every copy

class SnapshotHelperEveryCopy(OfflineTestCase):
    def choose(self, module, area="health", since=None, server_id=TEST_SERVER_ID):
        found = module.choose_snapshot(server_id, area, since)
        return found and found[1]["days_ago"]

    def test_uses_newest_earlier_day(self):
        for days in (0, 3, 9):
            write_snapshot(self.tmp, days, health={"version": f"v{days}"})
        for name, module in READERS:
            with self.subTest(script=name):
                area, when = module.choose_snapshot(TEST_SERVER_ID, "health")
                self.assertEqual((area, when["days_ago"]), ({"version": "v3"}, 3))
                self.assertEqual(when["snapshot_date"], (TODAY - datetime.timedelta(days=3)).isoformat())

    def test_since_days(self):
        for days in (1, 6, 8, 20):
            write_snapshot(self.tmp, days, health={})
        for name, module in READERS:
            with self.subTest(script=name):
                self.assertEqual(self.choose(module, since=7), 8)
                self.assertEqual(self.choose(module, since=30), 20)  # none that old: the oldest

    def test_skips_snapshots_without_the_area(self):
        write_snapshot(self.tmp, 1, health={})
        write_snapshot(self.tmp, 7, health={}, sharing={"people": []})
        for name, module in READERS:
            with self.subTest(script=name):
                self.assertEqual(self.choose(module, area="sharing"), 7)

    def test_other_server(self):
        write_snapshot(self.tmp, 1, server_id="otherserver", health={})
        for name, module in READERS:
            with self.subTest(script=name):
                self.assertIsNone(module.choose_snapshot(TEST_SERVER_ID, "health"))

    def test_skips_bad_files(self):
        good = write_snapshot(self.tmp, 9, health={"version": "good"})
        write_snapshot(self.tmp, 1, raw='{"format": 1, "health": {"vers')       # cut off halfway
        write_snapshot(self.tmp, 2, raw='["not", "an", "object"]')
        write_snapshot(self.tmp, 3, raw=json.dumps({"format": 2, "health": {}}))  # unknown format
        write_snapshot(self.tmp, 4, raw=b"\xff\xfe".decode("latin-1"))         # not valid JSON
        write_snapshot(self.tmp, 5, health={"padding": "x" * 500})                # too large
        link = write_snapshot(self.tmp, 6, health={})
        os.remove(link)
        os.symlink(good, link)                                                   # a link is skipped
        os.makedirs(os.path.join(os.path.dirname(good), "2026-13-45.json"))      # impossible date
        for name, module in READERS:
            with self.subTest(script=name), mock.patch.object(module, "SNAPSHOT_MAX_BYTES", 300):
                self.assertEqual(self.choose(module), 9)

    def test_strange_server_ids(self):
        write_snapshot(self.tmp, 1, health={})
        for name, module in READERS:
            for bad in ("../" + TEST_SERVER_ID, "a/b", "", None, "x" * 200):
                with self.subTest(script=name, server_id=bad):
                    self.assertEqual(module.snapshot_files(bad), [])

    def test_text_is_cleaned(self):
        title = "Evil\nTitle " + "x" * 500
        write_snapshot(self.tmp, 1, library={"1\n": {"items": {"5": title}}})
        for name, module in READERS:
            with self.subTest(script=name):
                area, _ = module.choose_snapshot(TEST_SERVER_ID, "library")
                [(key, lib)] = area.items()
                self.assertEqual(key, "1")
                self.assertTrue(lib["items"]["5"].startswith("Evil Title x"))
                self.assertEqual(len(lib["items"]["5"]), 120)

    def test_copies_are_identical(self):
        import inspect
        names = ("data_dir", "snapshots_dir", "snapshot_files", "clean_tree", "read_snapshot",
                 "choose_snapshot", "as_count")
        for name in names:
            first = inspect.getsource(getattr(ch, name))
            for script, module in READERS[1:]:
                with self.subTest(helper=name, script=script):
                    self.assertEqual(inspect.getsource(getattr(module, name)), first)


# ---------------------------------------------------------------- saving

class Saving(OfflineTestCase):
    def test_saves_a_private_file(self):
        self.assertEqual(ch.save_snapshot(reports()), TODAY.isoformat())
        data = saved(self.tmp)
        self.assertEqual((data["format"], data["date"], data["server_name"]), (1, TODAY.isoformat(), "Test Server"))
        self.assertEqual(data["health"], {"version": "1.41.0"})
        self.assertEqual(data["cinemetric_version"], ch.VERSION)
        if os.name == "posix":
            path = snapshot_path(self.tmp, TODAY)
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            for folder in (os.path.dirname(path), os.path.dirname(os.path.dirname(path)),
                           os.path.join(self.tmp, "data", "cinemetric")):
                self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o700, folder)

    def test_same_day_saves_merge(self):
        ch.save_snapshot(reports())
        evening = reports()
        del evening["sharing"]
        evening["health"]["snapshot"]["area"] = {"version": "1.42.0"}
        ch.save_snapshot(evening)
        data = saved(self.tmp)
        self.assertEqual(data["health"], {"version": "1.42.0"})
        self.assertEqual(data["sharing"], {"people": []})

    def test_strange_server_id_saves_nothing(self):
        for bad in ("../escape", "a/b", ""):
            with self.subTest(server_id=bad):
                self.assertIsNone(ch.save_snapshot(reports(server_id=bad)))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "data", "cinemetric", "snapshots")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "data", "escape")))

    def test_different_servers_save_nothing(self):
        mixed = reports()
        mixed["health"]["snapshot"]["server_id"] = "otherserver"
        self.assertIsNone(ch.save_snapshot(mixed))

    def test_nothing_to_save(self):
        self.assertIsNone(ch.save_snapshot({}))
        self.assertIsNone(ch.save_snapshot({"library": {"no": "snapshot"}}))

    def test_keeps_90_days(self):
        kept = write_snapshot(self.tmp, 90, health={})
        old = write_snapshot(self.tmp, 91, health={})
        other_server_old = write_snapshot(self.tmp, 200, server_id="otherserver", health={})
        notes = os.path.join(os.path.dirname(kept), "notes.txt")
        with open(notes, "w") as fh:
            fh.write("mine")
        ch.save_snapshot(reports())
        self.assertTrue(os.path.exists(kept))
        self.assertFalse(os.path.exists(old))
        self.assertFalse(os.path.exists(other_server_old))
        self.assertTrue(os.path.exists(notes))


# ---------------------------------------------------------------- commands

def no_subprocess(*args, **kwargs):
    raise AssertionError("save, list and forget must not run other scripts")


class Commands(OfflineTestCase):
    def run_main(self, *argv, stdin=""):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["changes.py", *argv]), \
                mock.patch.object(sys, "stdin", io.StringIO(stdin)), mock.patch.object(sys, "stdout", out), \
                mock.patch.object(subprocess, "run", no_subprocess):
            code = ch.main()
        return code, (json.loads(out.getvalue()) if code == 0 else None)

    def test_save_from_stdin(self):
        code, result = self.run_main("save", stdin=json.dumps(reports()))
        self.assertEqual((code, result), (0, {"snapshot_saved": TODAY.isoformat()}))
        self.assertEqual(saved(self.tmp)["sharing"], {"people": []})

    def test_save_refuses_bad_input(self):
        for text in ("not json", "[1, 2]"):
            with self.subTest(text=text):
                self.assertEqual(self.run_main("save", stdin=text)[0], 1)
        with mock.patch.object(ch, "SNAPSHOT_MAX_BYTES", 10):
            self.assertEqual(self.run_main("save", stdin=json.dumps(reports()))[0], 1)
        self.assertIn("error: ", self.stderr.getvalue())

    def test_list(self):
        write_snapshot(self.tmp, 1, health={})
        write_snapshot(self.tmp, 30, health={})
        code, result = self.run_main("list")
        self.assertEqual(result["servers"], [{
            "server": "Test Server", "snapshots": 2,
            "oldest": (TODAY - datetime.timedelta(days=30)).isoformat(),
            "newest": (TODAY - datetime.timedelta(days=1)).isoformat()}])

    def test_list_with_nothing_saved(self):
        self.assertEqual(self.run_main("list")[1]["servers"], [])

    def test_forget(self):
        write_snapshot(self.tmp, 1, health={})
        write_snapshot(self.tmp, 2, server_id="otherserver", health={})
        dashboard = os.path.join(self.tmp, "data", "cinemetric", "dashboard.html")
        with open(dashboard, "w") as fh:
            fh.write("page")
        code, result = self.run_main("forget")
        self.assertEqual(result, {"files_removed": 2})
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "data", "cinemetric", "snapshots")))
        self.assertTrue(os.path.exists(dashboard))


class DefaultRun(OfflineTestCase):
    def run_with(self, results, since=None):
        """Run cmd_changes with each report's (payload, error) given instead of running scripts."""
        with mock.patch.object(ch, "run_source", lambda name, s: (name, *results[name])):
            return ch.cmd_changes(argparse.Namespace(since=since))

    def test_normal_run(self):
        full = reports()
        for name in full:
            full[name]["since_snapshot"] = {"snapshot_date": "2026-01-01", "days_ago": 3, "area": name}
        result = self.run_with({name: (full[name], None) for name in full})
        self.assertEqual(result["snapshot_saved"], TODAY.isoformat())
        self.assertEqual(result["server"], "Test Server")
        self.assertEqual(result["sharing"]["area"], "sharing")
        self.assertEqual(result["sections_missing"], {})
        self.assertNotIn("snapshot", json.dumps(result).replace("snapshot_saved", "").replace("snapshot_date", ""))

    def test_first_run(self):
        result = self.run_with({name: (r, None) for name, r in reports().items()})
        self.assertEqual((result["library"], result["health"], result["sharing"]), (None, None, None))
        self.assertEqual(result["snapshot_saved"], TODAY.isoformat())

    def test_owner_only(self):
        r = reports()
        result = self.run_with({"library": (r["library"], None), "health": (r["health"], None),
                                "sharing": (None, "OWNER_ONLY: only the server owner ...")})
        self.assertIn("OWNER_ONLY", result["sections_missing"]["sharing"])
        self.assertEqual(result["snapshot_saved"], TODAY.isoformat())
        self.assertNotIn("sharing", saved(self.tmp))

    def test_not_configured(self):
        error = "NOT_CONFIGURED: Cinemetric is not connected"
        with self.assertRaises(ch.ChangesError) as caught:
            self.run_with({name: (None, error) for name in ch.SOURCES})
        self.assertTrue(str(caught.exception).startswith("NOT_CONFIGURED"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "data", "cinemetric", "snapshots")))

    def test_since_is_passed_on(self):
        commands = []

        def fake_run(command, **kwargs):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, json.dumps({}), "")

        with mock.patch.object(subprocess, "run", fake_run):
            ch.cmd_changes(argparse.Namespace(since=7))
        self.assertEqual(len(commands), 3)
        for command in commands:
            self.assertEqual(command[-3:], ["--snapshot-items", "--since", "7"])
        health = [c for c in commands if c[1].endswith("server_health.py")][0]
        self.assertIn("--stuck-wait", health)

    def test_since_is_limited(self):
        seen = []
        with mock.patch.object(sys, "argv", ["changes.py", "--since", "500"]), \
                mock.patch.object(ch, "cmd_changes", lambda a: seen.append(a.since) or {}), \
                mock.patch.object(sys, "stdout", io.StringIO()):
            ch.main()
        self.assertEqual(seen, [90])
