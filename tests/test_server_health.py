"""server-health (openspec/specs/server-health/spec.md)."""

import argparse
import time
from unittest import mock

from helpers import FAKE_TOKEN, FakeServer, OfflineTestCase, Reply, fixture, load_script, plex_container

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

    def test_hardware_transcoding_off(self):
        report = healthy()
        report["server"]["streaming_settings"] = {"hardware_acceleration": False}
        self.assertEqual(sh.worth_a_look(report, 7), [{"kind": "hardware_transcoding_off"}])
        report["server"]["streaming_settings"] = {"hardware_acceleration": True}
        self.assertEqual(kinds(report), [])

    def test_video_transcoding_off(self):
        report = healthy()
        report["server"]["streaming_settings"] = {"video_transcoding_disabled": True}
        self.assertEqual(sh.worth_a_look(report, 7), [{"kind": "video_transcoding_off"}])
        report["server"]["streaming_settings"] = {"video_transcoding_disabled": False}
        self.assertEqual(kinds(report), [])

    def test_remote_stream_limit_low(self):
        def with_limit(kbps):
            report = healthy()
            report["server"]["streaming_settings"] = {"remote_stream_limit_kbps": kbps}
            return report
        self.assertEqual(sh.worth_a_look(with_limit(4000), 7),
                         [{"kind": "remote_stream_limit_low", "limit_kbps": 4000}])
        # 8 Mbps is the lowest choice Plex labels as 1080p; 0 means no limit.
        self.assertEqual(kinds(with_limit(8000)), [])
        self.assertEqual(kinds(with_limit(0)), [])
        self.assertEqual(kinds(with_limit(None)), [])

    def test_missing_streaming_settings_are_not_flagged(self):
        report = healthy()
        report["server"]["streaming_settings"] = {}
        self.assertEqual(kinds(report), [])
        report["server"]["streaming_settings"] = None
        self.assertEqual(kinds(report), [])

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
    def test_never_is_not_a_date(self):
        # Plex sends -1 (or 0) for "never", for example an update check that hasn't run.
        for never in (-1, 0, None, ""):
            self.assertIsNone(sh.when(never))
            self.assertIsNone(sh.days_ago(never, 1_000_000))
        self.assertIsNotNone(sh.when(1_700_000_000))
        self.assertEqual(sh.days_ago(1_000_000 - 86400, 1_000_000), 1.0)

    def test_update_never_checked(self):
        client = mock.Mock()
        client.get.return_value = {"checkedAt": -1, "canInstall": "0"}
        self.assertIsNone(sh.update_status(client)["last_checked"])

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


class ReportTestCase(OfflineTestCase):
    """Builds a report from a FakeServer, with the stuck task wait recorded instead of slept."""

    def setUp(self):
        super().setUp()
        self.waits = []
        patcher = mock.patch.object(sh, "pause", self.waits.append)
        patcher.start()
        self.addCleanup(patcher.stop)

    def report(self, server, stale_days=7.0, stuck_wait=0):
        client = sh.PlexClient("http://192.0.2.10:32400", FAKE_TOKEN, True)
        server.attach(client._opener)
        return sh.build_report(client, argparse.Namespace(stale_days=stale_days, stuck_wait=stuck_wait))


class WholeReport(ReportTestCase):
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

    def test_only_selected_settings_are_kept(self):
        report = self.report(sample_server())
        self.assertEqual(report["background"]["maintenance_settings"], {
            "maintenance_start_hour": 2, "maintenance_end_hour": 5, "scan_on_folder_change": True,
            "scheduled_scans_enabled": True, "scheduled_scan_interval_seconds": 86400,
            "empty_trash_after_scan": False,
        })
        self.assertEqual(report["server"]["streaming_settings"], {
            "hardware_acceleration": True, "hardware_encoding": True, "video_transcoding_disabled": False,
            "remote_stream_limit_kbps": 0, "remote_total_upload_limit_kbps": 600000,
            "custom_transcoder_temp_folder": True,
        })

    def test_transcoder_folder_path_is_never_kept(self):
        self.assertNotIn("private-transcode-path-for-tests", str(self.report(sample_server())))

    def test_empty_transcoder_folder_is_not_custom(self):
        prefs = fixture("server-health", "server.json")["/:/prefs"]
        for setting in prefs["MediaContainer"]["Setting"]:
            if setting["id"] == "TranscoderTempDirectory":
                setting["value"] = ""
        report = self.report(sample_server(**{"/:/prefs": prefs}))
        self.assertIs(report["server"]["streaming_settings"]["custom_transcoder_temp_folder"], False)

    def test_missing_setting_is_left_out(self):
        prefs = {"Setting": [{"id": "HardwareAcceleratedEncoders", "value": "1", "type": "bool"}]}
        self.assertEqual(sh.pick_settings(prefs, sh.STREAMING_PREFS), {"hardware_encoding": True})

    def test_settings_are_requested_once(self):
        server = sample_server()
        self.report(server)
        self.assertEqual([seen.path for seen in server.requests].count("/:/prefs"), 1)

    def test_settings_unavailable_empties_both_parts(self):
        server = sample_server(**{"/:/prefs": Reply("", status=403)})
        report = self.report(server)
        self.assertIsNone(report["server"]["streaming_settings"])
        self.assertIsNone(report["background"]["maintenance_settings"])
        owner_only = "only available to the server owner's account"
        self.assertEqual(report["unavailable"], [
            {"part": "streaming settings", "reason": owner_only},
            {"part": "maintenance settings", "reason": owner_only}])
        self.assertEqual([seen.path for seen in server.requests].count("/:/prefs"), 1)
        self.assertIsNotNone(report["live_activity"])

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
        self.report(server, stuck_wait=15)
        for seen in server.requests:
            self.assertEqual(seen.method, "GET")
            self.assertTrue(any(rule.match(seen.path) for rule in sh.ALLOWED_PATHS), seen.path)


# ---------------------------------------------------------------- stuck task check

def task(progress=40, detail="Arrival", uuid="activity-uuid-for-tests", title="Scanning Movies"):
    found = {"type": "library.update.section", "title": title, "subtitle": detail, "progress": progress}
    if uuid:
        found["uuid"] = uuid
    return found


def checks(*answers):
    """An /activities route that gives each answer in turn: a list of tasks, or a Reply."""
    answers = list(answers)

    def route(seen):
        answer = answers.pop(0)
        return answer if isinstance(answer, Reply) else plex_container(Activity=answer)
    return route


class StuckTasks(ReportTestCase):
    def run_checks(self, *answers, stuck_wait=15):
        server = sample_server(**{"/activities": checks(*answers)})
        report = self.report(server, stuck_wait=stuck_wait)
        requests = [seen for seen in server.requests if seen.path == "/activities"]
        return report, len(requests)

    def stuck_notes(self, report):
        return [n for n in report["worth_a_look"] if n["kind"] == "task_not_progressing"]

    def test_nothing_running(self):
        report, requests = self.run_checks([])
        self.assertEqual(report["background"]["running_now"], [])
        self.assertEqual((requests, self.waits), (1, []))

    def test_task_without_progress_is_not_watched(self):
        report, requests = self.run_checks([task(progress=None)])
        self.assertIsNone(report["background"]["running_now"][0]["progress_moved"])
        self.assertEqual((requests, self.waits), (1, []))

    def test_dvr_tasks_are_not_watched(self):
        recording = task(94, "Live TV - Session", uuid="rec-uuid", title="Recording")
        recording["type"] = "grabber.grab"
        refresh = task(50, "Grabbing", uuid="sub-uuid", title="Refreshing Sub")
        refresh["type"] = "provider.subscription.refresh"
        report, requests = self.run_checks([recording, refresh])
        self.assertEqual([t["progress_moved"] for t in report["background"]["running_now"]], [None, None])
        self.assertEqual((requests, self.waits), (1, []))
        self.assertEqual(self.stuck_notes(report), [])

    def test_task_that_is_moving(self):
        report, requests = self.run_checks([task(40)], [task(55)])
        self.assertTrue(report["background"]["running_now"][0]["progress_moved"])
        self.assertEqual((requests, self.waits), (2, [15]))
        self.assertEqual(self.stuck_notes(report), [])

    def test_same_progress_new_item_counts_as_moving(self):
        report, _ = self.run_checks([task(40, "Arrival")], [task(40, "Blade Runner")])
        self.assertTrue(report["background"]["running_now"][0]["progress_moved"])

    def test_task_that_is_not_moving(self):
        report, _ = self.run_checks([task(40)], [task(40)])
        self.assertIs(report["background"]["running_now"][0]["progress_moved"], False)
        self.assertEqual(self.stuck_notes(report), [{
            "kind": "task_not_progressing", "seconds_between_checks": 15,
            "tasks": [{"title": "Scanning Movies", "progress_pct": 40}]}])

    def test_task_that_finished_during_the_wait(self):
        report, _ = self.run_checks([task(40)], [])
        self.assertIsNone(report["background"]["running_now"][0]["progress_moved"])
        self.assertEqual(self.stuck_notes(report), [])

    def test_task_that_only_shows_up_later_is_ignored(self):
        report, _ = self.run_checks([task(40)], [task(55), task(10, uuid="another-uuid", title="Other")])
        self.assertEqual([t["title"] for t in report["background"]["running_now"]], ["Scanning Movies"])

    def test_matched_by_type_and_title_without_uuid(self):
        report, _ = self.run_checks([task(40, uuid=None)], [task(40, uuid=None)])
        self.assertIs(report["background"]["running_now"][0]["progress_moved"], False)

    def test_tasks_that_cant_be_told_apart_are_not_compared(self):
        twins = [task(40, uuid=None), task(70, uuid=None)]
        report, _ = self.run_checks(twins, twins)
        self.assertEqual([t["progress_moved"] for t in report["background"]["running_now"]], [None, None])

    def test_check_turned_off(self):
        report, requests = self.run_checks([task(40)], stuck_wait=0)
        self.assertIsNone(report["background"]["running_now"][0]["progress_moved"])
        self.assertEqual((requests, self.waits), (1, []))

    def test_second_check_fails(self):
        report, _ = self.run_checks([task(40)], Reply("", status=500))
        self.assertEqual(report["background"]["running_now"][0]["progress_pct"], 40)
        self.assertIsNone(report["background"]["running_now"][0]["progress_moved"])
        self.assertEqual(self.stuck_notes(report), [])
        self.assertEqual(report["unavailable"], [
            {"part": "stuck task check", "reason": "Plex returned HTTP 500 for /activities."}])


class StuckWaitOption(OfflineTestCase):
    def parsed_wait(self, *argv):
        seen = {}

        def capture(client, args):
            seen["wait"] = args.stuck_wait
            return {}
        with mock.patch.object(sh, "load_config", return_value=("http://192.0.2.10:32400", FAKE_TOKEN, True)), \
                mock.patch.object(sh, "PlexClient"), mock.patch.object(sh, "build_report", capture), \
                mock.patch.object(sh.sys, "argv", ["server_health.py", *argv]), \
                mock.patch.object(sh.sys, "stdout"):
            self.assertEqual(sh.main(), 0)
        return seen["wait"]

    def test_default_and_limits(self):
        self.assertEqual(self.parsed_wait(), 15)
        self.assertEqual(self.parsed_wait("--stuck-wait", "9999"), 300)
        self.assertEqual(self.parsed_wait("--stuck-wait", "-5"), 0)
        self.assertEqual(self.parsed_wait("--stuck-wait", "0"), 0)
