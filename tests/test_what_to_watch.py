"""what-to-watch (openspec/specs/what-to-watch/spec.md)."""

import argparse
import contextlib
import io
import json
import sys
from unittest import mock

from helpers import (FAKE_API_KEY, FAKE_TOKEN, FakeServer, OfflineTestCase, fixture, load_script,
                     check_media_deletion)

wtw = load_script("what-to-watch")

PLEX = ("http://192.0.2.10:32400", FAKE_TOKEN, True)
TAUTULLI = ("http://192.0.2.10:8181", FAKE_API_KEY, True)


def args(**overrides):
    values = {
        "type": None, "library": None, "genre": None, "min_minutes": None, "max_minutes": None,
        "decade": None, "year_from": None, "year_to": None, "min_rating": None,
        "content_rating": None, "unwatched": False, "continue_watching": False, "sort": None,
        "limit": 20,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def config(plex=PLEX, tautulli=TAUTULLI):
    return {"plex": plex, "tautulli": tautulli, "tautulli_problem": None}


# ---------------------------------------------------------------- fake server

def listing(data, section):
    """A section's listing, paged, narrowed by Plex's genre filter when the request has one."""
    def page(seen):
        items = data["sections"][section]
        if "genre" in seen.query:
            members = set(data["genre_members"].get(seen.query["genre"], []))
            items = [i for i in items if i["ratingKey"] in members]
        start = int(seen.headers.get("x-plex-container-start", 0))
        size = int(seen.headers.get("x-plex-container-size", len(items)))
        return {"MediaContainer": {"Metadata": items[start:start + size], "totalSize": len(items)}}
    return page


def routes():
    data = fixture("what-to-watch", "plex.json")
    result = {
        "/": data["/"],
        "/library/sections": data["/library/sections"],
        "/library/onDeck": data["/library/onDeck"],
    }
    for section in data["sections"]:
        result[f"/library/sections/{section}/all"] = listing(data, section)
        result[f"/library/sections/{section}/genre"] = {
            "MediaContainer": {"Directory": data["genres"][section]}}
    return result


class Base(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.server = FakeServer(routes())
        real = wtw.build_opener
        patcher = mock.patch.object(wtw, "build_opener",
                                    lambda url, verify: self.server.attach(real(url, verify)))
        patcher.start()
        self.addCleanup(patcher.stop)
        # Random order is replaced with "leave as is" (title order), so results are predictable.
        patcher = mock.patch.object(wtw, "shuffle", lambda items: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def report(self, cfg=None, **kw):
        return wtw.build_report(cfg or config(), args(**kw))

    def titles(self, **kw):
        return [t["title"] for t in self.report(**kw)["titles"]]

    def title(self, name, **kw):
        return next(t for t in self.report(**kw)["titles"] if t["title"] == name)


ALL_TITLES = [
    "Critic Only (1988)", "Finished Show", "Fresh Show", "Half Watched (2001)", "Long Epic (1994)",
    "No Guid (1999)", "No Guid (1999)", "No Rating (2010)", "No Year", "Only In 4K (2020)",
    "Quiet Comedy (1985)", "Shared Film (2015)", "Started Show",
]


# ---------------------------------------------------------------- sources

class Sources(Base):
    def test_only_allowed_plex_requests(self):
        self.report(genre=["comedy"])
        self.report(continue_watching=True)
        self.assertTrue(self.server.requests)
        for seen in self.server.requests:
            self.assertEqual(seen.method, "GET")
            self.assertTrue(seen.url.startswith(PLEX[0] + "/"), seen.url)
            self.assertTrue(any(rule.match(seen.path) for rule in wtw.ALLOWED_PATHS), seen.path)

    def test_tautulli_is_never_contacted(self):
        self.report()
        self.assertNotIn("/api/v2", {s.path for s in self.server.requests})
        self.assertFalse(hasattr(wtw, "TautulliClient"))

    def test_library_items_are_read_in_pages_of_500(self):
        self.report()
        listings = [s for s in self.server.requests if s.path.endswith("/all")]
        self.assertTrue(listings)
        for seen in listings:
            self.assertEqual(seen.headers["x-plex-container-size"], "500")

    def test_not_configured(self):
        with self.assertRaises(wtw.ReportError) as caught:
            self.report(config(plex=None))
        self.assertTrue(str(caught.exception).startswith("NOT_CONFIGURED: "))


# ---------------------------------------------------------------- libraries

class Libraries(Base):
    def test_music_is_skipped(self):
        report = self.report()
        self.assertEqual(report["skipped_libraries"], [{"name": "Music", "type": "artist"}])
        self.assertEqual(report["libraries_checked"], ["Movies", "4K Movies", "TV Shows"])

    def test_music_library_asked_for(self):
        with self.assertRaises(wtw.ReportError) as caught:
            self.report(library=["music"])
        self.assertIn("Only movie and TV libraries", str(caught.exception))

    def test_unknown_library(self):
        with self.assertRaises(wtw.ReportError) as caught:
            self.report(library=["Cartoons"])
        self.assertIn("No library matched", str(caught.exception))

    def test_library_option_is_case_insensitive(self):
        report = self.report(library=["tv shows"])
        self.assertEqual(report["libraries_checked"], ["TV Shows"])
        self.assertEqual([t["title"] for t in report["titles"]], ["Finished Show", "Fresh Show", "Started Show"])

    def test_type_movie(self):
        report = self.report(type="movie")
        self.assertEqual(report["libraries_checked"], ["Movies", "4K Movies"])
        self.assertTrue(all(t["type"] == "movie" for t in report["titles"]))

    def test_type_show(self):
        self.assertEqual(self.titles(type="show"), ["Finished Show", "Fresh Show", "Started Show"])


# ---------------------------------------------------------------- watched status

class Watched(Base):
    def test_movie_states(self):
        self.assertEqual(self.title("Long Epic (1994)")["watched"], "watched")
        self.assertEqual(self.title("Half Watched (2001)")["watched"], "in_progress")
        self.assertEqual(self.title("Quiet Comedy (1985)")["watched"], "unwatched")

    def test_show_states(self):
        self.assertEqual(self.title("Fresh Show")["watched"], "unwatched")
        self.assertEqual(self.title("Started Show")["watched"], "started")
        self.assertEqual(self.title("Finished Show")["watched"], "watched")

    def test_unwatched_only(self):
        self.assertEqual(self.titles(unwatched=True), [
            "Critic Only (1988)", "Fresh Show", "Half Watched (2001)", "No Guid (1999)",
            "No Guid (1999)", "No Rating (2010)", "No Year", "Only In 4K (2020)", "Quiet Comedy (1985)",
        ])

    def test_a_started_show_is_not_unwatched(self):
        self.assertNotIn("Started Show", self.titles(unwatched=True))


# ---------------------------------------------------------------- filters

class Filters(Base):
    def test_genre_uses_plex_genre_filter(self):
        # Quiet Comedy's listing shows only Drama and Romance; Plex's filter knows it's a comedy.
        self.assertEqual(self.titles(genre=["comedy"]), [
            "Critic Only (1988)", "Finished Show", "Fresh Show", "Half Watched (2001)", "No Year",
            "Quiet Comedy (1985)", "Started Show",
        ])
        asked = {(s.path, s.query.get("genre")) for s in self.server.requests if "genre" in s.query}
        self.assertEqual(asked, {("/library/sections/1/all", "10"), ("/library/sections/3/all", "30")})

    def test_several_genres_mean_any_of_them(self):
        self.assertEqual(self.titles(genre=["Horror", "History"]), ["Long Epic (1994)", "No Rating (2010)"])

    def test_a_genre_the_library_does_not_have(self):
        report = self.report(genre=["Western"])
        self.assertEqual(report["matches"], 0)
        self.assertEqual(report["titles"], [])
        self.assertEqual(report["genres_available"], [
            "Action", "Animation", "Comedy", "Drama", "History", "Horror", "Romance",
            "Science Fiction", "Thriller",
        ])

    def test_short_comedies(self):
        self.assertEqual(self.titles(genre=["comedy"], max_minutes=100), [
            "Critic Only (1988)", "Finished Show", "Fresh Show", "Quiet Comedy (1985)", "Started Show",
        ])

    def test_max_minutes_is_inclusive_and_needs_a_length(self):
        titles = self.titles(max_minutes=100)
        self.assertIn("No Rating (2010)", titles)
        self.assertNotIn("No Year", titles)

    def test_min_minutes(self):
        self.assertEqual(self.titles(min_minutes=120),
                         ["Long Epic (1994)", "Only In 4K (2020)", "Shared Film (2015)"])

    def test_decade(self):
        self.assertEqual(self.titles(decade="1980s"), ["Critic Only (1988)", "Quiet Comedy (1985)"])
        self.assertEqual(self.titles(decade="1980"), ["Critic Only (1988)", "Quiet Comedy (1985)"])

    def test_year_range(self):
        self.assertEqual(self.titles(year_from=2010, year_to=2015),
                         ["No Rating (2010)", "Shared Film (2015)", "Started Show"])

    def test_decade_and_year_together(self):
        with self.assertRaises(wtw.ReportError) as caught:
            self.report(decade="1990s", year_from=1995)
        self.assertIn("not both", str(caught.exception))

    def test_bad_decade(self):
        for value in ("nineties", "1995", "90s"):
            with self.subTest(value=value), self.assertRaises(wtw.ReportError) as caught:
                self.report(decade=value)
            self.assertIn("--decade", str(caught.exception))

    def test_min_rating_uses_audience_then_critic(self):
        # Quiet Comedy has audience 7.5 and critic 8.0: the audience rating decides.
        self.assertEqual(self.titles(min_rating=8),
                         ["Critic Only (1988)", "Fresh Show", "Long Epic (1994)"])

    def test_bad_min_rating(self):
        with self.assertRaises(wtw.ReportError) as caught:
            self.report(min_rating=12)
        self.assertIn("--min-rating", str(caught.exception))

    def test_content_rating_is_case_insensitive(self):
        self.assertEqual(self.titles(content_rating=["PG"]), ["Critic Only (1988)", "Quiet Comedy (1985)"])

    def test_content_ratings_available(self):
        self.assertEqual(self.report()["content_ratings_available"],
                         ["PG", "pg", "PG-13", "R", "TV-14", "TV-PG"])

    def test_available_lists_ignore_the_other_filters(self):
        narrow = self.report(genre=["Horror"], unwatched=True)
        full = self.report()
        self.assertEqual(narrow["genres_available"], full["genres_available"])
        self.assertEqual(narrow["content_ratings_available"], full["content_ratings_available"])


# ---------------------------------------------------------------- same title in two libraries

class Merging(Base):
    def test_same_movie_in_two_libraries(self):
        report = self.report()
        shared = [t for t in report["titles"] if t["title"] == "Shared Film (2015)"]
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0]["libraries"], ["Movies", "4K Movies"])
        self.assertEqual(shared[0]["watched"], "watched")

    def test_items_without_guid_are_not_merged(self):
        self.assertEqual(self.titles().count("No Guid (1999)"), 2)

    def test_shows_use_the_copy_with_most_episodes_watched(self):
        section_a = {"key": "3", "type": "show", "title": "TV"}
        section_b = {"key": "5", "type": "show", "title": "TV 4K"}
        base = {"title": "Same Show", "guid": "plex://show/x", "leafCount": 10, "childCount": 1}
        merged = wtw.merge([
            wtw.entry(section_a, dict(base, ratingKey="1", viewedLeafCount=0)),
            wtw.entry(section_b, dict(base, ratingKey="2", viewedLeafCount=4)),
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["watched"], "started")
        self.assertEqual(merged[0]["episodes_watched"], 4)
        self.assertEqual(merged[0]["libraries"], ["TV", "TV 4K"])


# ---------------------------------------------------------------- order and limit

class Order(Base):
    def test_random_is_the_default(self):
        with mock.patch.object(wtw, "shuffle", lambda items: items.reverse()):
            self.assertEqual(self.titles(), list(reversed(ALL_TITLES)))

    def test_rating(self):
        self.assertEqual(self.titles(sort="rating"), [
            "Critic Only (1988)", "Long Epic (1994)", "Fresh Show", "Quiet Comedy (1985)",
            "Started Show", "Shared Film (2015)", "No Guid (1999)", "No Guid (1999)",
            "Only In 4K (2020)", "Finished Show", "Half Watched (2001)", "No Year", "No Rating (2010)",
        ])

    def test_added(self):
        self.assertEqual(self.titles(sort="added")[:4],
                         ["Shared Film (2015)", "Only In 4K (2020)", "No Guid (1999)", "Finished Show"])

    def test_year_with_ties_by_title(self):
        self.assertEqual(self.titles(sort="year"), [
            "Only In 4K (2020)", "Fresh Show", "Shared Film (2015)", "Started Show", "No Rating (2010)",
            "Finished Show", "Half Watched (2001)", "No Guid (1999)", "No Guid (1999)",
            "Long Epic (1994)", "Critic Only (1988)", "Quiet Comedy (1985)", "No Year",
        ])

    def test_limit_keeps_the_count(self):
        report = self.report(limit=2)
        self.assertEqual(report["matches"], 13)
        self.assertEqual(len(report["titles"]), 2)


# ---------------------------------------------------------------- continue watching

class Continue(Base):
    def test_halfway_movie_and_next_episode(self):
        report = self.report(continue_watching=True)
        self.assertEqual(report["mode"], "continue")
        self.assertEqual(report["continue_watching"], [
            {"type": "movie", "title": "Half Watched (2001)", "library": "Movies",
             "progress_pct": 50.0, "minutes_left": 60, "last_viewed": wtw.day(1727000000)},
            {"type": "episode", "title": "Started Show", "library": "TV Shows", "episode": "S02E05",
             "episode_title": "The Fifth One", "progress_pct": 0, "minutes_left": 30,
             "last_viewed": wtw.day(1726000000)},
        ])
        self.assertNotIn("titles", report)

    def test_does_not_read_the_libraries(self):
        self.report(continue_watching=True)
        self.assertFalse([s for s in self.server.requests if s.path.endswith("/all")])

    def test_type_and_library(self):
        shows = self.report(continue_watching=True, type="show")["continue_watching"]
        self.assertEqual([e["title"] for e in shows], ["Started Show"])
        movies = self.report(continue_watching=True, library=["Movies"])["continue_watching"]
        self.assertEqual([e["title"] for e in movies], ["Half Watched (2001)"])

    def test_limit(self):
        self.assertEqual(len(self.report(continue_watching=True, limit=1)["continue_watching"]), 1)

    def test_other_filters_are_refused(self):
        for extra in ({"genre": ["drama"]}, {"sort": "rating"}, {"unwatched": True}, {"decade": "1990s"}):
            with self.subTest(**{k: str(v) for k, v in extra.items()}), \
                    self.assertRaises(wtw.ReportError) as caught:
                self.report(continue_watching=True, **extra)
            self.assertIn("--continue only works with --library, --type and --limit", str(caught.exception))


# ---------------------------------------------------------------- report contents

class Contents(Base):
    def test_top_level_fields(self):
        report = self.report()
        self.assertEqual(report["server"], {"name": "Test Server", "version": "1.40.0.0000"})
        self.assertEqual(report["mode"], "pick")
        self.assertEqual(report["matches"], 13)
        for field in ("cinemetric_version", "generated_at", "filters", "libraries_checked",
                      "skipped_libraries", "titles", "genres_available", "content_ratings_available"):
            self.assertIn(field, report)
        self.assertEqual(report["filters"]["sort"], "random")

    def test_movie_fields(self):
        self.assertEqual(self.title("Quiet Comedy (1985)"), {
            "type": "movie", "title": "Quiet Comedy (1985)", "year": 1985, "libraries": ["Movies"],
            "genres": ["Drama", "Romance"], "critic_rating": 8.0, "audience_rating": 7.5,
            "content_rating": "PG", "summary": "Made-up summary of Quiet Comedy.",
            "added": wtw.day(1700000100), "watched": "unwatched", "minutes": 95,
        })

    def test_show_fields(self):
        self.assertEqual(self.title("Started Show"), {
            "type": "show", "title": "Started Show", "year": 2015, "libraries": ["TV Shows"],
            "genres": ["Comedy", "Drama"], "critic_rating": None, "audience_rating": 7.2,
            "content_rating": "TV-14", "summary": "Made-up summary.", "added": wtw.day(1700002000),
            "watched": "started", "episode_minutes": 30, "seasons": 2, "episodes": 20,
            "episodes_watched": 3,
        })

    def test_missing_values_are_null(self):
        no_year = self.title("No Year")
        self.assertIsNone(no_year["year"])
        self.assertIsNone(no_year["minutes"])
        self.assertIsNone(no_year["audience_rating"])
        self.assertIsNone(no_year["content_rating"])

    def test_long_summary_is_cut(self):
        self.assertEqual(len(self.title("No Year")["summary"]), 120)

    def test_no_private_fields_in_output(self):
        for title in self.report()["titles"]:
            self.assertFalse([k for k in title if k.startswith("_")])


# ---------------------------------------------------------------- command line

class CommandLine(Base):
    def run_main(self, *argv, cfg=None):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["what_to_watch.py", *argv]), \
                mock.patch.object(wtw, "load_config", return_value=cfg or config()), \
                contextlib.redirect_stdout(out):
            code = wtw.main()
        return code, out.getvalue()

    def test_limit_is_kept_between_1_and_100(self):
        for given, used in (("9999", 100), ("0", 1)):
            with self.subTest(limit=given), \
                    mock.patch.object(wtw, "build_report", wraps=wtw.build_report) as build:
                code, _ = self.run_main("--limit", given)
            self.assertEqual(code, 0)
            self.assertEqual(build.call_args[0][1].limit, used)

    def test_check(self):
        code, out = self.run_main("--check")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"ok": True, "plex": {"server": "Test Server", "version": "1.40.0.0000"}})
        self.assertEqual([s.path for s in self.server.requests], ["/"])

    def test_errors_go_to_stderr(self):
        code, out = self.run_main("--decade", "nineties")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("error: --decade takes a value like 1990s.", self.stderr.getvalue())

    def test_report_is_json(self):
        code, out = self.run_main("--genre", "comedy", "--unwatched")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["matches"], 5)


# ---------------------------------------------------------------- media deletion setting


class MediaDeletion(Base):
    def test_media_deletion_setting(self):
        def build(answer):
            self.server.routes["/:/prefs"] = answer
            self.server.requests.clear()
            return self.report(), self.server.requests
        check_media_deletion(self, build)

    def test_continue_watching_has_it_too(self):
        def build(answer):
            self.server.routes["/:/prefs"] = answer
            self.server.requests.clear()
            return self.report(continue_watching=True), self.server.requests
        check_media_deletion(self, build)
