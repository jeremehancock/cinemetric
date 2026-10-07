"""episode-gaps (openspec/specs/episode-gaps/spec.md)."""

import argparse
import contextlib
import io
import json
import sys
from unittest import mock

from helpers import (FAKE_API_KEY, FAKE_TOKEN, FakeServer, OfflineTestCase, fixture, load_script,
                     check_media_deletion)

gaps = load_script("episode-gaps")

PLEX = ("http://192.0.2.10:32400", FAKE_TOKEN, True)
TAUTULLI = ("http://192.0.2.10:8181", FAKE_API_KEY, True)
ALLOWED = {"/", "/library/sections", "/library/sections/1/all", "/:/prefs"}


def args(**overrides):
    values = {"library": None, "show": None, "limit": 25}
    values.update(overrides)
    return argparse.Namespace(**values)


def config(plex=PLEX, tautulli=TAUTULLI):
    return {"plex": plex, "tautulli": tautulli, "tautulli_problem": None}


def listing(data, section):
    """A section's listing for the requested type, paged the way Plex pages it."""
    def page(seen):
        items = data["listings"][section].get(seen.query.get("type"), [])
        start = int(seen.headers.get("x-plex-container-start", 0))
        size = int(seen.headers.get("x-plex-container-size", len(items)))
        return {"MediaContainer": {"Metadata": items[start:start + size], "totalSize": len(items)}}
    return page


def routes(data=None):
    data = data or fixture("episode-gaps", "plex.json")
    result = {"/": data["/"], "/library/sections": data["/library/sections"]}
    for section in data["listings"]:
        result[f"/library/sections/{section}/all"] = listing(data, section)
    return result


def episode(season, number, show="900", deleted=False, file=None):
    media = {"Part": [{"file": file or f"/tv/X/X - S{season:02d}E{number:02d}.mkv"}]}
    if deleted:
        media["deletedAt"] = 1700000000
    return {"grandparentRatingKey": show, "grandparentTitle": "X", "parentIndex": season,
            "index": number, "Media": [media]}


class Base(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.use(routes())

    def use(self, server_routes):
        self.server = FakeServer(server_routes)
        real = gaps.build_opener
        patcher = mock.patch.object(gaps, "build_opener",
                                    lambda url, verify: self.server.attach(real(url, verify)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def report(self, cfg=None, **kw):
        return gaps.build_report(cfg or config(), args(**kw))

    def library(self, **kw):
        [library] = self.report(**kw)["libraries"]
        return library

    def show(self, title, year=None, **kw):
        """The listed entry for a show, or None when it isn't listed."""
        for entry in self.library(limit=500, **kw)["listed"]:
            if entry["title"] == title and (year is None or entry["year"] == year):
                return entry
        return None

    def check(self, *episodes):
        """Gaps for one made-up show."""
        return gaps.check_show("X", None, list(episodes))


class SourcesUsed(Base):
    def test_only_allowed_paths_with_get(self):
        self.report()
        self.assertTrue(self.server.requests)
        for seen in self.server.requests:
            self.assertEqual(seen.method, "GET")
            self.assertIn(seen.path, ALLOWED)

    def test_tautulli_is_never_contacted(self):
        self.report(cfg=config())
        self.assertTrue(all(s.url.startswith(PLEX[0]) for s in self.server.requests))
        self.assertFalse(hasattr(gaps, "TautulliClient"))

    def test_reads_shows_and_episodes_in_pages_of_500(self):
        self.report()
        listings = [s for s in self.server.requests if s.path.endswith("/all")]
        self.assertEqual({s.query["type"] for s in listings}, {"2", "4"})
        self.assertTrue(all(s.headers["x-plex-container-size"] == "500" for s in listings))

    def test_no_plex_configured(self):
        with self.assertRaises(gaps.ReportError) as caught:
            self.report(cfg=config(plex=None))
        self.assertIn("NOT_CONFIGURED", str(caught.exception))


class LibrariesChecked(Base):
    def test_other_libraries_are_skipped(self):
        report = self.report()
        self.assertEqual([lib["name"] for lib in report["libraries"]], ["TV Shows"])
        self.assertEqual(report["skipped_libraries"],
                         [{"name": "Movies", "type": "movie"}, {"name": "Music", "type": "artist"}])

    def test_asking_for_a_movie_library(self):
        with self.assertRaises(gaps.ReportError) as caught:
            self.report(library=["movies"])
        self.assertIn("Only TV libraries", str(caught.exception))

    def test_asking_for_a_library_that_doesnt_exist(self):
        with self.assertRaises(gaps.ReportError):
            self.report(library=["Nope"])

    def test_library_names_ignore_case(self):
        self.assertEqual(self.library(library=["tv shows"])["name"], "TV Shows")

    def test_two_shows_with_the_same_title(self):
        old, new = self.show("Doctor Who", 1963), self.show("Doctor Who", 2005)
        self.assertEqual(old["seasons"][0]["missing"], [[2, 2]])
        self.assertIsNone(new)

    def test_show_filter(self):
        library = self.library(show="doctor")
        self.assertEqual(library["shows"], 2)
        self.assertEqual(self.report(show="doctor")["show_filter"], "doctor")

    def test_no_show_matches(self):
        library = self.library(show="zzz")
        self.assertEqual((library["shows"], library["shows_with_gaps"], library["listed"]), (0, 0, []))


class WhichEpisodesAreThere(Base):
    def test_a_file_that_holds_two_episodes(self):
        self.assertIsNone(self.show("Double Episode"))

    def test_multi_episode_forms(self):
        for name in ("X - S01E01-E03.mkv", "X - S01E01-03.mkv", "X - s01e01e02e03.mkv",
                     "X - S01E01-E02-E03.mkv"):
            with self.subTest(name=name):
                result = self.check(episode(1, 1, file="/tv/X/" + name), episode(1, 4))
                self.assertEqual(result["missing_episodes"], 0)

    def test_a_resolution_after_the_episode_number(self):
        self.assertEqual(self.show("Resolution Name")["seasons"][0]["missing"], [[2, 2]])

    def test_a_range_that_doesnt_start_at_the_episode(self):
        result = self.check(episode(1, 1, file="/tv/X/X - S01E05-E06.mkv"), episode(1, 3))
        self.assertEqual(result["seasons"][0]["missing"], [[2, 2]])

    def test_a_range_for_another_season(self):
        result = self.check(episode(1, 1, file="/tv/X/X - S02E01-E02.mkv"), episode(1, 3))
        self.assertEqual(result["seasons"][0]["missing"], [[2, 2]])

    def test_two_copies_of_an_episode(self):
        self.assertIsNone(self.show("Two Copies"))

    def test_plex_cant_find_the_file(self):
        entry = self.show("Unavailable Episode")
        self.assertEqual(entry["seasons"][0]["unavailable"], [5])
        self.assertEqual(entry["seasons"][0]["missing"], [])
        self.assertEqual((entry["missing_episodes"], entry["unavailable_episodes"]), (0, 1))

    def test_one_copy_missing_and_one_there(self):
        both = episode(1, 2)
        both["Media"].append({"deletedAt": 1700000000, "Part": [{"file": "/tv/X/old.mkv"}]})
        result = self.check(episode(1, 1), both, episode(1, 3))
        self.assertFalse(result["has_gaps"])

    def test_unnumbered_episodes_are_counted(self):
        self.assertEqual(self.library()["unnumbered"], 1)
        self.assertIsNone(self.show("Unnumbered Episode"))

    def test_specials(self):
        self.assertIsNone(self.show("Specials Show"))


class FindingGaps(Base):
    def test_a_gap_in_the_middle(self):
        entry = self.show("Middle Gap")
        self.assertEqual(entry["seasons"], [{"season": 1, "episodes": 3, "highest": 4, "missing": [[3, 3]],
                                             "unavailable": [], "continues_numbering": False}])

    def test_a_season_that_starts_late(self):
        self.assertEqual(self.show("Late Start")["seasons"][0]["missing"], [[1, 4]])

    def test_numbering_carries_on_across_seasons(self):
        entry = self.show("Carry On")
        self.assertIsNone(entry)
        result = self.check(*[episode(1, n) for n in range(1, 13)], *[episode(2, n) for n in range(13, 25)])
        self.assertEqual(result["missing_episodes"], 0)
        self.assertEqual([(s["season"], s["continues_numbering"]) for s in result["seasons"]], [(2, True)])

    def test_carry_on_needs_the_very_next_number(self):
        result = self.check(*[episode(1, n) for n in range(1, 4)], *[episode(2, n) for n in range(5, 7)])
        self.assertEqual(result["seasons"][0]["missing"], [[1, 4]])

    def test_a_missing_season(self):
        self.assertEqual(self.show("Missing Season")["missing_seasons"], [3])

    def test_only_the_later_seasons(self):
        self.assertIsNone(self.show("Later Seasons"))
        self.assertEqual(self.library()["shows_starting_later"], 1)  # Daily Show has no season 1 to 999
        result = self.check(episode(35, 1), episode(36, 1))
        self.assertEqual((result["first_season"], result["missing_seasons"]), (35, []))

    def test_missing_episodes_after_the_last_one(self):
        result = self.check(*[episode(1, n) for n in range(1, 9)])
        self.assertFalse(result["has_gaps"])

    def test_a_date_numbered_show(self):
        self.assertIsNone(self.show("Daily Show"))
        self.assertEqual(self.library()["seasons_not_checked"], 1)

    def test_big_episode_numbers_in_a_normal_season(self):
        result = self.check(episode(1, 1), episode(1, 20230105))
        self.assertFalse(result["has_gaps"])
        self.assertEqual(result["seasons_not_checked"], 1)


class ReportContents(Base):
    def test_several_gaps_in_one_season(self):
        entry = self.show("Several Gaps")
        self.assertEqual(entry["seasons"][0]["missing"], [[3, 3], [5, 7]])
        self.assertEqual(entry["missing_episodes"], 4)

    def test_report_fields(self):
        report = self.report()
        self.assertEqual(report["server"], {"name": "Test Server", "version": "1.41.0.0000"})
        self.assertIsNone(report["show_filter"])
        self.assertIn("can't be seen", report["limits"])
        entry = self.show("Middle Gap")
        self.assertEqual(set(entry), {"title", "year", "first_season", "missing_seasons", "missing_episodes",
                                      "unavailable_episodes", "unnumbered", "seasons"})

    def test_library_counts_and_totals(self):
        report = self.report()
        library = report["libraries"][0]
        expected = {"shows": 16, "episodes": 62, "shows_with_gaps": 7, "missing_episodes": 11,
                    "unavailable_episodes": 1, "missing_seasons": 1, "shows_starting_later": 1,
                    "seasons_not_checked": 1, "unnumbered": 1, "more_shows": 0}
        self.assertEqual({k: library[k] for k in expected}, expected)
        self.assertEqual(report["totals"], {k: expected[k] for k in gaps.TOTAL_FIELDS})

    def test_sorted_by_most_missing(self):
        titles = [(s["title"], s["year"]) for s in self.library()["listed"]]
        self.assertEqual(titles, [("Late Start", 2011), ("Several Gaps", 2022), ("Doctor Who", 1963),
                                  ("Middle Gap", 2010), ("Resolution Name", 2016),
                                  ("Unavailable Episode", 2018), ("Missing Season", 2013)])
        # Missing Season has no episodes missing, only a season, so it comes last.
        self.assertEqual(self.library()["shows_with_gaps"], 7)

    def test_more_shows_than_the_limit(self):
        library = self.library(limit=3)
        self.assertEqual(len(library["listed"]), 3)
        self.assertEqual((library["more_shows"], library["shows_with_gaps"]), (4, 7))

    def test_counts_only(self):
        library = self.library(limit=0)
        self.assertEqual(library["listed"], [])
        self.assertEqual(library["shows_with_gaps"], 7)

    def test_nothing_missing(self):
        data = fixture("episode-gaps", "plex.json")
        data["listings"]["1"]["4"] = [e for e in data["listings"]["1"]["4"]
                                      if e["grandparentRatingKey"] in ("113", "114")]
        self.use(routes(data))
        library = self.library()
        self.assertEqual((library["shows_with_gaps"], library["listed"]), (0, []))

    def test_no_file_paths_in_the_output(self):
        text = json.dumps(self.report(limit=500))
        self.assertNotIn("/tv/", text)
        self.assertNotIn(".mkv", text)


class Options(Base):
    def run_main(self, *argv):
        self.write_config({"plex_url": PLEX[0], "plex_token": FAKE_TOKEN})
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["episode_gaps.py", *argv]), contextlib.redirect_stdout(out):
            code = gaps.main()
        return code, out.getvalue()

    def test_out_of_range_limit(self):
        with mock.patch.object(gaps, "check_library", wraps=gaps.check_library) as spy:
            code, _ = self.run_main("--limit", "9999")
        self.assertEqual(code, 0)
        self.assertEqual(spy.call_args[0][3], 500)

    def test_check(self):
        code, out = self.run_main("--check")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["plex"]["server"], "Test Server")
        self.assertEqual([s.path for s in self.server.requests], ["/"])

    def test_error_exit_code(self):
        code, _ = self.run_main("--library", "Movies")
        self.assertEqual(code, 1)
        self.assertIn("error: Only TV libraries", self.stderr.getvalue())


# ---------------------------------------------------------------- media deletion setting


class MediaDeletion(Base):
    def test_media_deletion_setting(self):
        def build(answer):
            self.server.routes["/:/prefs"] = answer
            self.server.requests.clear()
            return self.report(), self.server.requests
        check_media_deletion(self, build)

    def test_connection_check_skips_settings(self):
        gaps.check(config())
        self.assertNotIn("/:/prefs", [seen.path for seen in self.server.requests])
