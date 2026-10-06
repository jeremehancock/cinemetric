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
    """Reports in the shape the four scripts print, with hostile text wherever text can appear."""
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
        "growth": {"added": EVIL, "gb": EVIL, "months": [{"month": EVIL, "added": 2, "gb": 4.0},
                                                         {"month": EVIL_ATTR, "added": 1, "gb": 1.0}]},
    }
    sharing = {
        "people": [
            {"name": "sam-test" + EVIL, "kind": "home", "status": "accepted", "libraries": "all",
             "last_played": "2026-09-30"},
            {"name": "riley-test" + EVIL_ATTR, "kind": "friend", "status": "accepted", "libraries": [EVIL],
             "last_played": None},
            {"name": "casey-test", "kind": EVIL, "status": "pending", "libraries": None, "last_played": None},
        ],
        "libraries": [{"title": EVIL, "shared_with_count": 2}],
        "totals": {"people": 3, "by_kind": {"home": 1, "friend": 2}},
        "worth_a_look": [
            {"kind": "inactive", "people": ["riley-test" + EVIL_ATTR], "days": 90},
            {"kind": "downloads_allowed", "people": ["riley-test" + EVIL_ATTR]},
            {"kind": "all_libraries", "people": ["sam-test" + EVIL]},
            {"kind": "old_pending_invite", "people": ["casey-test"], "days": 30},
            {"kind": "unused_library", "libraries": [EVIL], "days": 90},
        ],
    }
    unwatched = {
        "months": 6, "source": "tautulli", "history_since": "2021-12-19" + EVIL, "history_capped": True,
        "totals": {"unwatched": 2, "unwatched_gb": 80.0, "library_gb": 100.0, "unwatched_pct": EVIL,
                   "never_finished": 1, "never_finished_gb": 72.0},
        "libraries": [{
            "name": EVIL, "type": "movie", "items": 3, "unwatched": 2, "unwatched_gb": 80.0,
            "unwatched_pct": EVIL_ATTR, "never_finished": 1,
            "titles": [{"title": EVIL, "added": "2024-01-01" + EVIL, "gb": 72.0, "last_finished": None},
                       {"title": EVIL_ATTR, "added": "2023-01-01", "gb": 8.0, "last_finished": "2025-01-01" + EVIL}],
        }],
    }
    when = {"snapshot_date": "2026-09-29" + EVIL, "days_ago": 7}
    library["since_snapshot"] = dict(when, libraries=[
        {"name": EVIL, "type": "movie", "status": "same", "renamed_from": EVIL_ATTR,
         "added_count": 1, "added": [EVIL], "became_unavailable_count": 1, "became_unavailable": [EVIL_ATTR]},
        {"name": EVIL, "type": "show", "status": "same",
         "episodes_added_count": 2, "episodes_added": [{"show": EVIL, "count": 2}]},
        {"name": EVIL_ATTR, "type": "movie", "status": "new"},
    ], totals={"added": 1, "removed": 0, "episodes_added": 2, "episodes_removed": 0, "became_unavailable": 1,
               "available_again": 0, "size_gb_change": 12.5})
    health["since_snapshot"] = dict(when, changes=[{"kind": "version", "from": EVIL, "to": EVIL_ATTR},
                                                   {"kind": "remote_access", "from": EVIL, "to": EVIL}])
    sharing["since_snapshot"] = dict(when, added=[{"name": "sam-test" + EVIL, "kind": "friend"}],
                                     removed=[{"name": "alex-test" + EVIL_ATTR}], accepted=["casey-test" + EVIL],
                                     libraries_changed=[{"name": "riley-test", "gained": [EVIL], "lost": []}],
                                     downloads_changed=[{"name": "riley-test" + EVIL, "to": True}],
                                     email_invites_change=1)
    episode_gaps = {
        "limits": EVIL, "totals": {"shows": 3, "shows_with_gaps": 1, "missing_episodes": 2,
                                   "unavailable_episodes": 1, "missing_seasons": 1},
        "libraries": [{"name": EVIL_ATTR, "shows": 3, "shows_with_gaps": 1, "missing_episodes": 2,
                       "unavailable_episodes": 1, "missing_seasons": 1, "listed": [
                           {"title": EVIL, "year": EVIL_ATTR, "missing_seasons": [3], "missing_episodes": 2,
                            "unavailable_episodes": 1, "seasons": [
                                {"season": EVIL, "missing": [[EVIL, EVIL_ATTR]], "unavailable": [EVIL]}]}]}],
    }
    playback = {
        "limits": EVIL, "bitrate_limit": None,
        "totals": {"files": 3, "files_flagged": 1, "image_subtitles": 1},
        "libraries": [{"name": EVIL_ATTR, "files": 3, "image_subtitles": 1}],
        "playback_history": {"days": 90, "plays": 4, "transcodes": 2,
                             "devices": [{"device": EVIL, "app": EVIL_ATTR, "platform": EVIL, "plays": 4,
                                          "transcodes": 2, "reasons": {"subtitles": 2}}],
                             "people": [{"person": "alex-test" + EVIL, "plays": 4, "transcodes": 2,
                                         "reasons": {"audio": 1}}]},
    }
    return {"library": library, "health": health, "watch": watch, "sharing": sharing, "unwatched": unwatched,
            "episode_gaps": episode_gaps, "playback": playback}


def page(data, errors=None, hide_names=False, snapshot_saved=None):
    return db.full_page(*db.render(data, errors or {}, hide_names, snapshot_saved))


class PageSafety(OfflineTestCase):
    def test_every_report_value_is_escaped(self):
        html = page(sample_data())
        self.assertNotIn("<script", html)
        self.assertNotIn('onmouseover="', html)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;", html)

    def test_error_reasons_are_escaped(self):
        html = page({}, {"library": EVIL, "health": EVIL, "watch": EVIL, "sharing": EVIL, "unwatched": EVIL,
                         "episode_gaps": EVIL, "playback": EVIL})
        self.assertNotIn("<script", html)
        self.assertEqual(html.count("&lt;script&gt;"), 7)

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

    def test_server_health_skips_the_stuck_task_check(self):
        with mock.patch.object(db.subprocess, "run", return_value=finished(stdout="{}")) as run:
            db.run_source("health")
        command = run.call_args[0][0]
        self.assertTrue(command[1].endswith("server_health.py"))
        self.assertEqual(command[2:], ["--stuck-wait", "0", "--snapshot-items"])

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
        results = {"library": {"totals": {}}, "health": None, "watch": {"totals": {}}, "sharing": {"people": []},
                   "unwatched": {"totals": {}}, "episode_gaps": {"totals": {}}, "playback": {"totals": {}}}
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
    def build(self, hide_names=None, saved="2026-10-06"):
        with mock.patch.object(db, "collect", return_value=(sample_data(), {})), \
                mock.patch.object(db, "save_snapshot", return_value=saved):
            return db.build(argparse.Namespace(output=db.default_output(), hide_names=hide_names))

    def test_snapshot_saved_is_reported(self):
        self.assertEqual(self.build()["snapshot_saved"], "2026-10-06")
        self.assertIsNone(self.build(saved=None)["snapshot_saved"])

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


# ---------------------------------------------------------------- sharing section

def sharing_report(people=3, worth=None):
    rows = [{"name": f"person-{i:02d}", "kind": "friend", "status": "accepted", "libraries": ["Movies"],
             "last_played": "2026-09-30"} for i in range(people)]
    return {"people": rows, "libraries": [{"title": "Movies", "shared_with_count": people}],
            "totals": {"people": people, "by_kind": {"friend": people}}, "worth_a_look": worth or []}


def healthy():
    return {"server": {"name": "Test", "version": "1.0", "update": {"update_available": False},
                       "remote_access": {"state": "mapped"}}, "worth_a_look": []}


class SharingSection(OfflineTestCase):
    def test_section_is_built(self):
        html = page({"sharing": sharing_report(3)})
        self.assertIn("<h2>Sharing</h2>", html)
        self.assertIn("person-00", html)
        self.assertIn("People who can see it", html)

    def test_owner_only_failure(self):
        error = "OWNER_ONLY: only the server owner's Plex account can see who a server is shared with."
        fake = lambda name: (name, None, error) if name == "sharing" else (name, {"totals": {}}, None)
        with mock.patch.object(db, "run_source", fake):
            data, errors = db.collect()
        self.assertEqual(errors, {"sharing": error})
        html = page(data, errors)
        self.assertIn("only the server owner&#x27;s Plex account can see", html)
        self.assertNotIn("OWNER_ONLY", html)

    def test_downloads_item_keeps_the_page_healthy(self):
        worth = [{"kind": "downloads_allowed", "people": ["person-00"]}]
        html = page({"health": healthy(), "sharing": sharing_report(1, worth)})
        self.assertIn("1 friend can download", html)
        self.assertIn("Healthy", html)
        self.assertNotIn("Mostly fine", html)

    def test_names_hidden(self):
        worth = [{"kind": "inactive", "people": ["person-00", "person-01", "person-02"], "days": 90}]
        html = page({"sharing": sharing_report(3, worth)}, hide_names=True)
        self.assertIn("3 people with no plays in 90+ days", html)
        self.assertNotIn("person-0", html)
        self.assertNotIn("Last played", html)

    def test_unused_library_shows_titles_even_with_names_hidden(self):
        worth = [{"kind": "unused_library", "libraries": ["Fitness"], "days": 90}]
        html = page({"health": healthy(), "sharing": sharing_report(1, worth)}, hide_names=True)
        self.assertIn("1 shared library with no plays by the people it is shared with in 90+ days", html)
        self.assertIn("Fitness", html)
        self.assertIn("Healthy", html)
        worth = [{"kind": "unused_library", "libraries": ["Fitness", "Kids"], "days": 30}]
        html = page({"sharing": sharing_report(1, worth)})
        self.assertIn("2 shared libraries with no plays by the people they are shared with in 30+ days", html)

    def test_sample_names_hidden_everywhere(self):
        html = page(sample_data(), hide_names=True)
        for name in ("sam-test", "riley-test", "casey-test", "alex-test"):
            self.assertNotIn(name, html)

    def test_long_share_list(self):
        html = page({"sharing": sharing_report(26)})
        self.assertIn("person-19", html)
        self.assertNotIn("person-20", html)
        self.assertIn("and 6 more people", html)

    def test_nobody_shared(self):
        html = page({"sharing": sharing_report(0)})
        self.assertIn("isn't shared with anyone", html)


# ---------------------------------------------------------------- unwatched section

def unwatched_report(count=50, gb=600.0, titles=12):
    rows = [{"title": f"Movie {i:02d}", "added": "2024-03-01", "gb": float(100 - i),
             "last_finished": None if i % 2 else "2025-02-01"} for i in range(titles)]
    return {
        "months": 6, "source": "plex", "history_since": "2021-12-19", "history_capped": False,
        "totals": {"unwatched": count, "unwatched_gb": gb, "library_gb": 4000.0, "unwatched_pct": 15.0,
                   "never_finished": count // 2, "never_finished_gb": gb / 2},
        "libraries": [
            {"name": "Movies", "type": "movie", "items": 400, "unwatched": count, "unwatched_gb": gb,
             "unwatched_pct": 15.0, "never_finished": count // 2, "titles": rows},
            {"name": "DVR", "type": "movie", "items": 0, "unwatched": 0, "unwatched_gb": 0.0,
             "unwatched_pct": 0.0, "never_finished": 0, "titles": []},
        ],
    }


class UnwatchedSection(OfflineTestCase):
    def test_unwatched_runs_with_a_limit_of_ten(self):
        self.assertEqual(db.SOURCES["unwatched"], ("unwatched", "unwatched.py", ["--limit", "10"]))

    def test_section_is_built(self):
        html = page({"unwatched": unwatched_report()})
        self.assertIn("<h2>Unwatched</h2>", html)
        self.assertIn("50 titles</strong> added more than 6 months ago haven&#x27;t been finished", html)
        self.assertIn("600 GB", html)
        self.assertIn("15.0% of 4.0 TB", html)
        self.assertIn("Plex&#x27;s watch history, going back to Dec 2021", html)
        self.assertNotIn("DVR", html)

    def test_ten_largest_titles(self):
        html = page({"unwatched": unwatched_report()})
        self.assertIn("Movie 09", html)
        self.assertNotIn("Movie 10", html)
        self.assertIn("never finished", html)
        self.assertIn("last finished Feb 2025", html)
        self.assertIn("added Mar 2024", html)

    def test_page_stays_healthy(self):
        html = page({"health": healthy(), "unwatched": unwatched_report()})
        self.assertIn("Healthy", html)
        self.assertNotIn("Mostly fine", html)

    def test_no_deletion_advice(self):
        html = page({"unwatched": unwatched_report()}).lower()
        for word in ("delete", "remove", "free up"):
            self.assertNotIn(word, html)

    def test_nothing_unwatched(self):
        html = page({"unwatched": unwatched_report(count=0, gb=0.0, titles=0)})
        self.assertIn("Everything added more than 6 months ago has been finished", html)

    def test_capped_history_is_mentioned(self):
        report = unwatched_report()
        report["history_capped"] = True
        self.assertIn("only its newest part was read", page({"unwatched": report}))

    def test_failure(self):
        fake = lambda name: (name, None, "OWNER_ONLY: only the owner") if name == "unwatched" \
            else (name, {"totals": {}}, None)
        with mock.patch.object(db, "run_source", fake):
            data, errors = db.collect()
        self.assertEqual(list(errors), ["unwatched"])
        html = page(data, errors)
        self.assertIn("Couldn't load the unwatched report: only the owner", html)
        self.assertNotIn("OWNER_ONLY", html)

    def test_hiding_names_keeps_the_section(self):
        html = page({"unwatched": unwatched_report()}, hide_names=True)
        self.assertIn("Movie 00", html)


# ---------------------------------------------------------------- episode gaps section

def gap_show(title, missing=(), unavailable=(), seasons_missing=(), year=2010, season=2):
    count = sum(b - a + 1 for a, b in missing)
    return {"title": title, "year": year, "first_season": 1, "missing_seasons": list(seasons_missing),
            "missing_episodes": count, "unavailable_episodes": len(unavailable), "unnumbered": 0,
            "seasons": [{"season": season, "episodes": 5, "highest": 12, "missing": [list(r) for r in missing],
                         "unavailable": list(unavailable), "continues_numbering": False}]}


def gaps_report(shows=12, listed=10):
    rows = [gap_show(f"Show {i:02d}", missing=[(3, 3)] * (20 - i)) for i in range(listed)]
    library = {"name": "TV Shows", "shows": 417, "episodes": 19008, "shows_with_gaps": shows,
               "missing_episodes": 90, "unavailable_episodes": 0, "missing_seasons": 11,
               "shows_starting_later": 3, "seasons_not_checked": 16, "unnumbered": 0,
               "listed": rows, "more_shows": shows - listed}
    totals = {k: library[k] for k in ("shows", "episodes", "shows_with_gaps", "missing_episodes",
                                      "unavailable_episodes", "missing_seasons", "shows_starting_later")}
    return {"limits": "Only gaps between the episodes on the server can be found.",
            "libraries": [library], "totals": totals, "skipped_libraries": []}


class EpisodeGapsSection(OfflineTestCase):
    def test_runs_with_a_limit_of_ten(self):
        self.assertEqual(db.SOURCES["episode_gaps"], ("episode-gaps", "episode_gaps.py", ["--limit", "10"]))

    def test_not_part_of_the_snapshot(self):
        self.assertNotIn("episode_gaps", db.SNAPSHOT_AREAS)

    def test_section_is_built(self):
        html = page({"episode_gaps": gaps_report()})
        self.assertIn("<h2>Episode gaps</h2>", html)
        self.assertIn("<strong>12</strong> of 417 shows have gaps: 90 missing episodes, 11 missing seasons.", html)
        self.assertIn("Only gaps between the episodes on the server can be found.", html)
        self.assertIn("Show 09 (2010)", html)
        self.assertIn("2 more shows with gaps.", html)

    def test_shows_are_sorted_and_limited_across_libraries(self):
        report = gaps_report(shows=5, listed=5)
        second = dict(report["libraries"][0], name="Kids TV",
                      listed=[gap_show(f"Kid Show {i}", missing=[(1, 30 + i)]) for i in range(8)])
        report["libraries"].append(second)
        html = page({"episode_gaps": report})
        for i in range(8):
            self.assertIn(f"Kid Show {i}", html)
        self.assertIn("Show 00", html)
        self.assertIn("Show 01", html)
        self.assertNotIn("Show 02 ", html)

    def test_gaps_are_written_as_episodes(self):
        show = gap_show("Ranges", missing=[(3, 3), (5, 7)], unavailable=[9], seasons_missing=[3, 4, 5, 8])
        report = gaps_report(shows=1, listed=0)
        report["libraries"][0]["listed"] = [show]
        html = page({"episode_gaps": report})
        self.assertIn("seasons 3 to 5, season 8, S02E03, S02E05 to E07, S02E09 (file not found)", html)

    def test_unavailable_episodes_in_a_row(self):
        show = gap_show("Gone", unavailable=[5, 6, 7, 8, 10])
        report = gaps_report(shows=1, listed=0)
        report["libraries"][0]["listed"] = [show]
        html = page({"episode_gaps": report})
        self.assertIn("S02E05 to E08 (file not found), S02E10 (file not found)", html)

    def test_a_show_with_many_gaps(self):
        show = gap_show("Holes", missing=[(n, n) for n in range(1, 18, 2)])
        report = gaps_report(shows=1, listed=0)
        report["libraries"][0]["listed"] = [show]
        html = page({"episode_gaps": report})
        self.assertIn("S02E01, S02E03, S02E05, S02E07, S02E09, and 4 more", html)

    def test_unavailable_episodes_in_the_headline(self):
        report = gaps_report()
        report["totals"]["unavailable_episodes"] = 3
        self.assertIn("3 episodes whose file Plex can&#x27;t find", page({"episode_gaps": report}))

    def test_page_stays_healthy(self):
        html = page({"health": healthy(), "episode_gaps": gaps_report()})
        self.assertIn("Healthy", html)
        self.assertNotIn("Mostly fine", html)

    def test_no_advice(self):
        html = page({"episode_gaps": gaps_report()}).lower()
        section = html.split("<h2>episode gaps</h2>")[1].split("</section>")[0]
        for word in ("download", "delete", "replace"):
            self.assertNotIn(word, section)

    def test_no_gaps_found(self):
        report = gaps_report(shows=0, listed=0)
        html = page({"episode_gaps": report})
        self.assertIn("No gaps were found between the episodes on the server.", html)
        self.assertIn("Only gaps between the episodes on the server can be found.", html)

    def test_no_tv_library(self):
        report = gaps_report()
        report["libraries"] = []
        self.assertIn("This server has no TV library.", page({"episode_gaps": report}))

    def test_failure(self):
        fake = lambda name: (name, None, "could not reach the server") if name == "episode_gaps" \
            else (name, {"totals": {}}, None)
        with mock.patch.object(db, "run_source", fake):
            data, errors = db.collect()
        self.assertEqual(list(errors), ["episode_gaps"])
        self.assertIn("Couldn't load the episode gaps report: could not reach the server", page(data, errors))

    def test_hiding_names_keeps_the_section(self):
        self.assertIn("Show 00", page({"episode_gaps": gaps_report()}, hide_names=True))


# ---------------------------------------------------------------- playback section

def playback_report(history=True):
    report = {
        "limits": "These are likely causes on common devices, not a promise.",
        "bitrate_limit": None,
        "totals": {"titles": 2000, "files": 2000, "files_flagged": 900, "image_subtitles": 600,
                   "truehd_audio": 100, "dts_audio": 400, "over_bitrate_limit": 0},
        "libraries": [{"name": "Movies", "type": "movie", "files": 2000, "image_subtitles": 600,
                       "truehd_audio": 100, "dts_audio": 400, "over_bitrate_limit": 0, "listed": []}],
    }
    if history:
        report["playback_history"] = {
            "days": 90, "plays": 419, "transcodes": 32,
            "devices": [
                {"device": "Sam's iPhone", "app": "Plex for iOS", "platform": "iOS", "plays": 20,
                 "transcodes": 14, "reasons": {"subtitles": 10, "video": 2, "audio": 3}},
                {"device": "Den TV", "app": "Plex for Roku", "platform": "Roku", "plays": 10,
                 "transcodes": 4, "reasons": {"audio": 4}},
                {"device": "Bedroom TV", "app": "Plex for Roku", "platform": "Roku", "plays": 5,
                 "transcodes": 2, "reasons": {"video": 2}},
            ],
            "people": [{"person": "Sam", "plays": 25, "transcodes": 16, "reasons": {"subtitles": 10}}],
        }
    else:
        report["playback_history"] = None
        report["playback_history_note"] = "Transcodes by device and person need Tautulli."
    return report


class PlaybackSection(OfflineTestCase):
    def section(self, html):
        return html.split("<h2>Playback</h2>")[1].split("</section>")[0]

    def test_runs_with_counts_only(self):
        self.assertEqual(db.SOURCES["playback"], ("playback-check", "playback_check.py", ["--limit", "0"]))
        self.assertNotIn("playback", db.SNAPSHOT_AREAS)

    def test_section_is_built(self):
        html = self.section(page({"playback": playback_report()}))
        self.assertIn("<strong>900</strong> of 2,000 files are likely to be converted on some devices: "
                      "600 with image-based subtitles, 100 with TrueHD audio, 400 with DTS audio.", html)
        self.assertIn("No remote streaming limit is set, so bitrate wasn&#x27;t checked.", html)
        self.assertIn("In the last 90 days, 32 of 419 plays were transcoded.", html)
        self.assertIn("Sam&#x27;s iPhone · Plex for iOS", html)
        self.assertIn("14 of 20 plays (70%), mostly subtitles", html)
        self.assertIn("People who transcode most", html)
        self.assertIn("likely causes on common devices", html)

    def test_empty_libraries_are_left_out(self):
        report = playback_report()
        report["libraries"].append({"name": "Empty DVR", "type": "movie", "files": 0})
        self.assertNotIn("Empty DVR", page({"playback": report}))

    def test_bitrate_limit_line(self):
        report = playback_report()
        report["bitrate_limit"] = {"kbps": 12000, "source": "server"}
        self.assertIn("the server&#x27;s remote streaming limit: 12,000 kbps", page({"playback": report}))

    def test_page_stays_healthy(self):
        html = page({"health": healthy(), "playback": playback_report()})
        self.assertIn("Healthy", html)
        self.assertNotIn("Mostly fine", html)

    def test_no_tautulli(self):
        html = self.section(page({"playback": playback_report(history=False)}))
        self.assertIn("Transcodes by device and person need Tautulli.", html)
        self.assertNotIn("transcode most", html)

    def test_names_hidden(self):
        html = page({"playback": playback_report()}, hide_names=True)
        self.assertNotIn("Sam", html)
        self.assertNotIn("Den TV", html)
        self.assertNotIn("People who transcode most", html)
        # The two Roku devices are merged by app and platform.
        self.assertIn("Plex for Roku · Roku<span class=\"transcode-detail\">6 of 15 plays (40%), mostly audio", html)

    def test_no_advice(self):
        section = self.section(page({"playback": playback_report()})).lower()
        for word in ("convert your", "remux", "re-encode", "delete", "replace"):
            self.assertNotIn(word, section)

    def test_no_movie_or_tv_library(self):
        report = playback_report()
        report["libraries"] = []
        self.assertIn("This server has no movie or TV library.", page({"playback": report}))

    def test_failure(self):
        fake = lambda name: (name, None, "could not reach the server") if name == "playback" \
            else (name, {"totals": {}}, None)
        with mock.patch.object(db, "run_source", fake):
            data, errors = db.collect()
        self.assertEqual(list(errors), ["playback"])
        self.assertIn("Couldn't load the playback report: could not reach the server", page(data, errors))


# ---------------------------------------------------------------- library growth chart

def growth_library(sizes, start=(2025, 11)):
    """A library report whose growth.months has one month per size, starting at start (year, month)."""
    year, month, months = start[0], start[1], []
    for gb in sizes:
        months.append({"month": f"{year:04d}-{month:02d}", "added": 3 if gb else 0, "gb": gb})
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return {"libraries": [], "growth": {"added": sum(m["added"] for m in months),
                                        "gb": round(sum(sizes), 1), "months": months}}


class LibraryGrowthChart(OfflineTestCase):
    def test_plays_chart_is_unchanged(self):
        chart = db.daily_chart([{"date": "2026-09-01", "plays": 4, "hours": 2.0},
                                {"date": "2026-09-02", "plays": 0}, {"date": "2026-09-03", "plays": 2}])
        self.assertIn('aria-label="Plays per day over the last 3 days"', chart)
        self.assertEqual(chart.count('class="bar bar-peak"'), 2)  # tallest bar, in the wide and narrow chart
        self.assertEqual(chart.count('class="bar"'), 2)
        self.assertIn("<title>Sep 1: 4 plays, 2 h</title>", chart)
        self.assertIn("<title>Sep 2: 0 plays</title>", chart)
        self.assertIn('text-anchor="end">4</text>', chart)  # round axis ticks from nice_step

    def test_a_year_of_additions(self):
        sizes = [10, 20, 30, 40, 50, 400, 60, 70, 80, 90, 100, 5.5]
        html = page({"library": growth_library(sizes)})
        self.assertIn("Storage added per month", html)
        self.assertIn("956 GB, 36 items in the last 12 months", html)
        wide = html[html.index('<svg class="chart chart-wide" viewBox="0 0 720 200" role="img" '
                               'aria-label="Storage added per month'):]
        wide = wide[:wide.index("</svg>")]
        self.assertEqual(wide.count('class="bar'), 12)
        self.assertEqual(wide.count("bar-peak"), 1)
        self.assertIn("<title>Apr 2026: 400 GB, 3 items</title></path>", wide.replace('"bar bar-peak"', ""))
        self.assertIn("Nov '25</text>", wide)  # first bar shows the year
        self.assertIn("Jan '26</text>", wide)  # and so does January
        self.assertIn(">Feb</text>", wide)
        self.assertIn("<title>Oct 2026 so far: 5.5 GB, 3 items</title>", wide)
        self.assertIn(">400 GB</text>", wide)  # axis ticks in GB or TB
        narrow = html[html.index('<svg class="chart chart-narrow" viewBox="0 0 360 180" role="img" '
                                 'aria-label="Storage added per month'):]
        narrow = narrow[:narrow.index("</svg>")]
        # The narrow chart skips January's label, so the year goes on the first label shown in 2026.
        self.assertNotIn("Jan", narrow.split("<title>")[0])
        self.assertIn("Feb '26</text>", narrow)

    def test_axis_in_terabytes(self):
        self.assertIn(">1.6 TB</text>", page({"library": growth_library([3000, 100])}))

    def test_nothing_added(self):
        html = page({"library": growth_library([0] * 12)})
        self.assertIn("Nothing was added in the last 12 months.", html)
        self.assertNotIn("Storage added per month", html)

    def test_report_without_growth(self):
        html = page({"library": {"libraries": []}})
        self.assertIn("Library", html)
        self.assertNotIn("Storage added per month", html)
        self.assertNotIn("Nothing was added", html)

    def test_no_months(self):
        html = page({"library": {"libraries": [], "growth": {"added": 0, "gb": 0.0, "months": []}}})
        self.assertNotIn("Storage added per month", html)
        self.assertNotIn("Nothing was added", html)

    def test_page_stays_healthy_and_names_dont_matter(self):
        data = {"health": healthy(), "library": growth_library([5, 50, 500])}
        html = page(data)
        self.assertIn("Healthy", html)
        self.assertNotIn("Mostly fine", html)
        self.assertEqual(html, page(data, hide_names=True))


# ---------------------------------------------------------------- snapshots and the changes section

class SavingSnapshots(OfflineTestCase):
    def data(self):
        data = sample_data()
        for area in ("library", "health", "sharing"):
            data[area]["snapshot"] = {"server_id": "machineidfortests", "area": {"from": area}}
        return data

    def test_reports_are_handed_to_the_changes_script(self):
        data = self.data()
        with mock.patch.object(db.subprocess, "run",
                               return_value=finished(stdout='{"snapshot_saved": "2026-10-06"}')) as run:
            self.assertEqual(db.save_snapshot(data), "2026-10-06")
        command = run.call_args.args[0]
        self.assertTrue(command[1].endswith(os.path.join("changes", "scripts", "changes.py")))
        self.assertEqual(command[2:], ["save"])
        given = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(sorted(given), ["health", "library", "sharing"])
        self.assertEqual(given["health"]["snapshot"]["area"], {"from": "health"})
        # The snapshot blocks are for saving only and never reach the page.
        for area in ("library", "health", "sharing"):
            self.assertNotIn("snapshot", data[area])

    def test_failed_reports_are_left_out(self):
        data = self.data()
        data["sharing"] = None
        with mock.patch.object(db.subprocess, "run", return_value=finished(stdout='{"snapshot_saved": null}')) as run:
            db.save_snapshot(data)
        self.assertEqual(sorted(json.loads(run.call_args.kwargs["input"])), ["health", "library"])

    def test_a_failed_save_does_not_stop_the_build(self):
        for kwargs in ({"return_value": finished(returncode=1, stderr="error: disk full")},
                       {"return_value": finished(stdout="not json")},
                       {"side_effect": OSError("no python")},
                       {"side_effect": subprocess.TimeoutExpired(cmd="x", timeout=1)}):
            with self.subTest(kwargs=kwargs), mock.patch.object(db.subprocess, "run", **kwargs):
                data = self.data()
                self.assertIsNone(db.save_snapshot(data))
                self.assertNotIn("snapshot", data["library"])

    def test_nothing_to_save(self):
        with mock.patch.object(db.subprocess, "run", side_effect=AssertionError("should not run")):
            self.assertIsNone(db.save_snapshot({"watch": {}}))


class ChangesSection(OfflineTestCase):
    def test_shows_what_changed(self):
        html = page(sample_data())
        self.assertIn("Since Sep 29", html)
        self.assertIn("7 days ago", html)
        for text in ("Titles added", "New episodes", "+12 GB", "Can&#x27;t be found now",
                     "1 person now has access", "1 invite accepted", "Download access changed for 1 person",
                     "+1 invites sent by email"):
            self.assertIn(text, html)

    def test_names_hidden(self):
        html = page(sample_data(), hide_names=True)
        self.assertIn("1 person now has access", html)
        for name in ("sam-test", "alex-test", "casey-test", "riley-test"):
            self.assertNotIn(name, html)

    def test_first_build(self):
        data = sample_data()
        for area in ("library", "health", "sharing"):
            data[area]["since_snapshot"] = None
        self.assertIn("First snapshot saved today", page(data, snapshot_saved="2026-10-06"))
        self.assertIn("No earlier snapshot to compare with yet", page(data))

    def test_nothing_changed(self):
        when = {"snapshot_date": "2026-10-05", "days_ago": 1}
        data = {"library": {"since_snapshot": dict(when, libraries=[{"name": "Movies", "status": "same"}],
                                                   totals={})},
                "health": healthy()}
        data["health"]["since_snapshot"] = dict(when, changes=[])
        html = page(data)
        self.assertIn("Nothing changed.", html)
        self.assertIn("yesterday", html)

    def test_failed_reports_leave_their_part_out(self):
        data = sample_data()
        data["sharing"] = None
        html = page(data, {"sharing": "OWNER_ONLY: only the owner"})
        self.assertIn("Since Sep 29", html)
        self.assertNotIn("now has access", html)

    def test_no_section_when_every_report_failed(self):
        self.assertNotIn("What changed", page({}, {"library": "x", "health": "x", "sharing": "x"}))
