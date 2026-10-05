"""unwatched (openspec/specs/unwatched/spec.md)."""

import argparse
import contextlib
import io
import json
import sys
import time
from unittest import mock

from helpers import FAKE_API_KEY, FAKE_TOKEN, FakeServer, OfflineTestCase, Reply, fixture, load_script

uw = load_script("unwatched")

PLEX = ("http://192.0.2.10:32400", FAKE_TOKEN, True)
TAUTULLI = ("http://192.0.2.10:8181", FAKE_API_KEY, True)
DAY = 86400
GB = 1_000_000_000


def args(**overrides):
    values = {"months": 6, "library": None, "limit": 25, "source": "auto"}
    values.update(overrides)
    return argparse.Namespace(**values)


def config(plex=PLEX, tautulli=TAUTULLI, problem=None):
    return {"plex": plex, "tautulli": tautulli, "tautulli_problem": problem}


# ---------------------------------------------------------------- fake servers

def with_real_values(item, now):
    """Turn the fixture's addedDaysAgo and gb shorthands into Plex's addedAt and part sizes."""
    item = json.loads(json.dumps(item))
    if "addedDaysAgo" in item:
        item["addedAt"] = int(now - item.pop("addedDaysAgo") * DAY)
    for media in item.get("Media", []):
        for part in media.get("Part", []):
            part["size"] = int(part.pop("gb") * GB)
    return item


def paged(items, key="Metadata"):
    def page(seen):
        start = int(seen.headers.get("x-plex-container-start", 0))
        size = int(seen.headers.get("x-plex-container-size", len(items)))
        return {"MediaContainer": {key: items[start:start + size], "totalSize": len(items)}}
    return page


def plex_routes(now, history=None):
    data = fixture("unwatched", "plex.json")
    movies = [with_real_values(m, now) for m in data["movies"]]
    episodes = [with_real_values(e, now) for e in data["episodes"]]
    if history is None:
        history = data["history"]
    history = [dict(v, viewedAt=int(now - v["viewedDaysAgo"] * DAY)) for v in history]

    return {
        "/": data["/"],
        "/library/sections": data["/library/sections"],
        "/library/sections/1/all": paged(movies),
        "/library/sections/2/all": paged(episodes),
        "/status/sessions/history/all": paged(history),
    }


def tautulli_route(now, data=None):
    data = data or fixture("unwatched", "tautulli.json")

    def answer(seen):
        cmd = seen.query["cmd"]
        key = cmd + (":" + seen.query["media_type"] if seen.query.get("media_type") else "")
        if key not in data:
            return {"response": {"result": "error", "message": f"no sample for {key}"}}
        answer = data[key]
        if cmd == "get_history":
            rows = [dict(r, date=int(now - r["daysAgo"] * DAY), stopped=int(now - r["daysAgo"] * DAY))
                    for r in answer]
            start, length = int(seen.query["start"]), int(seen.query["length"])
            answer = {"data": rows[start:start + length]}
        return {"response": {"result": "success", "message": None, "data": answer}}
    return answer


class Network:
    """Route every client the script builds through one FakeServer."""

    def __init__(self, test, routes):
        self.server = FakeServer(routes)
        real = uw.build_opener
        patcher = mock.patch.object(uw, "build_opener", lambda url, verify: self.server.attach(real(url, verify)))
        patcher.start()
        test.addCleanup(patcher.stop)


class Base(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.now = time.time()

    def network(self, tautulli=True, history=None):
        routes = plex_routes(self.now, history)
        if tautulli:
            routes["/api/v2"] = tautulli_route(self.now)
        return Network(self, routes)

    def report(self, cfg=None, **kw):
        return uw.build_report(cfg or config(), args(**kw), now=self.now)

    @staticmethod
    def library(report, name):
        return next(lib for lib in report["libraries"] if lib["name"] == name)

    @staticmethod
    def titles(lib):
        return [t["title"] for t in lib["titles"]]


# ---------------------------------------------------------------- sources

class Sources(Base):
    def test_only_allowed_requests(self):
        net = self.network()
        self.report()
        for seen in net.server.requests:
            self.assertEqual(seen.method, "GET")
            if seen.path == "/api/v2":
                self.assertEqual(seen.query["cmd"], "get_history")
            else:
                self.assertTrue(any(rule.match(seen.path) for rule in uw.ALLOWED_PATHS), seen.path)
        paths = {s.path for s in net.server.requests}
        self.assertNotIn("/status/sessions/history/all", paths)

    def test_library_items_are_read_in_pages_of_500(self):
        net = self.network()
        self.report()
        listings = [s for s in net.server.requests if s.path.endswith("/all") and "sections" in s.path]
        self.assertTrue(listings)
        for seen in listings:
            self.assertEqual(seen.headers["x-plex-container-size"], "500")

    def test_tautulli_only_is_not_configured(self):
        self.network()
        with self.assertRaises(uw.ReportError) as caught:
            self.report(config(plex=None))
        self.assertTrue(str(caught.exception).startswith("NOT_CONFIGURED: "))

    def test_auto_uses_tautulli(self):
        self.network()
        report = self.report()
        self.assertEqual(report["source"], "tautulli")
        self.assertIsNone(report["fallback_reason"])

    def test_auto_without_tautulli_uses_plex(self):
        self.network(tautulli=False)
        report = self.report(config(tautulli=None))
        self.assertEqual(report["source"], "plex")
        self.assertEqual(report["fallback_reason"], "Tautulli is not set up")

    def test_tautulli_down_falls_back_to_plex(self):
        net = self.network()
        net.server.routes["/api/v2"] = Reply("", status=500)
        report = self.report()
        self.assertEqual(report["source"], "plex")
        self.assertIn("failed", report["fallback_reason"])

    def test_tautulli_asked_for_but_not_set_up(self):
        self.network(tautulli=False)
        with self.assertRaises(uw.ReportError) as caught:
            self.report(config(tautulli=None), source="tautulli")
        self.assertTrue(str(caught.exception).startswith("TAUTULLI_NOT_CONFIGURED: "))

    def test_tautulli_asked_for_and_down_does_not_fall_back(self):
        net = self.network()
        net.server.routes["/api/v2"] = Reply("", status=500)
        with self.assertRaises(uw.ReportError):
            self.report(source="tautulli")

    def test_settings_problem_is_the_fallback_reason(self):
        self.network(tautulli=False)
        report = self.report(config(tautulli=None, problem="file damaged"))
        self.assertIn("file damaged", report["fallback_reason"])

    def test_plex_only(self):
        net = self.network()
        report = self.report(source="plex")
        self.assertEqual(report["source"], "plex")
        self.assertNotIn("/api/v2", {s.path for s in net.server.requests})

    def test_owner_only(self):
        net = self.network(tautulli=False)
        net.server.routes["/status/sessions/history/all"] = Reply("", status=403)
        with self.assertRaises(uw.ReportError) as caught:
            self.report(config(tautulli=None))
        self.assertTrue(str(caught.exception).startswith("OWNER_ONLY: "))


# ---------------------------------------------------------------- which plays count and which titles are listed

class Listing(Base):
    """The fixture is built so both sources give the same answer."""

    def each_source(self):
        for source in ("tautulli", "plex"):
            with self.subTest(source=source):
                self.network()
                yield self.report(source=source)

    def test_movies_listed(self):
        for report in self.each_source():
            movies = self.library(report, "Movies")
            self.assertEqual(self.titles(movies), [
                "Two Versions (2013)", "Old Unplayed (2010)", "Optimized (2017)",
                "Finished Long Ago (2012)", "Half Watched (2016)",
            ])

    def test_started_but_not_finished_is_listed(self):
        self.network()
        movies = self.library(self.report(source="tautulli"), "Movies")
        half = next(t for t in movies["titles"] if t["title"] == "Half Watched (2016)")
        self.assertIsNone(half["last_finished"])

    def test_partly_watched_rows_never_count(self):
        history = uw.History()
        self.network()
        with mock.patch.object(uw, "History", return_value=history):
            self.report(source="tautulli")
        self.assertNotIn("108", history.last_finished)
        self.assertIn("102", history.last_finished)

    def test_live_tv_is_left_out(self):
        self.network()
        movies = self.library(self.report(source="tautulli"), "Movies")
        old = next(t for t in movies["titles"] if t["title"] == "Old Unplayed (2010)")
        self.assertIsNone(old["last_finished"])

    def test_friend_finished_it(self):
        for report in self.each_source():
            self.assertNotIn("Finished Recently (2011)", self.titles(self.library(report, "Movies")))

    def test_finished_long_ago_shows_the_date(self):
        for report in self.each_source():
            movies = self.library(report, "Movies")
            old = next(t for t in movies["titles"] if t["title"] == "Finished Long Ago (2012)")
            self.assertEqual(old["last_finished"], uw.day(self.now - 365 * DAY))

    def test_added_recently_missing_files_and_no_date_are_not_listed(self):
        for report in self.each_source():
            names = self.titles(self.library(report, "Movies"))
            for title in ("Added Recently (2024)", "All Missing (2014)", "No Added Date (2015)"):
                self.assertNotIn(title, names)

    def test_shows(self):
        for report in self.each_source():
            shows = self.library(report, "TV Shows")
            self.assertEqual(shows["titles"], [{
                "title": "Old Show", "added": uw.day(self.now - 690 * DAY), "gb": 3.0,
                "last_finished": None, "episodes": 2,
            }])
            self.assertEqual(shows["items"], 3)

    def test_sizes(self):
        self.network()
        movies = self.library(self.report(), "Movies")
        sizes = {t["title"]: t["gb"] for t in movies["titles"]}
        self.assertEqual(sizes["Two Versions (2013)"], 72.0)
        self.assertEqual(sizes["Optimized (2017)"], 8.0)

    def test_music_is_skipped(self):
        self.network()
        report = self.report()
        self.assertEqual(report["skipped_libraries"], [{"name": "Music", "type": "artist"}])
        self.assertEqual([lib["name"] for lib in report["libraries"]], ["Movies", "TV Shows"])

    def test_shorter_cutoff(self):
        self.network()
        movies = self.library(self.report(months=1), "Movies")
        self.assertIn("Added Recently (2024)", self.titles(movies))

    def test_empty_history(self):
        self.network(tautulli=False, history=[])
        report = self.report(config(tautulli=None))
        self.assertIsNone(report["history_since"])
        movies = self.library(report, "Movies")
        self.assertIn("Finished Recently (2011)", self.titles(movies))
        self.assertTrue(all(t["last_finished"] is None for t in movies["titles"]))

    def test_history_cap(self):
        self.network(tautulli=False)
        with mock.patch.object(uw, "HISTORY_CAP", 2):
            report = self.report(config(tautulli=None))
        self.assertTrue(report["history_capped"])
        self.assertEqual(report["history_since"], uw.day(self.now - 31 * DAY))

    def test_history_not_capped(self):
        self.network()
        report = self.report()
        self.assertFalse(report["history_capped"])
        self.assertEqual(report["history_since"], uw.day(self.now - 365 * DAY))


# ---------------------------------------------------------------- report contents

class Contents(Base):
    def test_library_counts(self):
        self.network()
        report = self.report()
        movies = self.library(report, "Movies")
        self.assertEqual(movies["type"], "movie")
        self.assertEqual(movies["items"], 9)
        self.assertEqual(movies["library_gb"], 112.0)
        self.assertEqual(movies["unwatched"], 5)
        self.assertEqual(movies["unwatched_gb"], 95.0)
        self.assertEqual(movies["unwatched_pct"], 84.8)
        self.assertEqual(movies["never_finished"], 4)
        self.assertEqual(movies["never_finished_gb"], 90.0)

    def test_totals(self):
        self.network()
        report = self.report()
        self.assertEqual(report["totals"], {
            "unwatched": 6, "unwatched_gb": 98.0, "library_gb": 122.0, "unwatched_pct": 80.3,
            "never_finished": 5, "never_finished_gb": 93.0,
        })

    def test_top_level_fields(self):
        self.network()
        report = self.report()
        self.assertEqual(report["server"], {"name": "Test Server", "version": "1.40.0.0000"})
        self.assertEqual(report["months"], 6)
        self.assertEqual(report["cutoff"], uw.day(uw.months_before(self.now, 6)))
        for field in ("cinemetric_version", "generated_at", "fallback_reason", "history_since",
                      "history_capped"):
            self.assertIn(field, report)

    def test_limit_keeps_the_counts(self):
        self.network()
        movies = self.library(self.report(limit=2), "Movies")
        self.assertEqual(self.titles(movies), ["Two Versions (2013)", "Old Unplayed (2010)"])
        self.assertEqual(movies["unwatched"], 5)

    def test_nothing_qualifies(self):
        self.network()
        report = self.report(months=120)
        for lib in report["libraries"]:
            self.assertEqual(lib["unwatched"], 0)
            self.assertEqual(lib["titles"], [])

    def test_no_person_names(self):
        for source in ("tautulli", "plex"):
            with self.subTest(source=source):
                self.network()
                text = json.dumps(self.report(source=source)) + self.stderr.getvalue()
                for name in ("friend-alex", "Alex Friend", "friend-sam", "Sam Friend", "owner-pat", "Pat Owner"):
                    self.assertNotIn(name, text)

    def test_library_option(self):
        self.network()
        report = self.report(library=["movies"])
        self.assertEqual([lib["name"] for lib in report["libraries"]], ["Movies"])
        self.assertEqual(report["skipped_libraries"], [])

    def test_unknown_library(self):
        self.network()
        with self.assertRaises(uw.ReportError) as caught:
            self.report(library=["Cartoons"])
        self.assertIn("No library matched", str(caught.exception))

    def test_music_library_asked_for(self):
        self.network()
        with self.assertRaises(uw.ReportError) as caught:
            self.report(library=["Music"])
        self.assertIn("Only movie and TV libraries", str(caught.exception))


class Cutoff(OfflineTestCase):
    def test_same_date_months_ago(self):
        now = time.mktime((2026, 10, 5, 12, 0, 0, 0, 0, -1))
        self.assertEqual(uw.day(uw.months_before(now, 6)), "2026-04-05")
        self.assertEqual(uw.day(uw.months_before(now, 12)), "2025-10-05")

    def test_clamped_to_the_end_of_a_short_month(self):
        now = time.mktime((2026, 8, 31, 12, 0, 0, 0, 0, -1))
        self.assertEqual(uw.day(uw.months_before(now, 6)), "2026-02-28")


# ---------------------------------------------------------------- command line

class CommandLine(Base):
    def run_main(self, *argv, cfg=None):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["unwatched.py", *argv]), \
                mock.patch.object(uw, "load_config", return_value=cfg or config()), \
                contextlib.redirect_stdout(out):
            code = uw.main()
        return code, out.getvalue()

    def test_limit_is_capped_at_500(self):
        self.network()
        with mock.patch.object(uw, "build_report", wraps=uw.build_report) as build:
            code, _ = self.run_main("--limit", "9999")
        self.assertEqual(code, 0)
        self.assertEqual(build.call_args[0][1].limit, 500)

    def test_months_are_limited(self):
        self.network()
        with mock.patch.object(uw, "build_report", wraps=uw.build_report) as build:
            self.run_main("--months", "0")
        self.assertEqual(build.call_args[0][1].months, 1)

    def test_check(self):
        self.network()
        code, out = self.run_main("--check")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["plex"]["server"], "Test Server")
        self.assertEqual(result["tautulli"], {"ok": True, "version": "v2.18.2"})

    def test_check_with_tautulli_key_rejected(self):
        net = self.network()
        net.server.routes["/api/v2"] = Reply("", status=401)
        code, out = self.run_main("--check")
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertFalse(result["ok"])
        self.assertFalse(result["tautulli"]["ok"])
        self.assertEqual(result["plex"]["server"], "Test Server")

    def test_errors_go_to_stderr(self):
        net = self.network(tautulli=False)
        net.server.routes["/status/sessions/history/all"] = Reply("", status=403)
        code, out = self.run_main(cfg=config(tautulli=None))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("error: OWNER_ONLY: ", self.stderr.getvalue())
