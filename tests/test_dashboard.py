"""dashboard (openspec/specs/dashboard/spec.md) and its page safety rules.

The dashboard normally runs the other report scripts as separate programs. Those programs wouldn't
be covered by this test run's network block, so these tests never start them: collect() and
run_source() are tested with their inputs replaced.
"""

import argparse
import json
import os
import stat
import subprocess
from unittest import mock

from helpers import OfflineTestCase, load_script

db = load_script("dashboard")

EVIL = '<script>alert("x")</script>'
EVIL_ATTR = '" onmouseover="steal()'


def sample_data():
    """Reports in the shape the three scripts print, with hostile text wherever text can appear."""
    health = {
        "server": {"name": EVIL, "version": EVIL_ATTR,
                   "update": {"update_available": True, "available_version": EVIL},
                   "remote_access": {"state": EVIL}},
        "worth_a_look": [
            {"kind": "update_available", "version": EVIL},
            {"kind": "remote_access_not_working", "state": EVIL},
            {"kind": "scheduled_scans_not_running", "libraries": [EVIL]},
            {"kind": "important_maintenance_disabled", "tasks": [EVIL]},
        ],
    }
    watch = {
        "source": "tautulli", "period_days": 30,
        "totals": {"plays": 3, "active_users": 1, "watch_hours": 2.0},
        "trend": {"earlier_half_plays": 1, "recent_half_plays": 2},
        "plays_by_type": {EVIL: 3},
        "daily": [{"date": EVIL, "plays": 3, "hours": 2.0}, {"date": "2026-09-02", "plays": 0}],
        "top_shows": [{"title": EVIL, "plays": 3, "hours": 1.0}],
        "top_movies": [{"title": EVIL_ATTR, "plays": 1}],
        "top_users": [{"user": "alex-test" + EVIL, "plays": 3}],
        "top_platforms": [{"platform": EVIL, "plays": 1}],
        "recent_plays": [{"when": "2026-09-01 20:00" + EVIL, "user": "alex-test" + EVIL_ATTR, "title": EVIL}],
    }
    library = {
        "server": {"name": EVIL, "version": EVIL},
        "totals": {"size_gb": 10.0, "files": 3},
        "libraries": [{
            "name": EVIL, "counts": {"movies": 3},
            "media": {"size_gb": 10.0, "resolution": {"4K": 1, EVIL: 2}, "unavailable_files": 1},
            "housekeeping": {"unmatched_count": 2},
            "recently_added": [{"title": EVIL, "added": "2026-09-01" + EVIL}],
        }],
    }
    return {"library": library, "health": health, "watch": watch}


def page(data, errors=None, hide_names=False):
    return db.full_page(*db.render(data, errors or {}, hide_names))


class PageSafety(OfflineTestCase):
    def test_every_report_value_is_escaped(self):
        html = page(sample_data())
        self.assertNotIn("<script", html)
        self.assertNotIn('onmouseover="', html)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;", html)

    def test_error_reasons_are_escaped(self):
        html = page({}, {"library": EVIL, "health": EVIL, "watch": EVIL})
        self.assertNotIn("<script", html)
        self.assertEqual(html.count("&lt;script&gt;"), 3)

    def test_page_blocks_scripts_and_outside_requests(self):
        html = page(sample_data())
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("default-src 'none'", html)
        self.assertNotIn("http://", html.replace("http://www.w3.org", ""))

    def test_hidden_names_leave_out_viewers(self):
        html = page(sample_data(), hide_names=True)
        self.assertNotIn("alex-test", html)
        self.assertNotIn("Top viewers", html)
        self.assertIn("alex-test", page(sample_data(), hide_names=False))

    def test_escape_helper(self):
        self.assertEqual(db.e('<a href="x">\'&'), "&lt;a href=&quot;x&quot;&gt;&#x27;&amp;")
        self.assertEqual(db.e(None), "")


# ---------------------------------------------------------------- rules

class Rules(OfflineTestCase):
    def test_attention_items(self):
        health = {"worth_a_look": [
            {"kind": "update_available", "version": "1.41"},
            {"kind": "remote_access_not_working", "state": "failed"},
            {"kind": "automatic_scans_off"},
            {"kind": "high_cpu", "average_pct": 95},  # shown elsewhere, not as an attention item
        ]}
        library = {"libraries": [
            {"media": {"unavailable_files": 2}, "housekeeping": {"unmatched_count": 1}},
            {"media": {"unavailable_files": 1}},
        ]}
        items = db.attention_items(health, library)
        self.assertEqual([(level, title) for level, title, _ in items], [
            ("warning", "Plex update available"),
            ("critical", "Remote access isn't working"),
            ("warning", "Automatic library scans are off"),
            ("warning", "3 files Plex can't find"),
            ("warning", "1 unmatched item"),
        ])

    def test_attention_items_with_missing_reports(self):
        self.assertEqual(db.attention_items(None, None), [])

    def test_overall_status(self):
        health = {"server": {"name": "Test Server"}}
        self.assertEqual(db.overall_status(None, []), ("unknown", "Health unknown"))
        self.assertEqual(db.overall_status(health, []), ("good", "Healthy"))
        self.assertEqual(db.overall_status(health, [("warning", "a", "b")]), ("warning", "Mostly fine"))
        self.assertEqual(db.overall_status(health, [("warning", "a", "b"), ("critical", "c", "d")]),
                         ("critical", "Needs attention"))

    def test_nice_step(self):
        cases = {0: 1, 3: 1, 7: 2, 37: 10, 100: 25, 1000: 250, 9999: 2500}
        for peak, expected in cases.items():
            with self.subTest(peak=peak):
                self.assertEqual(db.nice_step(peak), expected)

    def test_nice_step_always_fits_the_tallest_bar(self):
        for peak in range(0, 5001):
            step = db.nice_step(peak)
            self.assertIsInstance(step, int)
            self.assertGreaterEqual(step * 4, peak, peak)


# ---------------------------------------------------------------- collecting

def finished(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class Collecting(OfflineTestCase):
    def test_run_source_reads_json(self):
        with mock.patch.object(db.subprocess, "run", return_value=finished(stdout='{"totals": {}}')):
            self.assertEqual(db.run_source("library"), ("library", {"totals": {}}, None))

    def test_run_source_keeps_only_the_error_line(self):
        reply = finished(1, stderr="reading library: Movies\nerror: NOT_CONFIGURED: not connected\n")
        with mock.patch.object(db.subprocess, "run", return_value=reply):
            self.assertEqual(db.run_source("health"), ("health", None, "NOT_CONFIGURED: not connected"))

    def test_run_source_problems(self):
        cases = [
            (finished(1, stderr="Traceback ..."), "server-health failed"),
            (finished(0, stdout="not json"), "server-health produced unreadable output"),
            (subprocess.TimeoutExpired(cmd="x", timeout=1), "server-health took longer than 30 minutes"),
        ]
        for outcome, message in cases:
            with self.subTest(message=message):
                kwargs = {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
                with mock.patch.object(db.subprocess, "run", **kwargs):
                    self.assertEqual(db.run_source("health")[2], message)

    def test_run_source_missing_script(self):
        with mock.patch.object(db, "SKILLS_DIR", self.tmp), \
                mock.patch.object(db.subprocess, "run", side_effect=AssertionError("should not run")):
            self.assertEqual(db.run_source("watch")[2], "the watch-activity script is missing")

    def test_collect_keeps_going_when_one_source_fails(self):
        results = {"library": {"totals": {}}, "health": None, "watch": {"totals": {}}}
        fake = lambda name: (name, results[name], "HTTP 500" if results[name] is None else None)
        with mock.patch.object(db, "run_source", fake):
            data, errors = db.collect()
        self.assertEqual(errors, {"health": "HTTP 500"})
        self.assertEqual(data["library"], {"totals": {}})

    def test_collect_not_configured(self):
        fake = lambda name: (name, None, "NOT_CONFIGURED: Cinemetric is not connected")
        with mock.patch.object(db, "run_source", fake):
            with self.assertRaises(db.DashboardError) as caught:
                db.collect()
        self.assertTrue(str(caught.exception).startswith("NOT_CONFIGURED"))

    def test_collect_nothing_worked(self):
        fake = lambda name: (name, None, "HTTP 500")
        with mock.patch.object(db, "run_source", fake):
            with self.assertRaises(db.DashboardError) as caught:
                db.collect()
        self.assertIn("Nothing could be collected", str(caught.exception))

    def test_failed_section_shows_a_note(self):
        data = sample_data()
        data["library"] = None
        html = page(data, {"library": "Plex returned HTTP 500"})
        self.assertIn("Couldn't load the library report: Plex returned HTTP 500", html)


# ---------------------------------------------------------------- files

def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class BuildingAndSaving(OfflineTestCase):
    def build(self, hide_names=None):
        with mock.patch.object(db, "collect", return_value=(sample_data(), {})):
            return db.build(argparse.Namespace(output=db.default_output(), hide_names=hide_names))

    def test_page_lands_in_the_data_folder(self):
        result = self.build()
        expected = os.path.join(self.tmp, "data", "cinemetric", "dashboard.html")
        self.assertEqual(result["output"], expected)
        self.assertTrue(os.path.exists(expected))
        self.assertEqual(result["ask"], ["destination"])
        if os.name == "posix":
            self.assertEqual(mode(expected), 0o600)
            self.assertEqual(mode(os.path.dirname(expected)), 0o700)

    def test_hide_names_is_remembered(self):
        self.assertTrue(self.build(hide_names=True)["names_hidden"])
        result = self.build()
        self.assertTrue(result["names_hidden"])
        with open(result["output"], encoding="utf-8") as fh:
            self.assertNotIn("alex-test", fh.read())
        if os.name == "posix":
            self.assertEqual(mode(db.state_path()), 0o600)
        self.assertFalse(self.build(hide_names=False)["names_hidden"])

    def test_destination_is_saved(self):
        db.cmd_destination(argparse.Namespace(choice="both"))
        self.assertEqual(self.build()["destination"], "both")
        self.assertEqual(self.build()["ask"], [])

    def test_online_page_link_must_be_a_claude_page(self):
        for url in ("https://claude.ai/artifact/abc-123", "https://claude.ai/code/artifact/abc-123"):
            with self.subTest(url=url):
                self.assertEqual(db.cmd_online_page(argparse.Namespace(url=url, forget=False))["online_page"], url)
        for url in ("https://evil.test/artifact/abc", "https://claude.ai/artifact/abc?x=1",
                    "http://claude.ai/artifact/abc", "https://claude.ai.evil.test/artifact/abc"):
            with self.subTest(url=url):
                with self.assertRaises(db.DashboardError):
                    db.cmd_online_page(argparse.Namespace(url=url, forget=False))

    def test_online_page_can_be_forgotten(self):
        db.cmd_online_page(argparse.Namespace(url="https://claude.ai/artifact/abc", forget=False))
        self.assertIsNone(db.cmd_online_page(argparse.Namespace(url=None, forget=True))["online_page"])

    def test_tampered_state_is_ignored(self):
        os.makedirs(os.path.dirname(db.state_path()), exist_ok=True)
        with open(db.state_path(), "w", encoding="utf-8") as fh:
            json.dump({"destination": "somewhere", "online_page": "https://evil.test/"}, fh)
        result = self.build()
        self.assertIsNone(result["destination"])
        self.assertIsNone(result["online_page"])
