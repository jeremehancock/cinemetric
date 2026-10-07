"""The startup notice shown when Cinemetric's mods aren't running (hooks/mods_notice.py)."""

import importlib.util
import io
import json
import os
import unittest
from unittest import mock

from helpers import ROOT, OfflineTestCase

NOTICE_SCRIPT = os.path.join(ROOT, "plugins", "cinemetric", "hooks", "mods_notice.py")


def load_notice():
    spec = importlib.util.spec_from_file_location("cinemetric_mods_notice", NOTICE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


notice_script = load_notice()


def hook_input(source="startup"):
    return io.StringIO(json.dumps({"hook_event_name": "SessionStart", "source": source}))


class ModsNotice(OfflineTestCase):
    def notice_file(self):
        return os.path.join(self.tmp, "data", "cinemetric", "mods-notice.json")

    def test_mods_not_running_gets_the_notice(self):
        output = notice_script.notice(hook_input(), "2026-10-06")
        self.assertIn("2.1.260", output["systemMessage"])
        self.assertIn("claude update", output["systemMessage"])
        self.assertIn("still works", output["systemMessage"])
        self.assertIn("CLAUDE_CODE_ENABLE_FUNCTION_HOOKS", output["systemMessage"])
        self.assertIn("~/.claude/settings.json", output["systemMessage"])
        context = output["hookSpecificOutput"]
        self.assertEqual(context["hookEventName"], "SessionStart")
        self.assertIn("not running", context["additionalContext"])
        self.assertIn("CLAUDE_CODE_ENABLE_FUNCTION_HOOKS", context["additionalContext"])

    def test_the_day_is_saved_in_the_data_folder(self):
        notice_script.notice(hook_input(), "2026-10-06")
        with open(self.notice_file(), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"last_shown": "2026-10-06"})

    def test_shown_at_most_once_a_day(self):
        self.assertIsNotNone(notice_script.notice(hook_input(), "2026-10-06"))
        self.assertIsNone(notice_script.notice(hook_input(), "2026-10-06"))
        self.assertIsNotNone(notice_script.notice(hook_input(), "2026-10-07"))

    def test_quiet_when_the_mods_are_running(self):
        with mock.patch.dict(os.environ, {"CINEMETRIC_MODS_ACTIVE": "1"}):
            self.assertIsNone(notice_script.notice(hook_input(), "2026-10-06"))
        self.assertFalse(os.path.exists(self.notice_file()))

    def test_quiet_on_resume_clear_and_compact(self):
        for source in ("resume", "clear", "compact"):
            self.assertIsNone(notice_script.notice(hook_input(source), "2026-10-06"), source)

    def test_missing_or_odd_input_counts_as_startup(self):
        self.assertIsNotNone(notice_script.notice(io.StringIO(""), "2026-10-06"))
        os.remove(self.notice_file())
        self.assertIsNotNone(notice_script.notice(io.StringIO("not json"), "2026-10-06"))

    def test_damaged_saved_day_is_ignored(self):
        os.makedirs(os.path.dirname(self.notice_file()))
        with open(self.notice_file(), "w", encoding="utf-8") as f:
            f.write("{broken")
        self.assertIsNotNone(notice_script.notice(hook_input(), "2026-10-06"))

    def test_data_folder_override(self):
        folder = os.path.join(self.tmp, "elsewhere")
        with mock.patch.dict(os.environ, {"CINEMETRIC_DATA_DIR": folder}):
            notice_script.notice(hook_input(), "2026-10-06")
        self.assertTrue(os.path.exists(os.path.join(folder, "mods-notice.json")))

    def test_main_prints_one_json_document(self):
        stdout = io.StringIO()
        with mock.patch("sys.stdin", hook_input()), mock.patch("sys.stdout", stdout):
            self.assertEqual(notice_script.main(), 0)
        self.assertIn("systemMessage", json.loads(stdout.getvalue()))

    def test_main_stays_quiet_on_an_error(self):
        stdout = io.StringIO()
        with mock.patch.object(notice_script, "remember", side_effect=OSError("read-only disk")), \
                mock.patch("sys.stdin", hook_input()), mock.patch("sys.stdout", stdout):
            self.assertEqual(notice_script.main(), 0)
        self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
