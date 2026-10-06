"""playback-check (openspec/specs/playback-check/spec.md)."""

import argparse
import json
import time
import urllib.parse
from unittest import mock

from helpers import FAKE_API_KEY, FAKE_TOKEN, FakeServer, OfflineTestCase, Reply, Unreachable, fixture, load_script

pc = load_script("playback-check")

PLEX = ("http://192.0.2.10:32400", FAKE_TOKEN, True)
TAUTULLI = ("http://192.0.2.10:8181", FAKE_API_KEY, True)
DAY = 86400


def args(**overrides):
    values = {"library": None, "limit": 25, "max_bitrate": None, "days": 90}
    values.update(overrides)
    return argparse.Namespace(**values)


def config(plex=PLEX, tautulli=TAUTULLI, problem=None):
    return {"plex": plex, "tautulli": tautulli, "tautulli_problem": problem}


# ---------------------------------------------------------------- fake servers

def paged(items):
    def page(seen):
        start = int(seen.headers.get("x-plex-container-start", 0))
        size = int(seen.headers.get("x-plex-container-size", len(items)))
        return {"MediaContainer": {"Metadata": items[start:start + size], "totalSize": len(items)}}
    return page


def listing(data, seen):
    """The library listing for a section and type."""
    section, kind = seen.path.split("/")[3], seen.query.get("type")
    items = {("1", "1"): data["movies"], ("2", "4"): data["episodes"], ("2", "2"): data["shows"]}
    return paged(items.get((section, kind), []))(seen)


def details(data):
    def answer(seen):
        keys = seen.path.rsplit("/", 1)[-1].split(",")
        return {"MediaContainer": {"Metadata": [data["details"][k] for k in keys if k in data["details"]]}}
    return answer


def plex_routes(prefs="prefs_no_limit", data=None):
    data = data or fixture("playback-check", "plex.json")
    routes = {
        "/": data["/"],
        "/library/sections": data["/library/sections"],
        "/library/sections/1/all": lambda seen: listing(data, seen),
        "/library/sections/2/all": lambda seen: listing(data, seen),
        "/:/prefs": data[prefs] if isinstance(prefs, str) else prefs,
    }
    return routes, data


def tautulli_route(now, data=None):
    data = data or fixture("playback-check", "tautulli.json")

    def answer(seen):
        cmd = seen.query["cmd"]
        if cmd == "get_history":
            after = time.mktime(time.strptime(seen.query["after"], "%Y-%m-%d"))
            rows = [dict(r, date=int(now - r["daysAgo"] * DAY))
                    for r in data["get_history:" + seen.query["media_type"]]]
            rows = [r for r in rows if r["date"] >= after]
            start, length = int(seen.query["start"]), int(seen.query["length"])
            result = {"data": rows[start:start + length]}
        elif cmd == "get_stream_data":
            if seen.query["row_id"] not in data["get_stream_data"]:
                return {"response": {"result": "error", "message": "No stream data"}}
            result = data["get_stream_data"][seen.query["row_id"]]
        else:
            result = data[cmd]
        return {"response": {"result": "success", "message": None, "data": result}}
    return answer


class Network(FakeServer):
    """One FakeServer for every client the script builds.

    Detail paths change with the titles asked for (/library/metadata/1,2,3), so any path under
    /library/metadata/ is answered by `metadata`.
    """

    def __init__(self, test, routes, metadata=None):
        super().__init__(routes)
        self.metadata = metadata
        real = pc.build_opener
        patcher = mock.patch.object(pc, "build_opener", lambda url, verify: self.attach(real(url, verify)))
        patcher.start()
        test.addCleanup(patcher.stop)

    def default_open(self, request):
        path = urllib.parse.urlsplit(request.full_url).path
        if self.metadata and path.startswith("/library/metadata/"):
            self.routes[path] = self.metadata
        return super().default_open(request)


class Base(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.now = time.time()

    def network(self, tautulli=True, prefs="prefs_no_limit", data=None, tautulli_data=None):
        routes, data = plex_routes(prefs, data)
        if tautulli:
            routes["/api/v2"] = tautulli_route(self.now, tautulli_data) if tautulli is True else tautulli
        return Network(self, routes, metadata=details(data))

    def report(self, cfg=None, **kw):
        return pc.build_report(cfg or config(), args(**kw), now=self.now)

    @staticmethod
    def library(report, name):
        return next(lib for lib in report["libraries"] if lib["name"] == name)

    def movie(self, report, title):
        return next(m for m in self.library(report, "Movies")["listed"] if m["title"] == title)

    def listed_titles(self, report, name="Movies"):
        return [m["title"] for m in self.library(report, name)["listed"]]


# ---------------------------------------------------------------- sources

class Sources(Base):
    def test_only_allowed_paths_and_commands(self):
        net = self.network()
        self.report()
        for seen in net.requests:
            self.assertEqual(seen.method, "GET")
            if seen.path == "/api/v2":
                self.assertIn(seen.query["cmd"], pc.TAUTULLI_COMMANDS)
            else:
                self.assertTrue(any(rule.match(seen.path) for rule in pc.ALLOWED_PATHS), seen.path)

    def test_more_than_100_titles_in_one_request_is_blocked(self):
        net = self.network()
        client = pc.PlexClient(*PLEX)
        with self.assertRaises(pc.ReportError) as caught:
            client.get("/library/metadata/" + ",".join(str(n) for n in range(1, 102)))
        self.assertIn("allowlist", str(caught.exception))
        self.assertEqual(net.requests, [])

    def test_no_tautulli_request_without_tautulli(self):
        net = self.network(tautulli=False)
        report = self.report(config(tautulli=None))
        self.assertFalse(any(seen.path == "/api/v2" for seen in net.requests))
        self.assertIsNone(report["playback_history"])
        self.assertIn("Tautulli", report["playback_history_note"])
        self.assertTrue(report["libraries"])

    def test_details_are_read_100_at_a_time(self):
        data = fixture("playback-check", "plex.json")
        template = data["episodes"][0]
        data["episodes"] = [dict(template, ratingKey=str(5000 + n)) for n in range(250)]
        net = self.network(data=data)
        self.report(library=["TV Shows"])
        batches = [s for s in net.requests if s.path.startswith("/library/metadata/")]
        self.assertEqual([len(s.path.rsplit("/", 1)[-1].split(",")) for s in batches], [100, 100, 50])

    def test_only_the_remote_limit_is_read_from_prefs(self):
        self.network(prefs="prefs_with_limit")
        self.assertNotIn("pref-secret-value", json.dumps(self.report()))

    def test_prefs_not_requested_with_max_bitrate(self):
        net = self.network(prefs="prefs_with_limit")
        self.report(max_bitrate=8000)
        self.assertFalse(any(seen.path == "/:/prefs" for seen in net.requests))


# ---------------------------------------------------------------- libraries

class Libraries(Base):
    def test_music_library_is_skipped(self):
        self.network()
        report = self.report()
        self.assertEqual(report["skipped_libraries"], [{"name": "Music", "type": "artist"}])
        self.assertEqual([lib["name"] for lib in report["libraries"]], ["Movies", "TV Shows"])

    def test_asking_for_a_music_library(self):
        self.network()
        with self.assertRaises(pc.ReportError) as caught:
            self.report(library=["music"])
        self.assertIn("movie and TV", str(caught.exception))

    def test_no_library_matches(self):
        self.network()
        with self.assertRaises(pc.ReportError):
            self.report(library=["Nope"])

    def test_two_versions_are_checked_separately(self):
        self.network(prefs="prefs_with_limit")
        movie = self.movie(self.report(), "Two Versions")
        self.assertEqual(len(movie["files"]), 1)
        self.assertEqual(movie["files"][0]["resolution"], "4k")
        self.assertEqual(movie["files"][0]["causes"], ["truehd_audio", "over_bitrate_limit"])

    def test_unavailable_file_is_counted_not_checked(self):
        self.network()
        report = self.report()
        movies = self.library(report, "Movies")
        self.assertEqual(movies["unavailable"], 1)
        self.assertNotIn("Gone File", self.listed_titles(report))

    def test_title_missing_from_details_is_still_checked_for_audio(self):
        self.network()
        report = self.report()
        self.assertEqual(self.library(report, "Movies")["details_missing"], 1)
        movie = self.movie(report, "No Details")
        self.assertEqual(movie["files"][0]["causes"], ["dts_audio"])
        self.assertEqual(movie["files"][0]["audio"]["profile"], "dts")


# ---------------------------------------------------------------- causes

class Subtitles(Base):
    def setUp(self):
        super().setUp()
        self.network()
        self.out = self.report()

    def causes(self, title):
        listed = {m["title"]: m for m in self.library(self.out, "Movies")["listed"]}
        return listed[title]["files"][0]["causes"] if title in listed else []

    def test_only_image_subtitles_in_a_language(self):
        self.assertEqual(self.causes("Image Only"), ["image_subtitles"])
        self.assertEqual(self.movie(self.out, "Image Only")["files"][0]["image_subtitle_languages"], ["en"])

    def test_a_text_alternative_exists(self):
        self.assertEqual(self.causes("Image With Text"), [])
        self.assertEqual(self.library(self.out, "Movies")["image_subtitles_with_text"], 1)

    def test_forced_image_track(self):
        self.assertEqual(self.causes("Forced Image"), ["image_subtitles"])
        self.assertEqual(self.library(self.out, "Movies")["forced_image_subtitles"], 1)

    def test_default_image_track(self):
        self.assertEqual(self.causes("Default Image"), ["image_subtitles"])

    def test_separate_subtitle_file_counts(self):
        self.assertEqual(self.causes("Sidecar Sup"), ["image_subtitles"])
        self.assertEqual(self.movie(self.out, "Sidecar Sup")["files"][0]["image_subtitle_languages"], ["fr"])

    def test_text_subtitles_only(self):
        self.assertEqual(self.causes("Text Only"), [])

    def test_no_language_is_its_own_language(self):
        self.assertEqual(self.causes("No Language"), ["image_subtitles"])
        self.assertEqual(self.movie(self.out, "No Language")["files"][0]["image_subtitle_languages"], ["unknown"])


class Audio(Base):
    def setUp(self):
        super().setUp()
        self.network()
        self.out = self.report()

    def test_dts_hd_ma_with_an_ac3_track(self):
        f = self.movie(self.out, "DTS With AC3")["files"][0]
        self.assertEqual(f["causes"], ["dts_audio"])
        self.assertEqual(f["audio"], {"codec": "dca", "profile": "ma", "common_alternative": True})

    def test_truehd_with_nothing_else(self):
        f = self.movie(self.out, "TrueHD Only")["files"][0]
        self.assertEqual(f["causes"], ["truehd_audio"])
        self.assertFalse(f["audio"]["common_alternative"])

    def test_common_main_track(self):
        self.assertNotIn("EAC3 Main", self.listed_titles(self.out))


class Bitrate(Base):
    def test_server_limit(self):
        self.network(prefs="prefs_with_limit")
        report = self.report()
        self.assertEqual(report["bitrate_limit"], {"kbps": 12000, "source": "server"})
        self.assertIn("over_bitrate_limit", self.movie(report, "TrueHD Only")["files"][0]["causes"])
        self.assertEqual(self.library(report, "Movies")["over_bitrate_limit"], 2)

    def test_no_limit(self):
        self.network()
        report = self.report()
        self.assertIsNone(report["bitrate_limit"])
        self.assertEqual(report["totals"]["over_bitrate_limit"], 0)

    def test_limit_from_the_option(self):
        self.network()
        report = self.report(max_bitrate=5500)
        self.assertEqual(report["bitrate_limit"], {"kbps": 5500, "source": "option"})
        self.assertIn("over_bitrate_limit", self.movie(report, "Image Only")["files"][0]["causes"])
        self.assertNotIn("Clean Movie", self.listed_titles(report))

    def test_setting_cannot_be_read(self):
        self.network(prefs=Reply("", status=401))
        report = self.report()
        self.assertIsNone(report["bitrate_limit"])
        self.assertIn("401", report["bitrate_limit_problem"])
        self.assertTrue(report["libraries"])


# ---------------------------------------------------------------- report

class Report(Base):
    def test_shows_are_counted_per_episode(self):
        self.network()
        report = self.report()
        shows = {s["title"]: s for s in self.library(report, "TV Shows")["listed"]}
        self.assertEqual(set(shows), {"Subtitled Show", "DTS Show"})
        self.assertEqual(shows["DTS Show"]["episodes"], 3)
        self.assertEqual(shows["DTS Show"]["episodes_flagged"], 2)
        self.assertEqual(shows["DTS Show"]["dts_audio"], 2)
        self.assertEqual(shows["Subtitled Show"]["year"], 2010)

    def test_picture_causes_sort_first(self):
        self.network()
        titles = self.listed_titles(self.report())
        self.assertLess(titles.index("Image Only"), titles.index("DTS With AC3"))
        shows = self.listed_titles(self.report(), "TV Shows")
        self.assertEqual(shows, ["Subtitled Show", "DTS Show"])

    def test_movies_with_more_causes_then_bigger_files_come_first(self):
        data = fixture("playback-check", "plex.json")
        # Image Only also gets DTS audio (two causes); Forced Image becomes the biggest file.
        data["details"]["1001"]["Media"][0]["Part"][0]["Stream"][1]["codec"] = "dca"
        data["details"]["1003"]["Media"][0]["Part"][0]["size"] = int(12e9)
        self.network(data=data)
        titles = self.listed_titles(self.report())
        self.assertEqual(titles[:5], ["Image Only", "Forced Image", "Default Image", "No Language", "Sidecar Sup"])
        # After the picture conversions: the 60 GB TrueHD copy before the 4 GB audio-only files.
        self.assertEqual(titles[5], "Two Versions")

    def test_counts_and_totals(self):
        self.network()
        report = self.report()
        movies = self.library(report, "Movies")
        self.assertEqual(movies["titles"], 14)
        self.assertEqual(movies["files"], 14)  # 15 versions, one unavailable
        self.assertEqual(movies["image_subtitles"], 5)
        self.assertEqual(movies["truehd_audio"], 2)
        self.assertEqual(movies["dts_audio"], 2)
        self.assertEqual(movies["files_flagged"], 9)
        self.assertEqual(report["totals"]["files"], 21)
        self.assertEqual(report["totals"]["files_flagged"], 13)
        self.assertIn("likely", report["limits"])

    def test_clean_library(self):
        data = fixture("playback-check", "plex.json")
        data["movies"] = [m for m in data["movies"] if m["title"] == "Clean Movie"]
        self.network(data=data)
        movies = self.library(self.report(), "Movies")
        self.assertEqual(movies["files_flagged"], 0)
        self.assertEqual(movies["listed"], [])

    def test_limit_and_more(self):
        self.network()
        movies = self.library(self.report(limit=2), "Movies")
        self.assertEqual(len(movies["listed"]), 2)
        self.assertEqual(movies["more"], 7)

    def test_counts_only(self):
        self.network()
        movies = self.library(self.report(limit=0), "Movies")
        self.assertEqual(movies["listed"], [])
        self.assertEqual(movies["files_flagged"], 9)

    def test_no_file_paths_in_the_output(self):
        self.network(prefs="prefs_with_limit")
        self.assertNotIn("secret-path", json.dumps(self.report()))


# ---------------------------------------------------------------- history

class History(Base):
    def history(self, **kw):
        self.network(**kw)
        return self.report()["playback_history"]

    def test_device_and_person_groups(self):
        h = self.history()
        roku = next(d for d in h["devices"] if d["device"] == "Living Room")
        self.assertEqual((roku["app"], roku["platform"]), ("Plex for Roku", "Roku"))
        self.assertEqual((roku["plays"], roku["transcodes"], roku["transcode_share"]), (5, 3, 60))
        self.assertEqual((roku["direct_play"], roku["direct_stream"], roku["remote_transcodes"]), (1, 1, 1))
        self.assertEqual(roku["reasons"], {"subtitles": 1, "video": 1, "audio": 2, "unknown": 0, "not_checked": 0})
        alex = next(p for p in h["people"] if p["person"] == "Alex")
        self.assertEqual(alex["transcodes"], 3)
        self.assertEqual([d["device"] for d in h["devices"]], ["Living Room", "Pixel"])

    def test_window_and_live_plays(self):
        h = self.history()
        # Row 7 is 120 days old and row 8 is live TV: neither counts.
        self.assertEqual(h["plays"], 8)
        self.assertEqual(h["transcodes"], 4)
        self.assertEqual(h["devices_total"], 2)

    def test_copy_is_direct_stream(self):
        h = self.history()
        self.assertEqual(h["direct_stream"], 1)
        self.assertEqual(h["direct_play"], 3)

    def test_play_without_stream_data_is_unknown(self):
        pixel = next(d for d in self.history()["devices"] if d["device"] == "Pixel")
        self.assertEqual(pixel["reasons"]["unknown"], 1)

    def test_only_titles_transcoded_more_than_once(self):
        titles = self.history()["titles"]
        self.assertEqual([(t["title"], t["transcodes"]) for t in titles], [("Image Only", 2)])

    def test_titles_transcoded_once_are_left_out(self):
        data = fixture("playback-check", "tautulli.json")
        data["get_history:movie"] = [r for r in data["get_history:movie"] if r["row_id"] != 2]
        self.assertEqual(self.history(tautulli_data=data)["titles"], [])

    def test_only_200_plays_get_stream_data(self):
        data = fixture("playback-check", "tautulli.json")
        base = data["get_history:movie"][0]
        data["get_history:movie"] = [dict(base, row_id=n, daysAgo=1) for n in range(260)]
        data["get_history:episode"] = []
        net = self.network(tautulli_data=data)
        h = self.report()["playback_history"]
        asked = [s for s in net.requests if s.query.get("cmd") == "get_stream_data"]
        self.assertEqual(len(asked), 200)
        self.assertEqual(h["reasons"]["not_checked"], 60)

    def test_private_fields_are_dropped(self):
        self.network()
        text = json.dumps(self.report())
        for value in ("198.51.100.77", "machine-id-secret", "987654", "secret-thumb"):
            self.assertNotIn(value, text)

    def test_tautulli_down(self):
        self.network(tautulli=lambda seen: Unreachable("connection refused"))
        report = self.report()
        self.assertIsNone(report["playback_history"])
        self.assertIn("connection refused", report["playback_history_error"])
        self.assertTrue(report["libraries"])

    def test_days_zero_skips_tautulli(self):
        net = self.network()
        report = self.report(days=0)
        self.assertIsNone(report["playback_history"])
        self.assertFalse(any(seen.path == "/api/v2" for seen in net.requests))


# ---------------------------------------------------------------- options

class Options(OfflineTestCase):
    def run_main(self, *argv):
        captured = {}

        def fake_build(cfg, a):
            captured["args"] = a
            return {}
        with mock.patch("sys.argv", ["playback_check.py", *argv]), \
             mock.patch.object(pc, "load_config", lambda: config()), \
             mock.patch.object(pc, "build_report", fake_build), \
             mock.patch("sys.stdout"):
            self.assertEqual(pc.main(), 0)
        return captured["args"]

    def test_out_of_range_values(self):
        a = self.run_main("--limit", "9999", "--days", "99999", "--max-bitrate", "5")
        self.assertEqual((a.limit, a.days, a.max_bitrate), (500, 3650, 100))

    def test_check_tests_both_connections(self):
        server = Network(self, {"/": fixture("playback-check", "plex.json")["/"],
                                "/api/v2": tautulli_route(time.time())})
        result = pc.check(config())
        self.assertTrue(result["ok"])
        self.assertEqual(result["plex"]["server"], "Test Server")
        self.assertEqual(result["tautulli"]["version"], "v2.0.0")
        self.assertEqual(len(server.requests), 2)
