"""subtitles-and-languages (openspec/specs/subtitles-and-languages/spec.md)."""

import argparse
import collections
import copy
import json
import urllib.parse
from unittest import mock

from helpers import (FAKE_API_KEY, FAKE_TOKEN, FakeServer, OfflineTestCase, check_media_deletion, fixture,
                     load_script)

sl = load_script("subtitles-and-languages")
pc = load_script("playback-check")

PLEX = ("http://192.0.2.10:32400", FAKE_TOKEN, True)
TAUTULLI = ("http://192.0.2.10:8181", FAKE_API_KEY, True)


def args(**overrides):
    values = {"language": None, "library": None, "limit": 25}
    values.update(overrides)
    return argparse.Namespace(**values)


def config(tautulli=None):
    return {"plex": PLEX, "tautulli": tautulli, "tautulli_problem": None}


# ---------------------------------------------------------------- fake server

def paged(items):
    def page(seen):
        start = int(seen.headers.get("x-plex-container-start", 0))
        size = int(seen.headers.get("x-plex-container-size", len(items)))
        return {"MediaContainer": {"Metadata": items[start:start + size], "totalSize": len(items)}}
    return page


def listing(data, seen):
    section, kind = seen.path.split("/")[3], seen.query.get("type")
    items = {("1", "1"): data["movies"], ("2", "4"): data["episodes"], ("2", "2"): data["shows"]}
    return paged(items.get((section, kind), []))(seen)


def details(data):
    def answer(seen):
        keys = seen.path.rsplit("/", 1)[-1].split(",")
        return {"MediaContainer": {"Metadata": [data["details"][k] for k in keys if k in data["details"]]}}
    return answer


class Network(FakeServer):
    """Answers every client the script builds. Any path under /library/metadata/ goes to `metadata`."""

    def __init__(self, test, routes, metadata):
        super().__init__(routes)
        self.metadata = metadata
        real = sl.build_opener
        patcher = mock.patch.object(sl, "build_opener", lambda url, verify: self.attach(real(url, verify)))
        patcher.start()
        test.addCleanup(patcher.stop)

    def default_open(self, request):
        path = urllib.parse.urlsplit(request.full_url).path
        if path.startswith("/library/metadata/"):
            self.routes[path] = self.metadata
        return super().default_open(request)


class Base(OfflineTestCase):
    def network(self, data=None, prefs=None):
        data = data or fixture("subtitles-and-languages", "plex.json")
        routes = {
            "/": data["/"],
            "/library/sections": data["/library/sections"],
            "/library/sections/1/all": lambda seen: listing(data, seen),
            "/library/sections/2/all": lambda seen: listing(data, seen),
            "/:/prefs": prefs or {"MediaContainer": {"Setting": []}},
        }
        self.server = Network(self, routes, details(data))
        return self.server

    def report(self, cfg=None, **kw):
        return sl.build_report(cfg or config(), args(**kw))

    @staticmethod
    def library(report, name):
        return next(lib for lib in report["libraries"] if lib["name"] == name)

    def listed(self, report, finding, name="Movies"):
        return {e["title"]: e for e in self.library(report, name)["listed"][finding]}


def with_sections(data, **languages):
    """The fixture with the named libraries' languages changed (None removes it)."""
    data = copy.deepcopy(data)
    for section in data["/library/sections"]["MediaContainer"]["Directory"]:
        if section["title"] in languages:
            if languages[section["title"]] is None:
                section.pop("language", None)
            else:
                section["language"] = languages[section["title"]]
    return data


# ---------------------------------------------------------------- sources

class Sources(Base):
    def test_only_allowed_paths_with_get_and_no_tautulli(self):
        net = self.network()
        self.report(config(tautulli=TAUTULLI))
        self.assertTrue(net.requests)
        for seen in net.requests:
            self.assertEqual(seen.method, "GET")
            self.assertNotEqual(seen.path, "/api/v2")
            self.assertTrue(any(rule.match(seen.path) for rule in sl.ALLOWED_PATHS), seen.path)
        self.assertFalse(hasattr(sl, "TautulliClient"))

    def test_more_than_100_titles_in_one_request_is_blocked(self):
        net = self.network()
        client = sl.PlexClient(*PLEX)
        with self.assertRaises(sl.ReportError) as caught:
            client.get("/library/metadata/" + ",".join(str(n) for n in range(1, 102)))
        self.assertIn("allowlist", str(caught.exception))
        self.assertEqual(net.requests, [])

    def test_details_are_read_100_at_a_time(self):
        data = fixture("subtitles-and-languages", "plex.json")
        template = data["details"]["5002"]
        data["episodes"] = [dict(template, ratingKey=str(9000 + n)) for n in range(250)]
        data["details"].update({e["ratingKey"]: e for e in data["episodes"]})
        net = self.network(data=data)
        self.report(library=["TV Shows"])
        batches = [s for s in net.requests if s.path.startswith("/library/metadata/")]
        self.assertEqual([len(s.path.rsplit("/", 1)[-1].split(",")) for s in batches], [100, 100, 50])

    def test_media_deletion_setting(self):
        self.network()

        def build(answer):
            self.server.routes["/:/prefs"] = answer
            self.server.requests.clear()
            return self.report(), self.server.requests
        check_media_deletion(self, build)

    def test_connection_check_skips_settings(self):
        net = self.network()
        result = sl.check(config())
        self.assertEqual(result["plex"]["server"], "Test Server")
        self.assertEqual([s.path for s in net.requests], ["/"])


# ---------------------------------------------------------------- libraries

class Libraries(Base):
    def test_music_library_is_skipped(self):
        self.network()
        report = self.report()
        self.assertEqual(report["skipped_libraries"], [{"name": "Music", "type": "artist"}])
        self.assertEqual([lib["name"] for lib in report["libraries"]], ["Movies", "TV Shows"])

    def test_asking_for_a_music_library(self):
        self.network()
        with self.assertRaises(sl.ReportError) as caught:
            self.report(library=["music"])
        self.assertIn("movie and TV", str(caught.exception))

    def test_no_library_matches(self):
        self.network()
        with self.assertRaises(sl.ReportError):
            self.report(library=["Nope"])

    def test_title_missing_from_details_is_not_checked(self):
        self.network()
        report = self.report()
        movies = self.library(report, "Movies")
        self.assertEqual(movies["details_missing"], 1)
        for finding in sl.FINDINGS:
            self.assertNotIn("No Details", self.listed(report, finding))

    def test_unavailable_file_is_counted_not_checked(self):
        self.network()
        report = self.report()
        self.assertEqual(self.library(report, "Movies")["unavailable"], 1)
        # Gone File's only copy has Japanese audio and no subtitles, so it would be flagged if checked.
        self.assertNotIn("Gone File", self.listed(report, "foreign_no_subtitles"))

    def test_two_versions_are_checked_separately(self):
        self.network()
        movie = self.listed(self.report(), "no_subtitles")["Two Versions"]
        self.assertEqual([f["resolution"] for f in movie["files"]], ["720"])


# ---------------------------------------------------------------- reading languages

class Languages(OfflineTestCase):
    def test_track_language(self):
        cases = [
            ({"languageTag": "en-US", "languageCode": "eng"}, "en"),
            ({"languageTag": "en"}, "en"),
            ({"languageTag": "zh-Hans", "languageCode": "zho"}, "zh"),
            ({"languageCode": "eng"}, "eng"),
            ({"languageTag": "unk", "languageCode": ""}, None),
            ({"languageCode": "und"}, None),
            ({"languageTag": "zxx"}, None),
            ({}, None),
            ({"languageTag": "<b>"}, None),
        ]
        for stream, expected in cases:
            with self.subTest(stream=stream):
                self.assertEqual(sl.track_language(stream), expected)

    def test_matching_by_tag_or_three_letter_code(self):
        stream = {"languageTag": "en", "languageCode": "eng"}
        self.assertTrue(sl.matches(stream, {"en"}))
        self.assertTrue(sl.matches(stream, {"eng"}))
        self.assertFalse(sl.matches(stream, {"es"}))
        self.assertFalse(sl.matches({"languageCode": "und"}, {"und"}))

    def test_parse_languages(self):
        self.assertEqual(sl.parse_languages(["en", "ENG", "es-MX", "fre", "en"]), ["en", "eng", "es", "fra"])
        self.assertEqual(sl.parse_languages(["pt_BR"]), ["pt"])
        self.assertEqual(sl.parse_languages([]), [])

    def test_bad_language_values(self):
        for value in ("english", "e", "en1", ""):
            with self.subTest(value=value):
                with self.assertRaises(sl.ReportError) as caught:
                    sl.parse_languages([value])
                self.assertIn("2 or 3 letter", str(caught.exception))

    def test_too_many_languages(self):
        with self.assertRaises(sl.ReportError) as caught:
            sl.parse_languages(["en", "es", "fr", "de", "it", "ja"])
        self.assertIn("At most 5", str(caught.exception))

    def test_library_language(self):
        for value, expected in (("en-US", "en"), ("fr", "fr"), ("xn", None), (None, None), ("", None),
                                ("haw", "haw"), ("abcd", None)):
            with self.subTest(value=value):
                self.assertEqual(sl.library_language({"language": value}), expected)

    def test_main_track_is_the_same_as_playback_check(self):
        # Make one audio track TrueHD at a time: playback-check flags TrueHD only when that track is
        # its main track, so the two scripts must pick the same one.
        layouts = [
            [{}, {}],
            [{}, {"selected": True}],
            [{"default": True}, {}],
            [{"default": True}, {"selected": True}],
            [{}, {"default": "1"}, {}],
            [{"selected": "0"}, {"default": True}],
        ]
        files = [m for item in fixture("playback-check", "plex.json")["details"].values()
                 for m in item.get("Media", []) or []]
        layouts += [[{k: s[k] for k in ("selected", "default") if k in s} for s in tracks]
                    for tracks in ([s for p in m["Part"] for s in p.get("Stream", []) if s.get("streamType") == 2]
                                   for m in files) if tracks]
        for layout in layouts:
            tracks = [dict(flags, streamType=2, codec="aac") for flags in layout]
            chosen = sl.main_audio(tracks)
            for i in range(len(tracks)):
                trial = [dict(t, codec="truehd" if n == i else "aac") for n, t in enumerate(tracks)]
                media = {"Part": [{"Stream": trial}]}
                with self.subTest(layout=layout, track=i):
                    self.assertEqual("truehd_audio" in pc.check_file(media, 0, True)["causes"], chosen is tracks[i])


# ---------------------------------------------------------------- the user's language

class UsersLanguage(Base):
    def test_library_language_is_used_without_the_option(self):
        self.network()
        report = self.report()
        self.assertEqual(self.library(report, "Movies")["language"], {"codes": ["en"], "source": "library"})
        self.assertEqual(self.library(report, "TV Shows")["language"], {"codes": ["en"], "source": "library"})

    def test_option_wins(self):
        self.network()
        report = self.report(language=["en", "es"])
        for lib in report["libraries"]:
            self.assertEqual(lib["language"], {"codes": ["en", "es"], "source": "option"})
        # Spanish audio is understood now; only the German episode is left.
        show = self.listed(report, "foreign_no_subtitles", "TV Shows")["Harbor Tales"]
        self.assertEqual(show["episodes_flagged"], 1)
        self.assertEqual(show["audio_languages"], {"de": 1})

    def test_checking_another_language(self):
        self.network()
        report = self.report(language=["fr"])
        titles = self.listed(report, "no_subtitles")
        self.assertIn("Japanese With English", titles)
        self.assertNotIn("Japanese With French", titles)
        # French audio counts as understood.
        self.assertNotIn("SDH Only", self.listed(report, "foreign_no_subtitles"))

    def test_bad_option_stops_before_contacting_the_server(self):
        net = self.network()
        with self.assertRaises(sl.ReportError):
            self.report(language=["english"])
        self.assertEqual(net.requests, [])

    def test_library_with_no_language(self):
        for value in (None, "xn"):
            with self.subTest(language=value):
                data = with_sections(fixture("subtitles-and-languages", "plex.json"), Movies=value)
                self.network(data=data)
                report = self.report()
                movies = self.library(report, "Movies")
                self.assertIsNone(movies["language"])
                self.assertIn("--language", movies["language_problem"])
                for finding in ("foreign_no_subtitles", "no_subtitles", "forced_only"):
                    self.assertIsNone(movies[finding])
                for finding in ("foreign_no_subtitles", "no_subtitles"):
                    self.assertIsNone(movies["listed"][finding])
                    self.assertIsNone(movies["more"][finding])
                self.assertEqual(movies["unknown_language"], 2)
                self.assertTrue(movies["audio_languages"])
                # Totals count it as 0; TV Shows still has its findings.
                self.assertEqual(report["totals"]["foreign_no_subtitles"], 3)
                self.assertEqual(report["totals"]["forced_only"], 0)

    def test_library_with_no_language_and_the_option(self):
        data = with_sections(fixture("subtitles-and-languages", "plex.json"), Movies=None)
        self.network(data=data)
        movies = self.library(self.report(language=["en"]), "Movies")
        self.assertEqual(movies["language"], {"codes": ["en"], "source": "option"})
        self.assertNotIn("language_problem", movies)
        self.assertEqual(movies["foreign_no_subtitles"], 2)


# ---------------------------------------------------------------- findings

class Findings(Base):
    def setUp(self):
        super().setUp()
        self.network()
        self.out = self.report()

    def findings(self, title):
        return [f for f in sl.FINDINGS if title in self.listed(self.out, f)]

    def test_japanese_film_with_english_subtitles(self):
        self.assertEqual(self.findings("Japanese With English"), [])

    def test_japanese_film_with_only_french_subtitles(self):
        self.assertEqual(self.findings("Japanese With French"), ["foreign_no_subtitles", "no_subtitles"])
        f = self.listed(self.out, "foreign_no_subtitles")["Japanese With French"]["files"][0]
        self.assertEqual(f["main_audio_language"], "ja")
        self.assertEqual(f["subtitle_languages"], ["fr"])

    def test_english_dub(self):
        self.assertEqual(self.findings("English Dub"), ["no_subtitles"])
        f = self.listed(self.out, "no_subtitles")["English Dub"]["files"][0]
        self.assertEqual((f["main_audio_language"], f["audio_languages"]), ("ja", ["ja", "en"]))

    def test_only_forced_subtitles(self):
        self.assertEqual(self.findings("Forced Only"), ["foreign_no_subtitles", "no_subtitles"])
        f = self.listed(self.out, "foreign_no_subtitles")["Forced Only"]["files"][0]
        self.assertEqual((f["subtitle_languages"], f["forced_subtitle_languages"]), ([], ["en"]))
        self.assertEqual(self.library(self.out, "Movies")["forced_only"], 1)

    def test_audio_with_no_language(self):
        self.assertEqual(self.findings("Unlabelled Audio"), ["no_subtitles", "unknown_language"])
        f = self.listed(self.out, "unknown_language")["Unlabelled Audio"]["files"][0]
        self.assertEqual((f["main_audio_language"], f["unknown_audio_tracks"]), ("unknown", 1))

    def test_labelled_unknown(self):
        self.assertEqual(self.findings("Unknown Tag"), ["unknown_language"])

    def test_english_film_without_subtitles(self):
        self.assertEqual(self.findings("English No Subs"), ["no_subtitles"])

    def test_separate_subtitle_file_counts(self):
        self.assertEqual(self.findings("Sidecar Subs"), [])

    def test_region_tags(self):
        self.assertEqual(self.findings("Region Tags"), [])

    def test_hearing_impaired_subtitles_count(self):
        self.assertEqual(self.findings("SDH Only"), [])

    def test_no_audio_tracks(self):
        self.assertEqual(self.findings("No Audio"), ["no_subtitles"])
        f = self.listed(self.out, "no_subtitles")["No Audio"]["files"][0]
        self.assertIsNone(f["main_audio_language"])

    def test_forced_track_never_counts_as_subtitles(self):
        # A forced English track must not clear a Japanese-only film, wherever it sits.
        data = fixture("subtitles-and-languages", "plex.json")
        streams = data["details"]["1004"]["Media"][0]["Part"][0]["Stream"]
        streams.append(dict(streams[-1], default=True))
        self.network(data=data)
        self.assertIn("Forced Only", self.listed(self.report(), "foreign_no_subtitles"))


# ---------------------------------------------------------------- summary

class Summary(Base):
    def test_audio_and_subtitle_languages(self):
        self.network()
        movies = self.library(self.report(), "Movies")
        self.assertEqual(movies["audio_languages"], {"en": 4, "ja": 4, "unknown": 2, "fr": 1, "ko": 1})
        self.assertEqual(list(movies["audio_languages"]), ["en", "ja", "unknown", "fr", "ko"])
        self.assertEqual(movies["subtitle_languages"], {"en": 6, "fr": 1})

    def test_at_most_15_languages(self):
        counter = collections.Counter({f"l{n:02d}"[:3]: 100 - n for n in range(20)})
        result = sl.summary(counter)
        self.assertEqual(len(result), 16)
        self.assertEqual(result["other"], sum(100 - n for n in range(15, 20)))
        self.assertEqual(sl.summary(collections.Counter({"en": 3})), {"en": 3})

    def test_language_names(self):
        self.network()
        names = self.report()["language_names"]
        self.assertEqual(names["en"], "English")
        self.assertEqual(names["ja"], "Japanese")
        self.assertEqual(names["es"], "Spanish")
        self.assertNotIn("unknown", names)
        self.assertNotIn("other", names)

    def test_codes_without_a_name(self):
        data = fixture("subtitles-and-languages", "plex.json")
        stream = data["details"]["1006"]["Media"][0]["Part"][0]["Stream"][1]
        stream.update(languageTag="haw", languageCode="haw")
        stream.pop("language")
        self.network(data=data)
        self.assertIsNone(self.report()["language_names"]["haw"])


# ---------------------------------------------------------------- report

class Report(Base):
    def test_shows_are_grouped(self):
        self.network()
        report = self.report()
        show = self.listed(report, "foreign_no_subtitles", "TV Shows")["Harbor Tales"]
        self.assertEqual(show, {"title": "Harbor Tales", "year": 2010, "episodes": 4, "episodes_flagged": 3,
                                "audio_languages": {"es": 2, "de": 1},
                                "seasons": [{"season": 1, "episodes": [[2, 4]], "some_versions": []}],
                                "ranges_more": 0, "unnumbered": [], "unnumbered_more": 0})
        quiet = self.listed(report, "unknown_language", "TV Shows")["Quiet Show"]
        self.assertEqual((quiet["episodes"], quiet["episodes_flagged"]), (2, 1))

    def test_sorting(self):
        self.network()
        report = self.report()
        titles = [m["title"] for m in self.library(report, "Movies")["listed"]["no_subtitles"]]
        self.assertEqual(titles, sorted(titles, key=str.lower))
        shows = [s["title"] for s in self.library(report, "TV Shows")["listed"]["no_subtitles"]]
        self.assertEqual(shows, ["Harbor Tales", "Quiet Show"])  # 3 episodes, then 2

    def test_counts_and_totals(self):
        self.network()
        report = self.report()
        movies = self.library(report, "Movies")
        self.assertEqual((movies["titles"], movies["files"]), (14, 13))
        self.assertEqual((movies["foreign_no_subtitles"], movies["no_subtitles"], movies["unknown_language"]),
                         (2, 7, 2))
        tv = self.library(report, "TV Shows")
        self.assertEqual((tv["titles"], tv["files"]), (6, 6))
        self.assertEqual((tv["foreign_no_subtitles"], tv["no_subtitles"], tv["unknown_language"]), (3, 5, 1))
        self.assertEqual(report["totals"], {
            "titles": 20, "files": 19, "unavailable": 1, "details_missing": 1,
            "foreign_no_subtitles": 5, "no_subtitles": 12, "unknown_language": 3, "forced_only": 1,
        })
        self.assertIn("labels", report["limits"])

    def test_clean_library(self):
        data = fixture("subtitles-and-languages", "plex.json")
        data["movies"] = [m for m in data["movies"] if m["title"] == "Japanese With English"]
        self.network(data=data)
        movies = self.library(self.report(), "Movies")
        self.assertEqual(movies["listed"], {f: [] for f in sl.FINDINGS})
        self.assertEqual(movies["more"], {f: 0 for f in sl.FINDINGS})

    def test_limit_and_more(self):
        self.network()
        movies = self.library(self.report(limit=2), "Movies")
        self.assertEqual(len(movies["listed"]["no_subtitles"]), 2)
        self.assertEqual(movies["more"]["no_subtitles"], 5)
        self.assertEqual(movies["more"]["foreign_no_subtitles"], 0)

    def test_counts_only(self):
        self.network()
        movies = self.library(self.report(limit=0), "Movies")
        self.assertEqual(movies["listed"], {f: [] for f in sl.FINDINGS})
        self.assertEqual(movies["no_subtitles"], 7)
        self.assertTrue(movies["audio_languages"])

    def test_no_file_paths_in_the_output(self):
        self.network()
        self.assertNotIn("secret-path", json.dumps(self.report()))

    def test_server_text_is_cleaned(self):
        data = fixture("subtitles-and-languages", "plex.json")
        data["details"]["1002"]["title"] = "Bad\x1b[31mTitle"
        data["movies"][1]["title"] = "Bad\x1b[31mTitle"
        self.network(data=data)
        self.assertIn("Bad [31mTitle", self.listed(self.report(), "foreign_no_subtitles"))


# ---------------------------------------------------------------- episode numbers

SPANISH_NO_SUBTITLES = {"streamType": 2, "languageTag": "es", "languageCode": "spa", "language": "Spanish"}
ENGLISH = [{"streamType": 2, "languageTag": "en", "languageCode": "eng", "language": "English"},
           {"streamType": 3, "languageTag": "en", "languageCode": "eng", "language": "English"}]


def one_show(episodes):
    """The fixture with Harbor Tales as the only show. Each episode is (season, number, files), where
    files is a string with one letter per version: "f" for Spanish audio and no subtitles (flagged
    under foreign_no_subtitles and no_subtitles), "e" for English audio and subtitles (no finding).
    season or number can be None, and a fourth value gives extra listing fields."""
    data = fixture("subtitles-and-languages", "plex.json")
    data["episodes"], data["details"] = [], {k: v for k, v in data["details"].items()
                                             if "grandparentTitle" not in v}
    data["shows"] = [show for show in data["shows"] if show["title"] == "Harbor Tales"]
    for i, (season, number, files, *extra) in enumerate(episodes):
        key = str(90000 + i)
        item = {"ratingKey": key, "title": f"Episode {i}", "grandparentRatingKey": "500",
                "grandparentTitle": "Harbor Tales"}
        if season is not None:
            item["parentIndex"] = season
        if number is not None:
            item["index"] = number
        item.update(extra[0] if extra else {})
        data["episodes"].append(item)
        media = [{"id": int(key) * 10 + n, "videoResolution": "1080", "Part": [{
            "id": int(key) * 10 + n, "file": "/media/secret-path/x.mkv",
            "Stream": [{"streamType": 1}] + ([SPANISH_NO_SUBTITLES] if kind == "f" else ENGLISH)}]}
            for n, kind in enumerate(files)]
        data["details"][key] = dict(item, Media=media)
    return data


class EpisodeNumbers(Base):
    def show(self, episodes, finding="foreign_no_subtitles"):
        self.network(data=one_show(episodes))
        entries = self.listed(self.report(library=["TV Shows"]), finding, "TV Shows")
        return entries.get("Harbor Tales")

    def test_ranges_in_two_seasons(self):
        show = self.show([(1, n, "f") for n in (1, 2, 3, 4, 6)] + [(1, 5, "e"), (3, 2, "f"), (3, 1, "e")])
        self.assertEqual(show["seasons"], [{"season": 1, "episodes": [[1, 4], [6, 6]], "some_versions": []},
                                           {"season": 3, "episodes": [[2, 2]], "some_versions": []}])
        self.assertEqual((show["ranges_more"], show["unnumbered"], show["unnumbered_more"]), (0, [], 0))

    def test_one_version_of_an_episode_is_fine(self):
        show = self.show([(2, 5, "ef"), (2, 6, "ff")], finding="no_subtitles")
        self.assertEqual(show["seasons"], [{"season": 2, "episodes": [[5, 6]], "some_versions": [5]}])

    def test_episode_with_no_number(self):
        show = self.show([(1, None, "f", {"title": "Live Special", "originallyAvailableAt": "2021-12-31"}),
                          (None, None, "f", {"title": "Odd\x1bDate", "originallyAvailableAt": "31/12/2021"})])
        self.assertEqual(show["seasons"], [])
        self.assertEqual(show["unnumbered"], [
            {"title": "Live Special", "aired": "2021-12-31", "some_versions": False},
            {"title": "Odd Date", "aired": None, "some_versions": False}])

    def test_at_most_10_unnumbered_episodes(self):
        show = self.show([(1, None, "f")] * 13)
        self.assertEqual((len(show["unnumbered"]), show["unnumbered_more"]), (10, 3))

    def test_at_most_30_ranges(self):
        show = self.show([(1, n, "ef") for n in range(1, 100, 2)], finding="no_subtitles")
        [season] = show["seasons"]
        self.assertEqual(season["episodes"], [[n, n] for n in range(1, 60, 2)])
        self.assertEqual(season["some_versions"], list(range(1, 60, 2)))
        self.assertEqual(show["ranges_more"], 20)

    def test_cap_carries_across_seasons(self):
        show = self.show([(1, n, "f") for n in range(1, 50, 2)] + [(2, n, "f") for n in range(1, 20, 2)])
        self.assertEqual([len(s["episodes"]) for s in show["seasons"]], [25, 5])
        self.assertEqual(show["ranges_more"], 5)

    def test_every_episode_flagged(self):
        show = self.show([(s, n, "f") for s in range(1, 11) for n in range(1, 31)])
        self.assertEqual(show["seasons"], [{"season": s, "episodes": [[1, 30]], "some_versions": []}
                                           for s in range(1, 11)])
        self.assertEqual(show["ranges_more"], 0)

    def test_specials_come_first(self):
        show = self.show([(1, 1, "f"), (0, 3, "f")])
        self.assertEqual([s["season"] for s in show["seasons"]], [0, 1])

    def test_repeated_episode_appears_once(self):
        show = self.show([(1, 2, "f"), (1, 2, "f")])
        self.assertEqual(show["episodes_flagged"], 2)
        self.assertEqual(show["seasons"], [{"season": 1, "episodes": [[2, 2]], "some_versions": []}])

    def test_numbers_given_as_text(self):
        show = self.show([("1", "4", "f"), ("x", "5", "f")])
        self.assertEqual(show["seasons"], [{"season": 1, "episodes": [[4, 4]], "some_versions": []}])
        self.assertEqual(len(show["unnumbered"]), 1)

    def test_unavailable_version_is_not_counted_as_fine(self):
        data = one_show([(1, 1, "fe")])
        data["details"]["90000"]["Media"][1]["deletedAt"] = 1700000000
        self.network(data=data)
        show = self.listed(self.report(library=["TV Shows"]), "foreign_no_subtitles", "TV Shows")["Harbor Tales"]
        self.assertEqual(show["seasons"][0]["some_versions"], [])

    def test_no_file_paths(self):
        self.network(data=one_show([(1, 1, "f"), (None, None, "f")]))
        self.assertNotIn("secret-path", json.dumps(self.report()))

