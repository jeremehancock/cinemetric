"""watch-activity (openspec/specs/watch-activity/spec.md) and its settings rules."""

import argparse
import contextlib
import io
import json
import os
import sys
import time
from unittest import mock

from helpers import FAKE_API_KEY, FAKE_TOKEN, FakeServer, OfflineTestCase, Reply, fixture, load_script

wa = load_script("watch-activity")

PLEX = ("http://192.0.2.10:32400", FAKE_TOKEN, True)
TAUTULLI = ("http://192.0.2.10:8181", FAKE_API_KEY, True)


def args(**overrides):
    values = {"days": 7, "top": 10, "recent": 15, "source": "auto", "user": None}
    values.update(overrides)
    return argparse.Namespace(**values)


def config(plex=PLEX, tautulli=TAUTULLI, problem=None):
    return {"plex": plex, "tautulli": tautulli, "tautulli_problem": problem}


# ---------------------------------------------------------------- fake servers

def tautulli_route(data=None):
    """Answer Tautulli API calls from tests/fixtures/watch-activity/tautulli.json.

    History asked for one media type comes from "get_history:<type>", one page at a time.
    """
    data = data or fixture("watch-activity", "tautulli.json")

    def answer(seen):
        cmd = seen.query["cmd"]
        key = cmd
        if seen.query.get("stat_id"):
            key += ":" + seen.query["stat_id"]
        elif seen.query.get("y_axis"):
            key += ":" + seen.query["y_axis"]
        elif seen.query.get("media_type"):
            key += ":" + seen.query["media_type"]
        if key not in data:
            return {"response": {"result": "error", "message": f"no sample for {key}"}}
        answer = data[key]
        if seen.query.get("media_type"):
            start, length = int(seen.query["start"]), int(seen.query["length"])
            answer = dict(answer, data=answer["data"][start:start + length])
        return {"response": {"result": "success", "message": None, "data": answer}}
    return answer


def plex_routes():
    """Plex answers from tests/fixtures/watch-activity/plex.json.

    The fixture gives each play's time as "viewedDaysAgo"; it becomes Plex's viewedAt here so the
    report's date window doesn't depend on today's date.
    """
    data = fixture("watch-activity", "plex.json")
    now = time.time()
    history = data.pop("history")
    for view in history:
        view["viewedAt"] = int(now - view.pop("viewedDaysAgo") * 86400)

    def page(seen):
        start = int(seen.headers.get("x-plex-container-start", 0))
        size = int(seen.headers.get("x-plex-container-size", len(history)))
        return {"MediaContainer": {"Metadata": history[start:start + size]}}

    data["/status/sessions/history/all"] = page
    return data


class Network:
    """Route every client watch-activity builds through one FakeServer."""

    def __init__(self, test, routes):
        self.server = FakeServer(routes)
        real = wa.build_opener
        patcher = mock.patch.object(wa, "build_opener", lambda url, verify: self.server.attach(real(url, verify)))
        patcher.start()
        test.addCleanup(patcher.stop)


def both_working():
    routes = plex_routes()
    routes["/api/v2"] = tautulli_route()
    return routes


# ---------------------------------------------------------------- small helpers

class SmallHelpers(OfflineTestCase):
    def test_never_is_not_a_date(self):
        for never in (-1, 0, None, ""):
            self.assertIsNone(wa.when(never))
        self.assertIsNotNone(wa.when(1_700_000_000))

    def test_trend_compares_halves(self):
        daily = [{"plays": n} for n in (1, 2, 3, 4, 5)]
        self.assertEqual(wa.trend(daily), {"earlier_half_plays": 3, "recent_half_plays": 12})
        self.assertEqual(wa.trend([]), {"earlier_half_plays": 0, "recent_half_plays": 0})

    def test_stat_rows_accepts_a_list_or_a_single_group(self):
        rows = [{"title": "A"}]
        self.assertEqual(wa.stat_rows([{"stat_id": "top_tv", "rows": rows}], "top_tv"), rows)
        self.assertEqual(wa.stat_rows({"stat_id": "top_tv", "rows": rows}, "top_tv"), rows)
        self.assertEqual(wa.stat_rows([{"stat_id": "top_tv", "rows": rows}], "top_movies"), [])
        self.assertEqual(wa.stat_rows(None, "top_tv"), [])
        self.assertEqual(wa.stat_rows(["junk", {"stat_id": "top_tv", "rows": None}], "top_tv"), [])

    def test_hours(self):
        self.assertEqual(wa.hours(5400), 1.5)
        self.assertEqual(wa.hours(None), 0.0)


# ---------------------------------------------------------------- reports from each source

class TautulliReport(OfflineTestCase):
    def report(self, **options):
        Network(self, {"/api/v2": tautulli_route()})
        report, _ = wa.tautulli_report(wa.TautulliClient(*TAUTULLI), args(**options))
        return report

    def test_totals_leave_out_tautullis_own_total_series(self):
        report = self.report()
        self.assertEqual(report["totals"], {"plays": 13, "watch_hours": 9.0, "active_users": 2})
        self.assertEqual(report["plays_by_type"], {"movies": 5, "tv": 8})
        self.assertEqual([d["plays"] for d in report["daily"]], [3, 3, 3, 4])
        self.assertEqual([d["hours"] for d in report["daily"]], [2.0, 1.5, 2.5, 3.0])
        self.assertEqual(report["trend"], {"earlier_half_plays": 6, "recent_half_plays": 7})

    def test_top_lists(self):
        report = self.report()
        self.assertEqual(report["top_movies"], [{"title": "Arrival (2016)", "plays": 5, "hours": 10.0}])
        self.assertEqual(report["top_shows"], [{"title": "The Show", "plays": 8, "hours": 4.0}])
        self.assertEqual(report["top_music"], [])
        self.assertEqual([u["user"] for u in report["top_users"]], ["alex-test", "sam-test"])
        self.assertEqual(report["top_platforms"], [{"platform": "Roku", "plays": 10, "hours": 11.1}])

    def test_top_users_follow_the_top_option(self):
        self.assertEqual(len(self.report(top=1)["top_users"]), 1)

    def test_peak_uses_the_all_streams_row(self):
        peak = self.report()["most_concurrent_streams"]
        self.assertEqual(peak["streams"], 3)

    def test_recent_plays(self):
        [play] = self.report()["recent_plays"]
        self.assertEqual(play["title"], "Arrival")
        self.assertEqual(play["minutes"], 100)
        self.assertEqual(play["method"], "direct stream")
        self.assertIs(play["live_tv"], False)
        self.assertNotIn("192.0.2.20", str(play))

    def test_api_key_goes_in_the_query_of_get_requests_only(self):
        network = Network(self, {"/api/v2": tautulli_route()})
        wa.tautulli_report(wa.TautulliClient(*TAUTULLI), args())
        for seen in network.server.requests:
            self.assertEqual(seen.method, "GET")
            self.assertIn(seen.query["cmd"], wa.TAUTULLI_COMMANDS)


class PlexReport(OfflineTestCase):
    def report(self, **options):
        network = Network(self, plex_routes())
        report, _ = wa.plex_report(wa.PlexClient(*PLEX), args(**options))
        return report, network.server

    def test_counts_only_plays_inside_the_period(self):
        report, _ = self.report()
        self.assertEqual(report["source"], "plex")
        self.assertEqual(report["totals"], {"plays": 4, "watch_hours": None, "active_users": 3})
        self.assertEqual(report["plays_by_type"], {"movies": 1, "tv": 2, "music": 1})
        self.assertEqual(len(report["daily"]), 7)
        self.assertEqual(sum(d["plays"] for d in report["daily"]), 4)
        self.assertFalse(report["history_capped"])

    def test_top_lists_and_user_names(self):
        report, _ = self.report()
        self.assertEqual(report["top_shows"], [{"title": "The Show", "plays": 2}])
        self.assertEqual(report["top_movies"], [{"title": "Arrival (2016)", "plays": 1}])
        self.assertEqual(report["top_music"], [{"title": "Test Band", "plays": 1}])
        users = {u["user"]: u["plays"] for u in report["top_users"]}
        self.assertEqual(users, {"alex-test": 2, "user 2": 1, "user 99": 1})

    def test_recent_plays_newest_first(self):
        report, _ = self.report(recent=2)
        self.assertEqual([p["title"] for p in report["recent_plays"]], ["Arrival (2016)", "The Show S01E02"])

    def test_stops_paging_once_past_the_period(self):
        with mock.patch.object(wa, "PLEX_PAGE_SIZE", 2):
            report, server = self.report()
        self.assertEqual(report["totals"]["plays"], 4)
        pages = [s for s in server.requests if s.path == "/status/sessions/history/all"]
        self.assertEqual([s.headers["x-plex-container-start"] for s in pages], ["0", "2", "4"])


# ---------------------------------------------------------------- busiest moment

class BusiestMoment(OfflineTestCase):
    def test_tautulli_gives_streams_and_transcodes(self):
        Network(self, {"/api/v2": tautulli_route()})
        report, _ = wa.tautulli_report(wa.TautulliClient(*TAUTULLI), args())
        peak = report["most_concurrent_streams"]
        self.assertEqual((peak["streams"], peak["transcodes"]), (3, 1))
        self.assertEqual(peak["when"], wa.when(1700000000))
        self.assertEqual(peak["transcodes_when"], wa.when(1699990000))
        self.assertIsNone(report["most_concurrent_streams_unavailable"])

    def test_transcodes_missing(self):
        data = fixture("watch-activity", "tautulli.json")
        for group in data["get_home_stats"]:
            if group["stat_id"] == "most_concurrent":
                group["rows"] = [r for r in group["rows"] if r["title"] == "Concurrent Streams"]
        Network(self, {"/api/v2": tautulli_route(data)})
        report, _ = wa.tautulli_report(wa.TautulliClient(*TAUTULLI), args())
        peak = report["most_concurrent_streams"]
        self.assertEqual(peak["streams"], 3)
        self.assertIsNone(peak["transcodes"])
        self.assertIsNone(peak["transcodes_when"])

    def test_plex_explains_why_there_is_none(self):
        Network(self, plex_routes())
        report, _ = wa.plex_report(wa.PlexClient(*PLEX), args())
        self.assertIsNone(report["most_concurrent_streams"])
        self.assertIn("started and stopped", report["most_concurrent_streams_unavailable"])


# ---------------------------------------------------------------- unfinished titles

class UnfinishedTitles(OfflineTestCase):
    def report(self, **options):
        network = Network(self, {"/api/v2": tautulli_route()})
        report, _ = wa.tautulli_report(wa.TautulliClient(*TAUTULLI), args(**options))
        return report, network.server

    def test_lists_only_titles_nobody_finished_newest_first(self):
        report, _ = self.report()
        self.assertEqual(report["unfinished"], [
            {"user": "Samantha", "title": "The Show - Second", "type": "episode",
             "furthest_pct": 5, "plays": 1, "last_played": wa.when(1700000700)},
            {"user": "Samantha", "title": "The Show - Pilot", "type": "episode",
             "furthest_pct": 50, "plays": 1, "last_played": wa.when(1700000600)},
            {"user": "alex-test", "title": "Blade Runner", "type": "movie",
             "furthest_pct": 35, "plays": 2, "last_played": wa.when(1700000200)},
        ])
        self.assertEqual(report["unfinished_count"], 3)
        self.assertFalse(report["unfinished_capped"])
        self.assertIsNone(report["unfinished_unavailable"])

    def test_finished_on_a_later_try_is_left_out(self):
        report, _ = self.report()
        self.assertNotIn("Dune", [u["title"] for u in report["unfinished"]])

    def test_live_tv_is_left_out(self):
        report, _ = self.report()
        self.assertNotIn("Live Thing", [u["title"] for u in report["unfinished"]])

    def test_top_option_limits_the_list_not_the_count(self):
        report, _ = self.report(top=1)
        self.assertEqual([u["title"] for u in report["unfinished"]], ["The Show - Second"])
        self.assertEqual(report["unfinished_count"], 3)

    def test_reads_grouped_movie_and_episode_history_in_pages(self):
        with mock.patch.object(wa, "TAUTULLI_PAGE_SIZE", 2):
            report, server = self.report()
        self.assertEqual(report["unfinished_count"], 3)
        pages = [s.query for s in server.requests if s.query.get("media_type")]
        self.assertEqual([(q["media_type"], q["start"]) for q in pages],
                         [("movie", "0"), ("movie", "2"), ("movie", "4"), ("episode", "0"), ("episode", "2")])
        self.assertTrue(all(q["grouping"] == "1" for q in pages))

    def test_stops_at_the_row_limit(self):
        with mock.patch.object(wa, "TAUTULLI_HISTORY_CAP", 4), mock.patch.object(wa, "TAUTULLI_PAGE_SIZE", 3):
            report, server = self.report()
        self.assertTrue(report["unfinished_capped"])
        pages = [s.query for s in server.requests if s.query.get("media_type")]
        self.assertEqual([(q["media_type"], q["length"]) for q in pages], [("movie", "3"), ("movie", "1")])

    def test_plex_explains_why_there_is_none(self):
        Network(self, plex_routes())
        report, _ = wa.plex_report(wa.PlexClient(*PLEX), args())
        self.assertIsNone(report["unfinished"])
        self.assertIsNone(report["unfinished_count"])
        self.assertIn("finished plays", report["unfinished_unavailable"])


# ---------------------------------------------------------------- one person

def person(name, *more, key=None):
    return {"name": name, "names": [name, *more], "id": key or name}


class PickingAPerson(OfflineTestCase):
    people = [person("alex-test", "alex"), person("Samantha", "sam-test"), person("Sammy", "sammy")]

    def test_exact_name_in_a_different_case(self):
        self.assertEqual(wa.pick_person("ALEX-TEST", self.people, "Plex")["name"], "alex-test")

    def test_any_of_a_persons_names(self):
        self.assertEqual(wa.pick_person("sam-test", self.people, "Plex")["name"], "Samantha")

    def test_part_of_a_name(self):
        self.assertEqual(wa.pick_person("manth", self.people, "Plex")["name"], "Samantha")

    def test_exact_name_wins_over_a_longer_one(self):
        people = self.people + [person("Sam")]
        self.assertEqual(wa.pick_person("sam", people, "Plex")["name"], "Sam")

    def test_two_people_match(self):
        with self.assertRaises(wa.PersonError) as caught:
            wa.pick_person("sam", self.people, "Tautulli")
        message = str(caught.exception)
        self.assertTrue(message.startswith("USER_AMBIGUOUS"))
        self.assertIn("Samantha", message)
        self.assertIn("Sammy", message)

    def test_nobody_matches_lists_known_names(self):
        with self.assertRaises(wa.PersonError) as caught:
            wa.pick_person("zed", self.people, "Tautulli")
        message = str(caught.exception)
        self.assertTrue(message.startswith("USER_NOT_FOUND"))
        self.assertIn("alex-test, Samantha, Sammy", message)

    def test_known_names_are_limited(self):
        people = [person(f"user{n:02d}") for n in range(40)]
        with self.assertRaises(wa.PersonError) as caught:
            wa.pick_person("zed", people, "Plex")
        self.assertIn("user29", str(caught.exception))
        self.assertNotIn("user30", str(caught.exception))


class OnePerson(OfflineTestCase):
    def test_tautulli_sends_their_id_with_every_history_and_stats_request(self):
        network = Network(self, {"/api/v2": tautulli_route()})
        report, chosen = wa.tautulli_report(wa.TautulliClient(*TAUTULLI), args(user="sam-test"))
        self.assertEqual(report["user"], "Samantha")
        self.assertEqual(chosen["names"], ["Samantha", "sam-test"])
        narrowed = [s.query for s in network.server.requests
                    if s.query["cmd"] in ("get_home_stats", "get_plays_by_date", "get_history")]
        self.assertGreater(len(narrowed), 5)
        self.assertTrue(all(q.get("user_id") == "2" for q in narrowed))

    def test_tautulli_leaves_out_the_server_wide_peak(self):
        Network(self, {"/api/v2": tautulli_route()})
        report, _ = wa.tautulli_report(wa.TautulliClient(*TAUTULLI), args(user="alex-test"))
        self.assertIsNone(report["most_concurrent_streams"])
        self.assertIn("whole server", report["most_concurrent_streams_unavailable"])

    def test_plex_counts_only_their_plays(self):
        Network(self, plex_routes())
        report, _ = wa.plex_report(wa.PlexClient(*PLEX), args(user="alex-test"))
        self.assertEqual(report["user"], "alex-test")
        self.assertEqual(report["totals"], {"plays": 2, "watch_hours": None, "active_users": 1})
        self.assertEqual(report["top_users"], [{"user": "alex-test", "plays": 2}])
        self.assertEqual({p["user"] for p in report["recent_plays"]}, {"alex-test"})
        self.assertEqual(sum(d["plays"] for d in report["daily"]), 2)

    def test_everyone_without_a_name(self):
        Network(self, both_working())
        self.assertIsNone(wa.build_report(config(), args())["user"])

    def test_plex_nobody_matches(self):
        Network(self, plex_routes())
        with self.assertRaises(wa.PersonError) as caught:
            wa.build_report(config(tautulli=None), args(user="zed"))
        self.assertTrue(str(caught.exception).startswith("USER_NOT_FOUND"))

    def test_unknown_name_with_tautulli_does_not_fall_back_to_plex(self):
        network = Network(self, both_working())
        with self.assertRaises(wa.PersonError) as caught:
            wa.build_report(config(), args(user="zed"))
        self.assertTrue(str(caught.exception).startswith("USER_NOT_FOUND"))
        self.assertNotIn("/status/sessions/history/all", [s.path for s in network.server.requests])

    def test_a_name_containing_401_is_not_owner_only(self):
        routes = plex_routes()
        routes["/accounts"] = {"MediaContainer": {"Account": [{"id": 1, "name": "fan401"}]}}
        Network(self, routes)
        with self.assertRaises(wa.ReportError) as caught:
            wa.build_report(config(tautulli=None), args(user="zed"))
        self.assertTrue(str(caught.exception).startswith("USER_NOT_FOUND"))

    def test_watching_now_keeps_only_their_session(self):
        Network(self, both_working())
        report = wa.build_report(config(), args(user="Samantha"))
        self.assertEqual([s["user"] for s in report["now_watching"]], ["sam-test"])
        report = wa.build_report(config(tautulli=None), args(user="alex-test"))
        self.assertEqual([s["user"] for s in report["now_watching"]], ["alex-test"])

    def test_check_ignores_the_name(self):
        Network(self, both_working())
        out = io.StringIO()
        with mock.patch.object(wa, "load_config", return_value=config()), \
                mock.patch.object(sys, "argv", ["watch_activity.py", "--check", "--user", "zed"]), \
                contextlib.redirect_stdout(out):
            self.assertEqual(wa.main(), 0)
        self.assertTrue(json.loads(out.getvalue())["ok"])


# ---------------------------------------------------------------- choosing a source

class ChoosingASource(OfflineTestCase):
    def test_tautulli_is_used_when_set_up(self):
        Network(self, both_working())
        report = wa.build_report(config(), args())
        self.assertEqual(report["source"], "tautulli")
        self.assertIsNone(report["fallback_reason"])
        self.assertEqual(report["period_days"], 7)

    def test_plex_is_used_when_tautulli_is_not_set_up(self):
        Network(self, both_working())
        report = wa.build_report(config(tautulli=None), args())
        self.assertEqual(report["source"], "plex")
        self.assertEqual(report["fallback_reason"], "Tautulli is not set up")

    def test_falls_back_to_plex_when_tautulli_fails(self):
        routes = plex_routes()
        routes["/api/v2"] = Reply("", status=500)
        Network(self, routes)
        report = wa.build_report(config(), args())
        self.assertEqual(report["source"], "plex")
        self.assertTrue(report["fallback_reason"].startswith("Tautulli is configured but failed"))

    def test_falls_back_when_tautulli_sends_an_unexpected_shape(self):
        data = fixture("watch-activity", "tautulli.json")
        data["get_plays_by_date:plays"] = ["not", "a", "dict"]
        routes = plex_routes()
        routes["/api/v2"] = tautulli_route(data)
        Network(self, routes)
        report = wa.build_report(config(), args())
        self.assertEqual(report["source"], "plex")
        self.assertIn("didn't expect", report["fallback_reason"])

    def test_falls_back_when_tautulli_settings_cant_be_read(self):
        Network(self, both_working())
        report = wa.build_report(config(tautulli=None, problem="file is damaged"), args())
        self.assertEqual(report["source"], "plex")
        self.assertIn("file is damaged", report["fallback_reason"])

    def test_tautulli_only_without_tautulli(self):
        Network(self, both_working())
        with self.assertRaises(wa.ReportError) as caught:
            wa.build_report(config(tautulli=None), args(source="tautulli"))
        self.assertTrue(str(caught.exception).startswith("TAUTULLI_NOT_CONFIGURED"))

    def test_tautulli_only_when_tautulli_fails(self):
        routes = plex_routes()
        routes["/api/v2"] = Reply("", status=500)
        Network(self, routes)
        with self.assertRaises(wa.ReportError):
            wa.build_report(config(), args(source="tautulli"))

    def test_plex_only_skips_tautulli(self):
        network = Network(self, both_working())
        report = wa.build_report(config(), args(source="plex"))
        self.assertEqual(report["source"], "plex")
        self.assertFalse(any(s.path == "/api/v2" for s in network.server.requests))

    def test_no_plex_and_no_working_tautulli(self):
        Network(self, {})
        with self.assertRaises(wa.ReportError) as caught:
            wa.build_report(config(plex=None, tautulli=None, problem=None), args())
        self.assertTrue(str(caught.exception).startswith("NOT_CONFIGURED"))

    def test_history_limited_to_the_owner(self):
        routes = plex_routes()
        routes["/status/sessions/history/all"] = Reply("", status=403)
        Network(self, routes)
        with self.assertRaises(wa.ReportError) as caught:
            wa.build_report(config(tautulli=None), args())
        self.assertTrue(str(caught.exception).startswith("OWNER_ONLY"))

    def test_bad_token_is_not_reported_as_owner_only(self):
        Network(self, {"/": Reply("", status=401), "/accounts": Reply("", status=401)})
        with self.assertRaises(wa.ReportError) as caught:
            wa.build_report(config(tautulli=None), args())
        self.assertNotIn("OWNER_ONLY", str(caught.exception))
        self.assertIn("401", str(caught.exception))


# ---------------------------------------------------------------- watching now

class WatchingNow(OfflineTestCase):
    def test_two_people_watching(self):
        Network(self, both_working())
        report = wa.build_report(config(tautulli=None), args())
        self.assertIsNone(report["now_watching_unavailable"])
        self.assertEqual(report["now_watching"], [
            {"user": "alex-test", "title": "Severance S02E03", "type": "episode",
             "player": "Living Room TV", "platform": "Roku", "state": "playing",
             "progress_pct": 50, "live_tv": False},
            {"user": "sam-test", "title": "Arrival (2016)", "type": "movie",
             "player": "Plex Web", "platform": "Chrome", "state": "paused",
             "progress_pct": 10, "live_tv": False},
        ])

    def test_leaves_technical_details_to_server_health(self):
        Network(self, both_working())
        for session in wa.build_report(config(tautulli=None), args())["now_watching"]:
            for field in ("method", "bandwidth_kbps", "source_quality", "transcode", "location"):
                self.assertNotIn(field, session)

    def test_nothing_playing(self):
        routes = plex_routes()
        routes["/status/sessions"] = {"MediaContainer": {"size": 0}}
        Network(self, routes)
        report = wa.build_report(config(tautulli=None), args())
        self.assertEqual(report["now_watching"], [])
        self.assertIsNone(report["now_watching_unavailable"])

    def test_tautulli_source_reads_sessions_from_plex(self):
        network = Network(self, both_working())
        report = wa.build_report(config(), args())
        self.assertEqual(report["source"], "tautulli")
        self.assertEqual(len(report["now_watching"]), 2)
        self.assertIn("/status/sessions", [s.path for s in network.server.requests])
        self.assertNotIn("get_activity", [s.query.get("cmd") for s in network.server.requests])

    def test_shared_server_with_tautulli(self):
        routes = both_working()
        routes["/status/sessions"] = Reply("", status=403)
        Network(self, routes)
        report = wa.build_report(config(), args())
        self.assertEqual(report["source"], "tautulli")
        self.assertIsNone(report["now_watching"])
        self.assertEqual(report["now_watching_unavailable"], "only available to the server owner's account")

    def test_tautulli_only_no_plex(self):
        Network(self, {"/api/v2": tautulli_route()})
        report = wa.build_report(config(plex=None), args())
        self.assertEqual(report["source"], "tautulli")
        self.assertIsNone(report["now_watching"])
        self.assertEqual(report["now_watching_unavailable"], "Plex is not set up")

    def test_sessions_error_keeps_the_history_report(self):
        routes = plex_routes()
        routes["/status/sessions"] = Reply("", status=500)
        Network(self, routes)
        report = wa.build_report(config(tautulli=None), args())
        self.assertEqual(report["totals"]["plays"], 4)
        self.assertIsNone(report["now_watching"])
        self.assertIn("500", report["now_watching_unavailable"])

    def test_unexpected_session_shape_keeps_the_history_report(self):
        routes = plex_routes()
        routes["/status/sessions"] = {"MediaContainer": {"Metadata": ["not a session"]}}
        Network(self, routes)
        report = wa.build_report(config(tautulli=None), args())
        self.assertIsNone(report["now_watching"])
        self.assertIn("didn't expect", report["now_watching_unavailable"])

    def test_refused_sessions_are_not_owner_only(self):
        routes = plex_routes()
        routes["/status/sessions"] = Reply("", status=401)
        Network(self, routes)
        report = wa.build_report(config(tautulli=None), args())
        self.assertEqual(report["source"], "plex")
        self.assertEqual(report["now_watching_unavailable"], "only available to the server owner's account")


class ConnectionCheck(OfflineTestCase):
    def test_does_not_read_current_sessions(self):
        network = Network(self, both_working())
        wa.check(config())
        self.assertNotIn("/status/sessions", [s.path for s in network.server.requests])

    def test_reports_both_connections(self):
        Network(self, both_working())
        self.assertEqual(wa.check(config()), {
            "ok": True,
            "plex": {"server": "Test Server", "version": "1.40.0.0000-test"},
            "tautulli": {"ok": True, "version": "v2.14.0-test"},
        })

    def test_tautulli_problem_is_reported_not_raised(self):
        routes = plex_routes()
        routes["/api/v2"] = Reply("", status=401)
        Network(self, routes)
        result = wa.check(config())
        self.assertFalse(result["ok"])
        self.assertFalse(result["tautulli"]["ok"])


# ---------------------------------------------------------------- settings

class Settings(OfflineTestCase):
    def test_environment_wins_over_the_file(self):
        self.write_config({"plex_url": "http://192.0.2.99:32400", "plex_token": "file-token"})
        os.environ.update({"PLEX_URL": "http://192.0.2.10:32400", "PLEX_TOKEN": FAKE_TOKEN})
        self.assertEqual(wa.load_config()["plex"], ("http://192.0.2.10:32400", FAKE_TOKEN, True))

    def test_reads_plex_and_tautulli_from_the_file(self):
        self.write_config({"plex_url": "http://192.0.2.10:32400/", "plex_token": FAKE_TOKEN,
                           "verify_tls": False, "tautulli_url": "https://192.0.2.10:8181",
                           "tautulli_api_key": FAKE_API_KEY, "tautulli_verify_tls": False})
        result = wa.load_config()
        self.assertEqual(result["plex"], ("http://192.0.2.10:32400", FAKE_TOKEN, False))
        self.assertEqual(result["tautulli"], ("https://192.0.2.10:8181", FAKE_API_KEY, False))

    def test_nothing_configured(self):
        with self.assertRaises(wa.ReportError) as caught:
            wa.load_config()
        self.assertTrue(str(caught.exception).startswith("NOT_CONFIGURED"))

    def test_file_readable_by_others_is_refused(self):
        if os.name != "posix":
            self.skipTest("file permissions are only checked on POSIX")
        self.write_config({"plex_url": "http://192.0.2.10:32400", "plex_token": FAKE_TOKEN}, mode=0o644)
        with self.assertRaises(wa.ReportError) as caught:
            wa.load_config()
        self.assertIn("chmod 600", str(caught.exception))

    def test_unsafe_file_only_costs_tautulli_when_plex_comes_from_the_environment(self):
        if os.name != "posix":
            self.skipTest("file permissions are only checked on POSIX")
        self.write_config({"tautulli_url": "http://192.0.2.10:8181", "tautulli_api_key": FAKE_API_KEY}, mode=0o644)
        os.environ.update({"PLEX_URL": "http://192.0.2.10:32400", "PLEX_TOKEN": FAKE_TOKEN})
        result = wa.load_config()
        self.assertIsNotNone(result["plex"])
        self.assertIsNone(result["tautulli"])
        self.assertIn("chmod 600", result["tautulli_problem"])

    def test_file_is_not_read_when_the_environment_has_everything(self):
        self.write_config({"plex_url": "http://192.0.2.10:32400"}, mode=0o644)
        os.environ.update({"PLEX_URL": "http://192.0.2.10:32400", "PLEX_TOKEN": FAKE_TOKEN,
                           "TAUTULLI_URL": "http://192.0.2.10:8181", "TAUTULLI_API_KEY": FAKE_API_KEY})
        with mock.patch.object(wa, "read_config_file", side_effect=AssertionError("file was read")):
            result = wa.load_config()
        self.assertIsNone(result["tautulli_problem"])
