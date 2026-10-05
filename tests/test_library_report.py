"""library-report (openspec/specs/library-report/spec.md)."""

import argparse
import io
import re
import time
from unittest import mock

from helpers import FAKE_TOKEN, FakeServer, OfflineTestCase, fixture, load_script, plex_container

lr = load_script("library-report")
GB = 1000 ** 3


def movie(title, guid="plex://movie/x", year=None, media=(), **extra):
    item = {"title": title, "guid": guid, "Media": list(media)}
    if year:
        item["year"] = year
    item.update(extra)
    return item


def media(resolution="1080", codec="h264", gb=1.0, parts=1, **extra):
    size = int(gb * GB / parts)
    return dict({"videoResolution": resolution, "videoCodec": codec,
                 "Part": [{"size": size} for _ in range(parts)]}, **extra)


def args(**overrides):
    values = {"library": None, "recent": 10, "large_gb": 40.0, "duplicate_examples": 15,
              "upgrade_examples": 15, "growth_months": 12}
    values.update(overrides)
    return argparse.Namespace(**values)


# ---------------------------------------------------------------- small helpers

class MediaDetails(OfflineTestCase):
    def test_resolution_bucket(self):
        cases = {"4k": "4K", "2160": "4K", "2k": "2K", "1080": "1080p", "720": "720p", "480": "SD",
                 "576": "SD", "sd": "SD", "SD": "SD", None: "unknown", "": "unknown", "8k": "8k"}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(lr.resolution_bucket(value), expected)

    def test_ten_bit(self):
        self.assertTrue(lr.is_ten_bit({"videoProfile": "main 10"}))
        self.assertTrue(lr.is_ten_bit({"videoProfile": "high 10"}))
        self.assertFalse(lr.is_ten_bit({"videoProfile": "high"}))
        self.assertFalse(lr.is_ten_bit({}))

    def test_unmatched(self):
        self.assertTrue(lr.is_unmatched({"guid": "local://12"}))
        self.assertTrue(lr.is_unmatched({"guid": ""}))
        self.assertTrue(lr.is_unmatched({}))
        self.assertFalse(lr.is_unmatched({"guid": "plex://movie/abc"}))

    def test_copies_skip_missing_files_and_optimized_versions(self):
        item = movie("Film", media=[
            media("1080", gb=8, parts=2),             # one copy split into two files
            media("4k", "hevc", gb=50),
            media("720", gb=2, proxyType=42),          # Plex optimized version
            media("480", gb=1, deletedAt=1700000000),  # file no longer on disk
        ])
        found = lr.copies(item)
        self.assertEqual([c["resolution"] for c in found], ["4K", "1080p"])  # largest first
        self.assertEqual(found[1]["bytes"], 8 * GB)

    def test_labels(self):
        self.assertEqual(lr.movie_label({"title": "Heat", "year": 1995}), "Heat (1995)")
        self.assertEqual(lr.movie_label({"title": "Home Video"}), "Home Video")
        self.assertEqual(lr.episode_label({"grandparentTitle": "The Show", "parentIndex": 2, "index": 5}),
                         "The Show S02E05")


class TallyAndHousekeeping(OfflineTestCase):
    def test_tally(self):
        tally = lr.Tally(large_bytes=40 * GB)
        tally.add(movie("Big", media=[media("4k", "HEVC", gb=60, videoProfile="main 10", audioCodec="TrueHD")]), "Big")
        tally.add(movie("Split", media=[media("1080", gb=8, parts=2, audioCodec="ac3")]), "Split")
        tally.add(movie("Gone", media=[media("720", gb=1, deletedAt=1)]), "Gone")
        out = tally.as_dict()
        self.assertEqual(out["files"], 4)
        self.assertEqual(out["size_gb"], 69.0)
        self.assertEqual(out["resolution"], {"4K": 1, "1080p": 1, "720p": 1})
        self.assertEqual(out["video_codec"], {"hevc": 1, "h264": 2})
        self.assertEqual(out["audio_codec"], {"truehd": 1, "ac3": 1})
        self.assertEqual(out["ten_bit_files"], 1)
        self.assertEqual(out["large_files"], [{"title": "Big", "gb": 60.0}])
        self.assertEqual(out["large_files_total"], 1)
        self.assertEqual(out["unavailable_files"], 1)
        self.assertEqual(out["unavailable_examples"], ["Gone"])

    def test_music_tally_leaves_out_video_details(self):
        tally = lr.Tally(large_bytes=40 * GB)
        tally.add({"Media": [{"audioCodec": "flac", "Part": [{"size": 30 * 1000 ** 2}]}]}, "Track")
        out = tally.as_dict(video=False)
        self.assertNotIn("resolution", out)
        self.assertNotIn("large_files", out)
        self.assertEqual(out["audio_codec"], {"flac": 1})

    def test_housekeeping(self):
        items = [
            movie("Fine", thumb="/t/1"),
            movie("No Poster"),
            movie("Unmatched", guid="local://3", thumb="/t/3"),
        ]
        out = lr.housekeeping(items, lambda i: i["title"])
        self.assertEqual(out, {
            "missing_poster_count": 1, "missing_poster_examples": ["No Poster"],
            "unmatched_count": 1, "unmatched_examples": ["Unmatched"],
        })

    def test_housekeeping_examples_are_capped(self):
        items = [movie(f"Film {n}") for n in range(40)]
        out = lr.housekeeping(items, lambda i: i["title"])
        self.assertEqual(out["missing_poster_count"], 40)
        self.assertEqual(len(out["missing_poster_examples"]), 15)

    def test_recent_is_newest_first_and_limited(self):
        items = [movie("Old", addedAt=100), movie("New", addedAt=300), movie("Middle", addedAt=200)]
        self.assertEqual([r["title"] for r in lr.recent(items, 2, lambda i: i["title"])], ["New", "Middle"])


# ---------------------------------------------------------------- duplicates

class DuplicatesWithinALibrary(OfflineTestCase):
    def test_movie_with_two_copies(self):
        items = [
            movie("Arrival", year=2016, media=[media("1080", gb=10), media("4k", "hevc", gb=60)]),
            movie("Heat", year=1995, media=[media("1080", gb=8)]),
        ]
        out = lr.library_duplicates(items, lr.movie_label, limit=15)
        self.assertEqual(out["titles"], 1)
        self.assertEqual(out["extra_copies"], 1)
        self.assertEqual(out["extra_gb"], 10.0)  # every copy except the largest
        self.assertEqual(out["examples"], [{
            "title": "Arrival (2016)",
            "copies": [{"resolution": "4K", "video_codec": "hevc", "gb": 60.0},
                       {"resolution": "1080p", "video_codec": "h264", "gb": 10.0}],
            "extra_gb": 10.0,
        }])

    def test_optimized_versions_and_missing_files_are_not_duplicates(self):
        items = [movie("Film", media=[media("1080", gb=8), media("720", gb=2, proxyType=42),
                                      media("1080", gb=8, deletedAt=1)])]
        out = lr.library_duplicates(items, lr.movie_label, limit=15)
        self.assertEqual(out["titles"], 0)
        self.assertEqual(out["examples"], [])

    def test_three_copies_count_two_extra(self):
        items = [movie("Film", media=[media(gb=3), media(gb=2), media(gb=1)])]
        out = lr.library_duplicates(items, lr.movie_label, limit=15)
        self.assertEqual(out["extra_copies"], 2)
        self.assertEqual(out["extra_gb"], 3.0)

    def test_episodes_are_grouped_by_show(self):
        def episode(show, key, number, *copies):
            return {"grandparentTitle": show, "grandparentRatingKey": key, "parentIndex": 1, "index": number,
                    "Media": list(copies)}
        items = [
            episode("The Show", "10", 1, media(gb=3), media("720", gb=1)),
            episode("The Show", "10", 2, media(gb=3), media("720", gb=1)),
            episode("Other Show", "11", 1, media(gb=2), media("720", gb=2)),
            episode("Other Show", "11", 2, media(gb=2)),
        ]
        out = lr.library_duplicates(items, lr.episode_label, limit=15, by_show=True)
        self.assertEqual(out["titles"], 3)
        self.assertEqual(out["extra_gb"], 4.0)
        self.assertCountEqual(out["examples"], [
            {"title": "The Show", "episodes": 2, "extra_gb": 2.0},
            {"title": "Other Show", "episodes": 1, "extra_gb": 2.0},
        ])

    def test_example_limit_keeps_the_biggest(self):
        items = [movie(f"Film {n}", media=[media(gb=10), media(gb=n)]) for n in range(1, 6)]
        out = lr.library_duplicates(items, lr.movie_label, limit=2)
        self.assertEqual(out["titles"], 5)
        self.assertEqual([e["title"] for e in out["examples"]], ["Film 5", "Film 4"])

    def test_limit_zero_gives_counts_only(self):
        items = [movie("Film", media=[media(gb=2), media(gb=1)])]
        out = lr.library_duplicates(items, lr.movie_label, limit=0)
        self.assertEqual(out["titles"], 1)
        self.assertEqual(out["examples"], [])


class DuplicatesAcrossLibraries(OfflineTestCase):
    def test_same_movie_in_two_libraries(self):
        guids = {}
        lr.remember_guids(guids, [movie("Arrival", "plex://movie/a", 2016, [media("4k", gb=60), media(gb=10)])],
                          "Movies", lr.movie_label)
        lr.remember_guids(guids, [movie("Arrival", "plex://movie/a", 2016, [media(gb=12)]),
                                  movie("Cars", "plex://movie/c", 2006, [media(gb=5)])],
                          "Kids Movies", lr.movie_label)
        out = lr.cross_library_duplicates(guids, limit=15)
        self.assertEqual(out["titles"], 1)
        self.assertEqual(out["extra_gb"], 12.0)  # each library counts once, by its largest copy
        self.assertEqual(out["examples"], [{
            "title": "Arrival (2016)",
            "libraries": [{"library": "Movies", "resolution": "4K", "gb": 60.0},
                          {"library": "Kids Movies", "resolution": "1080p", "gb": 12.0}],
            "extra_gb": 12.0,
        }])

    def test_unmatched_items_and_missing_files_are_ignored(self):
        guids = {}
        lr.remember_guids(guids, [movie("Home", "local://1", media=[media()]),
                                  movie("Gone", "plex://movie/g", media=[media(deletedAt=1)])], "A", lr.movie_label)
        lr.remember_guids(guids, [movie("Home", "local://1", media=[media()]),
                                  movie("Gone", "plex://movie/g", media=[media()])], "B", lr.movie_label)
        self.assertEqual(lr.cross_library_duplicates(guids, limit=15)["titles"], 0)

    def test_episodes_are_grouped_by_show(self):
        def episode(guid, gb):
            return {"grandparentTitle": "The Show", "guid": guid, "Media": [media(gb=gb)]}
        guids = {}
        lr.remember_guids(guids, [episode("e1", 3), episode("e2", 3)], "TV", lr.episode_label, show=True)
        lr.remember_guids(guids, [episode("e1", 1), episode("e2", 1)], "Kids TV", lr.episode_label, show=True)
        out = lr.cross_library_duplicates(guids, limit=15)
        self.assertEqual(out["titles"], 2)
        self.assertEqual(out["examples"], [
            {"title": "The Show", "episodes": 2, "libraries": ["Kids TV", "TV"], "extra_gb": 2.0}])


# ---------------------------------------------------------------- upgrade candidates

def upgrades(libraries, limit=15, by_show=False):
    """Run the upgrade steps the way build_report does: every library first, then each one's section."""
    ranks, pending = {}, []
    for name, items in libraries.items():
        label = lr.episode_label if by_show else lr.movie_label
        pending.append((name, lr.upgrade_candidates(items, label, ranks, name)))
    return {name: lr.library_upgrades(found, ranks, name, limit, by_show) for name, found in pending}


class UpgradeCandidates(OfflineTestCase):
    def test_best_copy_is_the_highest_resolution(self):
        item = movie("Film", media=[media("720", gb=20), media("1080", gb=8), media("1080", gb=9),
                                    media("4k", gb=60, deletedAt=1), media("8k", gb=90)])
        best = lr.best_copy(item)
        self.assertEqual((best["resolution"], best["bytes"]), ("1080p", 9 * GB))
        self.assertIsNone(lr.best_copy(movie("Odd", media=[media(None), media("8k")])))

    def test_old_sd_movie(self):
        out = upgrades({"Movies": [movie("Old", year=1950, media=[media("480", "mpeg4", gb=1.4)]),
                                   movie("New", media=[media("1080")])]})["Movies"]
        self.assertEqual(out, {
            "titles": 1,
            "by_resolution": {"SD": 1, "720p": 0},
            "covered_elsewhere": 0,
            "examples": [{"title": "Old (1950)", "resolution": "SD", "video_codec": "mpeg4", "gb": 1.4}],
        })

    def test_better_copy_in_the_same_library(self):
        out = upgrades({"Movies": [movie("Film", media=[media("720"), media("1080")])]})["Movies"]
        self.assertEqual(out["titles"], 0)

    def test_optimized_version_does_not_count_as_better(self):
        out = upgrades({"Movies": [movie("Film", media=[media("720"), media("1080", proxyType=42)])]})["Movies"]
        self.assertEqual(out["by_resolution"], {"SD": 0, "720p": 1})

    def test_unknown_resolution_is_left_out(self):
        out = upgrades({"Movies": [movie("Film", media=[media(None)])]})["Movies"]
        self.assertEqual(out["titles"], 0)

    def test_better_copy_in_another_library(self):
        out = upgrades({
            "Movies": [movie("Film", "plex://movie/abc", media=[media("720")]),
                       movie("Home", "local://1", media=[media("720")])],
            "4K Movies": [movie("Film", "plex://movie/abc", media=[media("4k")]),
                          movie("Home", "local://1", media=[media("4k")])],
        })
        self.assertEqual(out["Movies"]["titles"], 1)  # the local:// item can't be matched
        self.assertEqual(out["Movies"]["examples"][0]["title"], "Home")
        self.assertEqual(out["Movies"]["covered_elsewhere"], 1)
        self.assertEqual(out["4K Movies"]["titles"], 0)

    def test_other_library_that_is_also_low_quality_does_not_cover(self):
        out = upgrades({"Movies": [movie("Film", media=[media("720")])],
                        "Kids Movies": [movie("Film", media=[media("480")])]})
        self.assertEqual((out["Movies"]["titles"], out["Kids Movies"]["titles"]), (1, 1))

    def test_movies_are_ordered_sd_first_then_by_title(self):
        items = [movie(t, media=[media(r)]) for t, r in [("b", "720"), ("A", "720"), ("c", "sd"), ("D", "1080")]]
        out = upgrades({"Movies": items})["Movies"]
        self.assertEqual([e["title"] for e in out["examples"]], ["c", "A", "b"])

    def test_series_is_grouped_by_show(self):
        def episode(show, number, resolution):
            return {"grandparentTitle": show, "grandparentRatingKey": show, "guid": f"{show}/{number}",
                    "parentIndex": 1, "index": number, "Media": [media(resolution)]}
        items = ([episode("Old Show", n, "720") for n in range(30)] + [episode("Old Show", 30 + n, "480") for n in range(2)]
                 + [episode("Small Show", 1, "720"), episode("New Show", 1, "1080")])
        out = upgrades({"TV": items}, by_show=True)["TV"]
        self.assertEqual(out["titles"], 33)
        self.assertEqual(out["examples"], [
            {"title": "Old Show", "episodes": 32, "by_resolution": {"SD": 2, "720p": 30}},
            {"title": "Small Show", "episodes": 1, "by_resolution": {"SD": 0, "720p": 1}},
        ])

    def test_example_limit(self):
        items = [movie(f"Film {n}", media=[media("720")]) for n in range(5)]
        self.assertEqual(len(upgrades({"Movies": items}, limit=2)["Movies"]["examples"]), 2)
        out = upgrades({"Movies": items}, limit=0)["Movies"]
        self.assertEqual((out["titles"], out["examples"]), (5, []))


def local_ts(year, month, day=15):
    """A timestamp in the middle of a local calendar day, so the time zone can't move its month."""
    return int(time.mktime((year, month, day, 12, 0, 0, 0, 0, -1)))


class GrowthByMonth(OfflineTestCase):
    MAY_2026 = local_ts(2026, 5, 20)

    def test_month_keys(self):
        self.assertEqual(lr.month_keys(3, now=self.MAY_2026), ["2026-03", "2026-04", "2026-05"])
        self.assertEqual(lr.month_keys(3, now=local_ts(2026, 1)), ["2025-11", "2025-12", "2026-01"])
        self.assertEqual(lr.month_keys(0, now=self.MAY_2026), [])
        self.assertEqual(len(lr.month_keys(120, now=self.MAY_2026)), 120)

    def test_two_months_with_a_gap(self):
        keys = lr.month_keys(3, now=self.MAY_2026)
        items = [
            movie("A", addedAt=local_ts(2026, 3, 2), media=[media(gb=10)]),
            movie("B", addedAt=local_ts(2026, 3, 28), media=[media(gb=5)]),
            movie("C", addedAt=local_ts(2026, 5, 1), media=[media(gb=20)]),
        ]
        out = lr.growth_section(lr.growth_counts(items, keys), keys)
        self.assertEqual(out["months"], [
            {"month": "2026-03", "added": 2, "gb": 15.0},
            {"month": "2026-04", "added": 0, "gb": 0.0},
            {"month": "2026-05", "added": 1, "gb": 20.0},
        ])
        self.assertEqual((out["added"], out["gb"]), (3, 35.0))

    def test_added_before_the_period_or_undated_is_not_counted(self):
        keys = lr.month_keys(12, now=self.MAY_2026)
        items = [movie("Old", addedAt=local_ts(2023, 5), media=[media(gb=9)]),
                 movie("No date", media=[media(gb=9)])]
        out = lr.growth_section(lr.growth_counts(items, keys), keys)
        self.assertEqual((out["added"], out["gb"]), (0, 0.0))
        self.assertEqual(len(out["months"]), 12)

    def test_size_counts_every_file_as_the_media_breakdown_does(self):
        keys = lr.month_keys(1, now=self.MAY_2026)
        item = movie("Film", addedAt=self.MAY_2026, media=[
            media("1080", gb=8, parts=2), media("720", gb=2, proxyType=42), media("480", gb=1, deletedAt=1)])
        self.assertEqual(lr.growth_counts([item], keys)["2026-05"], [1, 11 * GB])

    def test_no_months(self):
        out = lr.growth_section(lr.growth_counts([movie("A", addedAt=self.MAY_2026)], []), [])
        self.assertEqual(out, {"added": 0, "gb": 0.0, "months": []})

    def test_growth_months_option_is_clamped(self):
        for given, expected in (("500", 120), ("-3", 0), ("6", 6)):
            with self.subTest(given=given):
                seen = {}
                with mock.patch.object(lr, "load_config", return_value=("http://192.0.2.10:32400", FAKE_TOKEN, True)), \
                        mock.patch.object(lr, "build_report", side_effect=lambda c, a: seen.update(months=a.growth_months) or {}), \
                        mock.patch("sys.argv", ["library_report.py", "--growth-months", given]), \
                        mock.patch("sys.stdout", io.StringIO()):
                    self.assertEqual(lr.main(), 0)
                self.assertEqual(seen["months"], expected)


# ---------------------------------------------------------------- whole report

def fake_plex(page_size=None):
    """A FakeServer for the sample libraries in tests/fixtures/library-report/."""
    items = {
        ("1", "1"): fixture("library-report", "movies.json"),
        ("2", "2"): fixture("library-report", "shows.json"),
        ("2", "3"): [{"title": "Season 1"}, {"title": "Season 1"}],
        ("2", "4"): fixture("library-report", "episodes.json"),
        ("3", "1"): fixture("library-report", "kids-movies.json"),
        ("4", "13"): [{"title": f"Photo {n}"} for n in range(250)],
    }

    def section(seen):
        key = re.match(r"/library/sections/(\d+)/all", seen.path).group(1)
        found = items.get((key, seen.query.get("type")), [])
        start = int(seen.headers.get("x-plex-container-start", 0))
        size = int(seen.headers.get("x-plex-container-size", len(found)))
        page = found[start:start + size]
        return plex_container(size=len(page), totalSize=len(found), Metadata=page)

    routes = {
        "/": fixture("library-report", "root.json"),
        "/library/sections": fixture("library-report", "sections.json"),
    }
    routes.update({f"/library/sections/{n}/all": section for n in "1234"})
    return FakeServer(routes)


FIXTURE_MONTH = time.strftime("%Y-%m", time.localtime(1700000000))  # when the sample items were added


class WholeReport(OfflineTestCase):
    def report(self, server, **options):
        client = lr.PlexClient("http://192.0.2.10:32400", FAKE_TOKEN, True)
        server.attach(client._opener)
        # Pretend it's the month the sample items were added, so growth doesn't depend on today's date.
        month_keys = lr.month_keys
        with mock.patch.object(lr, "month_keys", lambda n: month_keys(n, now=1700000000 + 86400)):
            return lr.build_report(client, args(**options))

    def test_server_and_totals(self):
        report = self.report(fake_plex())
        self.assertEqual(report["server"], {"name": "Test Server", "version": "1.40.0.0000-test", "platform": "Linux"})
        self.assertEqual(report["totals"], {"libraries": 4, "files": 12, "size_gb": 145.5})
        self.assertEqual([lib["name"] for lib in report["libraries"]], ["Movies", "TV", "Kids Movies", "Photos"])

    def test_movie_library(self):
        movies = self.report(fake_plex())["libraries"][0]
        self.assertEqual(movies["counts"], {"movies": 4})
        m = movies["media"]
        self.assertEqual((m["files"], m["size_gb"]), (7, 126.0))
        self.assertEqual(m["resolution"], {"4K": 1, "1080p": 3, "720p": 1, "SD": 1})
        self.assertEqual(m["ten_bit_files"], 2)
        self.assertEqual([f["title"] for f in m["large_files"]], ["Arrival (2016)", "Lost Film (2001)"])
        self.assertEqual(m["unavailable_examples"], ["Lost Film (2001)"])
        self.assertEqual(movies["housekeeping"]["missing_poster_examples"], ["Heat (1995)"])
        self.assertEqual(movies["housekeeping"]["unmatched_examples"], ["Home Video"])
        self.assertEqual([r["title"] for r in movies["recently_added"]],
                         ["Arrival (2016)", "Heat (1995)", "Home Video", "Lost Film (2001)"])
        self.assertEqual(movies["duplicates"]["titles"], 1)
        self.assertEqual(movies["duplicates"]["extra_gb"], 10.0)

    def test_show_library(self):
        tv = self.report(fake_plex())["libraries"][1]
        self.assertEqual(tv["counts"], {"shows": 2, "seasons": 2, "episodes": 3})
        self.assertEqual(tv["media"]["files"], 4)
        self.assertEqual(tv["housekeeping"]["unmatched_examples"], ["Mystery Show"])
        self.assertEqual(tv["duplicates"]["examples"], [{"title": "The Show", "episodes": 1, "extra_gb": 1.0}])
        self.assertEqual(tv["recently_added"][0]["title"], "The Show S01E02")

    def test_upgrades(self):
        report = self.report(fake_plex())
        movies, tv, kids = report["libraries"][:3]
        self.assertEqual(movies["upgrades"]["examples"],
                         [{"title": "Home Video", "resolution": "SD", "video_codec": "mpeg2video", "gb": 1.0}])
        self.assertEqual(tv["upgrades"]["examples"],
                         [{"title": "Mystery Show", "episodes": 1, "by_resolution": {"SD": 1, "720p": 0}}])
        self.assertEqual(kids["upgrades"]["titles"], 0)

    def test_growth(self):
        report = self.report(fake_plex())
        movies, tv, kids, photos = report["libraries"]
        self.assertEqual(movies["growth"]["months"][-1], {"month": FIXTURE_MONTH, "added": 4, "gb": 126.0})
        self.assertEqual(len(movies["growth"]["months"]), 12)
        self.assertEqual((tv["growth"]["added"], tv["growth"]["gb"]), (3, tv["media"]["size_gb"]))
        self.assertEqual(kids["growth"]["added"], 1)
        self.assertNotIn("growth", photos)
        # The combined section adds every library up, month by month.
        self.assertEqual(report["growth"]["added"], 8)
        self.assertEqual(report["growth"]["gb"], report["totals"]["size_gb"])
        self.assertEqual(report["growth"]["months"][-1]["added"], 8)

    def test_growth_months_zero(self):
        report = self.report(fake_plex(), growth_months=0)
        self.assertEqual(report["growth"], {"added": 0, "gb": 0.0, "months": []})
        self.assertEqual(report["libraries"][0]["growth"]["months"], [])

    def test_music_library_has_no_duplicates_or_upgrades(self):
        client = mock.Mock(get_all=lambda sid, kind: [], count=lambda sid, kind: 0)
        music = lr.summarise_section(client, {"key": "9", "type": "artist", "title": "Music"}, args(), {}, {}, [],
                                     [], [])
        self.assertNotIn("duplicates", music)
        self.assertNotIn("upgrades", music)

    def test_music_growth_counts_tracks(self):
        added = 1700000000
        tracks = [{"title": f"Track {n}", "addedAt": added, "Media": [{"Part": [{"size": GB}]}]} for n in range(3)]
        albums = [{"title": "Album", "parentTitle": "Band", "addedAt": added}]
        client = mock.Mock(get_all=lambda sid, kind: tracks if kind == lr.TYPE_TRACK else albums,
                           count=lambda sid, kind: 1)
        keys = lr.month_keys(1, now=added)
        music = lr.summarise_section(client, {"key": "9", "type": "artist", "title": "Music"}, args(), {}, {}, [],
                                     keys, [])
        self.assertEqual(music["growth"]["months"], [{"month": keys[0], "added": 3, "gb": 3.0}])

    def test_photo_library_is_counted_only(self):
        photos = self.report(fake_plex())["libraries"][3]
        self.assertEqual(photos, {"name": "Photos", "type": "photo", "counts": {"photos": 250}})

    def test_cross_library_duplicates(self):
        cross = self.report(fake_plex())["cross_library_duplicates"]
        self.assertEqual(cross["titles"], 1)
        self.assertEqual(cross["extra_gb"], 12.0)
        self.assertEqual(cross["examples"][0]["title"], "Arrival (2016)")

    def test_only_allowed_get_requests(self):
        server = fake_plex()
        self.report(server)
        self.assertTrue(server.requests)
        for seen in server.requests:
            self.assertEqual(seen.method, "GET")
            self.assertTrue(any(rule.match(seen.path) for rule in lr.ALLOWED_PATHS), seen.path)

    def test_library_filter_ignores_case(self):
        report = self.report(fake_plex(), library=["tv", "KIDS MOVIES"])
        self.assertEqual([lib["name"] for lib in report["libraries"]], ["TV", "Kids Movies"])
        self.assertEqual(report["cross_library_duplicates"]["titles"], 0)

    def test_library_filter_that_matches_nothing(self):
        with self.assertRaises(lr.ReportError) as caught:
            self.report(fake_plex(), library=["Nope"])
        self.assertIn("No library matched", str(caught.exception))

    def test_items_are_read_in_pages(self):
        server = fake_plex()
        with mock.patch.object(lr, "PAGE_SIZE", 3):
            report = self.report(server, library=["Movies"])
        self.assertEqual(report["libraries"][0]["counts"], {"movies": 4})
        starts = [s.headers["x-plex-container-start"] for s in server.requests
                  if s.path == "/library/sections/1/all"]
        self.assertEqual(starts, ["0", "3"])

    def test_progress_goes_to_stderr(self):
        self.report(fake_plex())
        self.assertIn("reading library: Movies", self.stderr.getvalue())
