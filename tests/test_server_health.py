"""server-health (openspec/specs/server-health/spec.md)."""

import argparse
import time

from helpers import FAKE_TOKEN, FakeServer, OfflineTestCase, Reply, fixture, load_script

sh = load_script("server-health")


def healthy():
    """A report with nothing worth flagging."""
    return {
        "server": {
            "update": {"update_available": False},
            "remote_access": {"state": "mapped"},
            "resource_use": {"average": {"host_cpu_pct": 10.0, "host_memory_pct": 20.0}},
        },
        "live_activity": {"streams": []},
        "background": {
            "library_scans": [{"name": "Movies", "scanning_now": False, "days_since_scan": 1.0}],
            "maintenance_settings": {"scheduled_scans_enabled": True, "scan_on_folder_change": True},
            "maintenance_tasks": {"important_disabled": []},
        },
    }


def kinds(report, stale_days=7):
    return [note["kind"] for note in sh.worth_a_look(report, stale_days)]


class WorthALook(OfflineTestCase):
    def test_nothing_to_flag(self):
        self.assertEqual(sh.worth_a_look(healthy(), 7), [])

    def test_update_available(self):
        report = healthy()
        report["server"]["update"] = {"update_available": True, "available_version": "1.41.0"}
        self.assertEqual(sh.worth_a_look(report, 7), [{"kind": "update_available", "version": "1.41.0"}])

    def test_remote_access_not_working(self):
        report = healthy()
        report["server"]["remote_access"] = {"state": "failed", "error_message": "Port not open"}
        self.assertEqual(sh.worth_a_look(report, 7), [
            {"kind": "remote_access_not_working", "state": "failed", "error": "Port not open"}])

    def test_unknown_remote_access_state_is_not_flagged(self):
        report = healthy()
        report["server"]["remote_access"] = {"state": None}
        self.assertEqual(kinds(report), [])

    def test_transcode_too_slow(self):
        def with_stream(transcode):
            report = healthy()
            report["live_activity"]["streams"] = [{"user": "sam", "title": "Film", "transcode": transcode}]
            return report
        self.assertEqual(kinds(with_stream({"speed": "0.6", "throttled": False})), ["transcode_too_slow"])
        # Throttled means the server is ahead and resting; fast enough, or unknown speed, is fine.
        self.assertEqual(kinds(with_stream({"speed": "0.6", "throttled": True})), [])
        self.assertEqual(kinds(with_stream({"speed": "1.5", "throttled": False})), [])
        self.assertEqual(kinds(with_stream({"speed": None, "throttled": False})), [])
        self.assertEqual(kinds(with_stream(None)), [])

    def test_scheduled_scans_not_running(self):
        report = healthy()
        report["background"]["library_scans"] = [
            {"name": "Movies", "scanning_now": False, "days_since_scan": 1.0},
            {"name": "TV", "scanning_now": False, "days_since_scan": 30.0},
            {"name": "Never", "scanning_now": False, "days_since_scan": None},
            {"name": "Music", "scanning_now": True, "days_since_scan": 40.0},
        ]
        self.assertEqual(sh.worth_a_look(report, 7), [
            {"kind": "scheduled_scans_not_running", "days": 7, "libraries": ["TV", "Never"]}])

    def test_old_scans_are_normal_when_only_folder_watching_is_on(self):
        report = healthy()
        report["background"]["maintenance_settings"] = {"scheduled_scans_enabled": False,
                                                        "scan_on_folder_change": True}
        report["background"]["library_scans"][0]["days_since_scan"] = 300.0
        self.assertEqual(kinds(report), [])

    def test_automatic_scans_off(self):
        report = healthy()
        report["background"]["maintenance_settings"] = {"scheduled_scans_enabled": False,
                                                        "scan_on_folder_change": False}
        self.assertEqual(kinds(report), ["automatic_scans_off"])

    def test_important_maintenance_disabled(self):
        report = healthy()
        report["background"]["maintenance_tasks"]["important_disabled"] = ["Backup Database"]
        self.assertEqual(sh.worth_a_look(report, 7), [
            {"kind": "important_maintenance_disabled", "tasks": ["Backup Database"]}])

    def test_high_cpu_and_memory(self):
        report = healthy()
        report["server"]["resource_use"]["average"] = {"host_cpu_pct": 85.0, "host_memory_pct": 90.0}
        self.assertEqual(kinds(report), ["high_cpu", "high_memory"])
        report["server"]["resource_use"]["average"] = {"host_cpu_pct": 84.9, "host_memory_pct": 89.9}
        self.assertEqual(kinds(report), [])

    def test_missing_parts_do_not_break_it(self):
        report = {"server": {"update": None, "remote_access": None, "resource_use": None},
                  "live_activity": None, "background": {}}
        self.assertEqual(sh.worth_a_look(report, 7), [])


class SmallHelpers(OfflineTestCase):
    def test_playback_method(self):
        self.assertEqual(sh.playback_method({}), "direct play")
        self.assertEqual(sh.playback_method({"TranscodeSession": {"videoDecision": "copy",
                                                                  "audioDecision": "copy"}}), "direct stream")
        self.assertEqual(sh.playback_method({"TranscodeSession": {"videoDecision": "copy",
                                                                  "audioDecision": "transcode"}}), "transcode")

    def test_stream_title(self):
        self.assertEqual(sh.stream_title({"type": "episode", "grandparentTitle": "The Show",
                                          "parentIndex": "3", "index": "7"}), "The Show S03E07")
        self.assertEqual(sh.stream_title({"type": "track", "grandparentTitle": "Band", "title": "Song"}),
                         "Band - Song")
        self.assertEqual(sh.stream_title({"type": "movie", "title": "Heat", "year": 1995}), "Heat (1995)")
        self.assertEqual(sh.stream_title({"type": "clip", "title": "Trailer\n"}), "Trailer")

    def test_as_int_and_as_bool(self):
        self.assertEqual(sh.as_int("12.7"), 12)
        self.assertEqual(sh.as_int(None), 0)
        self.assertEqual(sh.as_int("abc", None), None)
        for value in (True, "1", "true", "Yes"):
            self.assertTrue(sh.as_bool(value), value)
        for value in (False, "0", "false", None, ""):
            self.assertFalse(sh.as_bool(value), value)

    def test_days_ago(self):
        now = 1700000000
        self.assertEqual(sh.days_ago(now - 3 * 86400, now), 3.0)
        self.assertIsNone(sh.days_ago(None, now))
        self.assertIsNone(sh.days_ago(0, now))

    def test_task_label(self):
        self.assertEqual(sh.task_label({"name": "ButlerTaskGenerateAdMarkers"}), "Generate Ad Markers")
        self.assertEqual(sh.task_label({"name": "X", "title": "Nice Title"}), "Nice Title")


# ---------------------------------------------------------------- whole report

def sample_server(**overrides):
    """A FakeServer for tests/fixtures/server-health/server.json.

    The fixture gives each library's last scan as "scannedDaysAgo"; it is turned into Plex's
    scannedAt time here so the report's "days since scan" doesn't depend on today's date.
    """
    routes = fixture("server-health", "server.json")
    now = time.time()
    for section in routes["/library/sections"]["MediaContainer"]["Directory"]:
        section["scannedAt"] = int(now - section.pop("scannedDaysAgo") * 86400)
    routes.update(overrides)
    return FakeServer(routes)


class WholeReport(OfflineTestCase):
    def report(self, server, stale_days=7.0):
        client = sh.PlexClient("http://192.0.2.10:32400", FAKE_TOKEN, True)
        server.attach(client._opener)
        return sh.build_report(client, argparse.Namespace(stale_days=stale_days))

    def test_server_basics(self):
        server = self.report(sample_server())["server"]
        self.assertEqual(server["name"], "Test Server")
        self.assertEqual(server["platform"], "Linux 6.1")
        self.assertIs(server["signed_in_to_plex"], True)
        self.assertIs(server["plex_pass"], True)
        self.assertEqual(server["update"]["available_version"], "1.41.0.0000-test")

    def test_remote_access_leaves_out_addresses(self):
        remote = self.report(sample_server())["server"]["remote_access"]
        self.assertEqual(remote["state"], "failed")
        self.assertNotIn("198.51.100.7", str(remote))

    def test_resource_use(self):
        use = self.report(sample_server())["server"]["resource_use"]
        self.assertEqual(use["average"]["host_cpu_pct"], 88.0)
        self.assertEqual(use["latest"]["host_cpu_pct"], 86.0)  # the newest sample, whatever the order
        self.assertEqual(use["samples"], 2)

    def test_live_streams(self):
        live = self.report(sample_server())["live_activity"]
        self.assertEqual(live["totals"], {"streams": 2, "direct_play": 1, "direct_stream": 0, "transcode": 1,
                                          "bandwidth_kbps": 24000, "lan_kbps": 20000, "wan_kbps": 4000})
        movie, episode = live["streams"]
        self.assertEqual((movie["title"], movie["method"], movie["progress_pct"]), ("Arrival (2016)", "direct play", 25))
        self.assertNotIn("transcode", movie)
        self.assertEqual(episode["title"], "The Show S01E02")
        self.assertEqual(episode["transcode"], {"video": "transcode", "audio": "copy", "hardware": False,
                                                "speed": "0.8", "throttled": False})
        self.assertNotIn("192.0.2.20", str(live))

    def test_background_work(self):
        background = self.report(sample_server())["background"]
        self.assertEqual(background["running_now"][0]["progress_pct"], 40)
        self.assertEqual(background["maintenance_tasks"]["important_disabled"], ["Backup Database"])
        self.assertIn("Optimize Database", background["maintenance_tasks"]["enabled"])
        self.assertEqual([lib["name"] for lib in background["library_scans"]], ["Movies", "TV", "Music"])

    def test_only_maintenance_settings_are_kept(self):
        settings = self.report(sample_server())["background"]["maintenance_settings"]
        self.assertEqual(settings, {
            "maintenance_start_hour": 2, "maintenance_end_hour": 5, "scan_on_folder_change": True,
            "scheduled_scans_enabled": True, "scheduled_scan_interval_seconds": 86400,
        })

    def test_worth_a_look(self):
        report = self.report(sample_server())
        self.assertEqual([n["kind"] for n in report["worth_a_look"]], [
            "update_available", "remote_access_not_working", "transcode_too_slow",
            "scheduled_scans_not_running", "important_maintenance_disabled", "high_cpu"])
        scans = next(n for n in report["worth_a_look"] if n["kind"] == "scheduled_scans_not_running")
        self.assertEqual(scans["libraries"], ["TV"])
        self.assertEqual(report["unavailable"], [])

    def test_no_secret_from_settings_reaches_the_report(self):
        self.assertNotIn("secret-in-prefs-for-tests", str(self.report(sample_server())))

    def test_owner_only_part_is_listed_instead_of_failing(self):
        report = self.report(sample_server(**{"/myplex/account": Reply("", status=403)}))
        self.assertIsNone(report["server"]["remote_access"])
        self.assertEqual(report["unavailable"], [
            {"part": "remote access", "reason": "only available to the server owner's account"}])
        self.assertIsNotNone(report["live_activity"])

    def test_broken_part_is_listed_with_its_reason(self):
        report = self.report(sample_server(**{"/butler": Reply("", status=500)}))
        self.assertIsNone(report["background"]["maintenance_tasks"])
        self.assertEqual(report["unavailable"], [
            {"part": "maintenance tasks", "reason": "Plex returned HTTP 500 for /butler."}])

    def test_bad_token_stops_the_report(self):
        with self.assertRaises(sh.ReportError):
            self.report(sample_server(**{"/": Reply("", status=401)}))

    def test_only_allowed_get_requests(self):
        server = sample_server()
        self.report(server)
        for seen in server.requests:
            self.assertEqual(seen.method, "GET")
            self.assertTrue(any(rule.match(seen.path) for rule in sh.ALLOWED_PATHS), seen.path)
