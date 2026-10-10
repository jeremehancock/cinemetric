"""export (openspec/specs/export/spec.md).

The export script runs the other report scripts as separate programs. Those programs wouldn't see a
test's fake server, so run_source() is replaced with canned report outputs from
fixtures/export/reports.json, and run_source() itself is tested with subprocess.run replaced.
"""

import argparse
import copy
import datetime
import json
import os
import re
import subprocess
import zipfile
from unittest import mock
from xml.etree import ElementTree

from helpers import (FAKE_TOKEN, FakeServer, OfflineTestCase, Reply, check_media_deletion, fixture,
                     load_script)

ex = load_script("export")

PLEX = ("http://192.0.2.10:32400", FAKE_TOKEN, True)
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NOW = datetime.datetime(2026, 10, 9, 12, 0).timestamp()
TODAY = "2026-10-09"


def args(**overrides):
    values = {"library": None, "tv": "shows", "language": None, "skip": [], "output": None, "replace": False}
    values.update(overrides)
    return argparse.Namespace(**values)


def config():
    return {"plex": PLEX, "tautulli": None, "tautulli_problem": None}


def paged(items, with_total=True):
    def page(seen):
        start = int(seen.headers.get("x-plex-container-start", 0))
        size = int(seen.headers.get("x-plex-container-size", len(items)))
        fields = {"Metadata": items[start:start + size]}
        if with_total:
            fields["totalSize"] = len(items)
        return {"MediaContainer": fields}
    return page


def routes(data):
    result = {"/": data["/"], "/library/sections": data["/library/sections"],
              "/:/prefs": {"MediaContainer": {"Setting": []}}}
    for section, by_type in data["listings"].items():
        result[f"/library/sections/{section}/all"] = (
            lambda seen, by_type=by_type: paged(by_type.get(seen.query.get("type"), []))(seen))
    for section, cols in data["collections"].items():
        result[f"/library/sections/{section}/collections"] = paged(cols)
    for key, children in data["children"].items():
        result[f"/library/collections/{key}/children"] = paged(children, with_total=False)
    return result


# ---------------------------------------------------------------- reading the workbook back

def column_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_workbook(path):
    """{tab name: rows}, each row a list of values: text, numbers, or datetime.date for dates."""
    with zipfile.ZipFile(path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        names = [s.get("name") for s in workbook.find("m:sheets", NS)]
        tabs = {}
        for i, name in enumerate(names, start=1):
            sheet = ElementTree.fromstring(archive.read(f"xl/worksheets/sheet{i}.xml"))
            rows = []
            for row in sheet.find("m:sheetData", NS):
                values = []
                for cell in row:
                    index = column_index(cell.get("r"))
                    values += [None] * (index - len(values))
                    if cell.get("t") == "inlineStr":
                        values.append("".join(t.text or "" for t in cell.iter(f"{{{NS['m']}}}t")))
                    else:
                        raw = cell.find("m:v", NS).text
                        number = float(raw) if "." in raw else int(raw)
                        if cell.get("s") == str(ex.DATE_STYLE):
                            number = datetime.date(1899, 12, 30) + datetime.timedelta(days=number)
                        values.append(number)
                rows.append(values)
            tabs[name] = rows
    return tabs


def table(rows):
    """Rows with column names as dicts, notes left out."""
    header = rows[0]
    out = []
    for row in rows[1:]:
        if not row or (isinstance(row[0], str) and row[0].startswith("Note: ")):
            continue
        out.append({name: (row[i] if i < len(row) else None) for i, name in enumerate(header)})
    return out


def notes(rows):
    return [row[0] for row in rows if row and isinstance(row[0], str) and row[0].startswith("Note: ")]


class Base(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.data = fixture("export", "plex.json")
        self.reports = fixture("export", "reports.json")
        self.failures = {}
        self.runs = []
        self.server = FakeServer(routes(self.data))
        real = ex.build_opener
        patcher = mock.patch.object(ex, "build_opener", lambda url, verify: self.server.attach(real(url, verify)))
        patcher.start()
        self.addCleanup(patcher.stop)

        def fake_run(name, extra):
            self.runs.append((name, list(extra)))
            if name in self.failures:
                return name, None, self.failures[name]
            return name, copy.deepcopy(self.reports[name]), None
        runner = mock.patch.object(ex, "run_source", fake_run)
        runner.start()
        self.addCleanup(runner.stop)

    def rebuild(self):
        self.server.routes = routes(self.data)

    def export(self, **overrides):
        summary = ex.build(config(), args(**overrides), now=NOW)
        return summary, read_workbook(summary["output"])

    def library_rows(self, **overrides):
        """Rows of the Movies tab, then the TV Shows tab, each with the tab it came from."""
        tabs = self.export(**overrides)[1]
        return [dict(row, Tab=tab) for tab in ("Movies", "TV Shows") for row in table(tabs.get(tab, [[]]))]

    def by_title(self, rows):
        return {row["Title"]: row for row in rows}


# ---------------------------------------------------------------- tabs, libraries and scripts run

class TabsAndSources(Base):
    def test_every_tab_in_order(self):
        summary, tabs = self.export()
        self.assertEqual(list(tabs), list(ex.TABS))
        self.assertEqual([t["name"] for t in summary["tabs"]], list(ex.TABS))

    def test_skipping_tabs_skips_their_scripts(self):
        summary, tabs = self.export(skip=["playback", "subtitles"])
        self.assertEqual(list(tabs), ["Server", "Movies", "TV Shows", "Issues", "Episode gaps"])
        self.assertEqual(sorted(name for name, _ in self.runs), ["gaps", "health", "library"])
        self.assertEqual(summary["skipped_tabs"], ["Playback", "Subtitles"])

    def test_library_report_runs_when_either_tab_needs_it(self):
        self.export(skip=["server"])
        self.assertIn("library", [name for name, _ in self.runs])
        self.assertNotIn("health", [name for name, _ in self.runs])

    def test_library_tab_cant_be_skipped(self):
        with self.assertRaises(SystemExit):
            ex.parse_args(["--skip", "library"])
        self.assertIn("server, issues, gaps, playback, subtitles", self.stderr.getvalue())

    def test_options_passed_to_each_script(self):
        self.export(library=["Movies", "TV Shows"], language=["es"])
        runs = dict(self.runs)
        self.assertEqual(runs["health"], [])
        self.assertEqual(runs["library"], ["--library", "Movies", "--library", "TV Shows"])
        self.assertEqual(runs["gaps"], ["--library", "Movies", "--library", "TV Shows"])
        self.assertEqual(runs["playback"], ["--library", "Movies", "--library", "TV Shows"])
        self.assertEqual(runs["subtitles"], ["--library", "Movies", "--library", "TV Shows", "--language", "es"])

    def test_fixed_options(self):
        self.assertEqual(ex.SOURCES["health"][2], ["--stuck-wait", "0"])
        self.assertEqual(ex.SOURCES["gaps"][2], ["--limit", "500"])
        self.assertEqual(ex.SOURCES["playback"][2], ["--limit", "500", "--days", "0"])
        self.assertEqual(ex.SOURCES["subtitles"][2], ["--limit", "500"])
        self.assertEqual(ex.SOURCES["library"][2], ["--recent", "0", "--growth-months", "0", "--music-examples", "0",
                                                    "--duplicate-examples", "500", "--upgrade-examples", "500"])

    def test_music_library_is_skipped(self):
        summary, tabs = self.export()
        self.assertEqual(summary["skipped_libraries"], [{"name": "Music", "type": "artist"}])
        self.assertEqual({row["Library"] for row in table(tabs["Movies"])}, {"Movies"})
        self.assertEqual({row["Library"] for row in table(tabs["TV Shows"])}, {"TV Shows"})

    def test_library_that_matches_nothing(self):
        with self.assertRaises(ex.ReportError) as caught:
            ex.build(config(), args(library=["Cartoons"]), now=NOW)
        self.assertIn("Movies, TV Shows", str(caught.exception))
        self.assertEqual(self.runs, [])

    def test_music_only_is_refused_before_anything_runs(self):
        with self.assertRaises(ex.ReportError) as caught:
            ex.build(config(), args(library=["music"]), now=NOW)
        self.assertIn("Only movie and TV libraries can be exported", str(caught.exception))
        self.assertEqual(self.runs, [])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "data", "cinemetric")))

    def test_movies_only_skips_episode_gaps(self):
        summary, tabs = self.export(library=["Movies"])
        self.assertNotIn("gaps", [name for name, _ in self.runs])
        self.assertIn("No TV library was included", " ".join(notes(tabs["Episode gaps"])))

    def test_library_that_cant_be_read(self):
        self.server.routes["/library/sections/1/all"] = Reply("broken", status=500)
        summary, tabs = self.export()
        self.assertEqual(table(tabs["Movies"]), [])
        self.assertIn("Note: Movies couldn't be read: the Plex server (/library/sections/1/all) returned HTTP 500.",
                      notes(tabs["Movies"]))
        self.assertEqual({row["Library"] for row in table(tabs["TV Shows"])}, {"TV Shows"})
        self.assertEqual(summary["unavailable"][0]["library"], "Movies")
        self.assertEqual(summary["unavailable"][0]["part"], "listing")
        self.assertEqual([lib["name"] for lib in summary["libraries"]], ["TV Shows"])

    def test_no_library_can_be_read(self):
        self.server.routes["/library/sections/1/all"] = Reply("broken", status=500)
        self.server.routes["/library/sections/2/all"] = Reply("broken", status=500)
        with self.assertRaises(ex.ReportError) as caught:
            ex.build(config(), args(), now=NOW)
        self.assertIn("nothing was saved", str(caught.exception))
        folder = os.path.join(self.tmp, "data", "cinemetric")
        self.assertFalse(os.path.exists(folder) and os.listdir(folder))

    def test_a_report_that_fails(self):
        self.failures["playback"] = "playback-check failed"
        summary, tabs = self.export()
        self.assertIn("Note: This tab couldn't be built: playback-check failed", notes(tabs["Playback"]))
        entry = next(t for t in summary["tabs"] if t["name"] == "Playback")
        self.assertEqual(entry, {"name": "Playback", "rows": 0, "problem": "playback-check failed"})
        self.assertGreater(len(table(tabs["Movies"])), 0)

    def test_not_configured(self):
        with self.assertRaises(ex.ReportError) as caught:
            ex.build({"plex": None, "tautulli": None, "tautulli_problem": None}, args(), now=NOW)
        self.assertTrue(str(caught.exception).startswith("NOT_CONFIGURED"))
        self.assertEqual(self.runs, [])


class RunSource(OfflineTestCase):
    def run_with(self, returncode=0, stdout="", stderr=""):
        done = subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)
        with mock.patch.object(ex.subprocess, "run", return_value=done) as run:
            result = ex.run_source("playback", ["--library", "Movies"])
        return result, run

    def test_reads_json_and_passes_options(self):
        result, run = self.run_with(stdout='{"libraries": []}')
        self.assertEqual(result, ("playback", {"libraries": []}, None))
        command = run.call_args[0][0]
        self.assertEqual(command[2:], ["--limit", "500", "--days", "0", "--library", "Movies"])
        self.assertTrue(command[1].endswith(os.path.join("playback-check", "scripts", "playback_check.py")))

    def test_error_line_without_its_code(self):
        result, _ = self.run_with(1, stderr="warning: x\nerror: NOT_CONFIGURED: not connected\n")
        self.assertEqual(result[2], "not connected")

    def test_owner_only_is_explained(self):
        result, _ = self.run_with(1, stderr="error: OWNER_ONLY: history needs the owner\n")
        self.assertEqual(result[2], ex.OWNER_ONLY_TEXT)

    def test_output_that_isnt_a_json_object(self):
        for stdout in ("not json", "[1, 2]"):
            with self.subTest(stdout=stdout):
                result, _ = self.run_with(stdout=stdout)
                self.assertEqual(result[2], "playback-check produced unreadable output")

    def test_timeout(self):
        with mock.patch.object(ex.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 1)):
            self.assertEqual(ex.run_source("gaps", [])[2], "episode-gaps took longer than 30 minutes")


# ---------------------------------------------------------------- the Library tab

class LibraryRows(Base):
    def test_columns(self):
        _, tabs = self.export()
        self.assertEqual(tuple(tabs["Movies"][0]), ex.MOVIE_COLUMNS)
        self.assertEqual(tuple(tabs["TV Shows"][0]), ex.SHOW_COLUMNS)
        self.assertNotIn("Season", ex.MOVIE_COLUMNS)
        self.assertNotIn("Length (min)", ex.SHOW_COLUMNS)

    def test_episode_columns(self):
        _, tabs = self.export(tv="episodes")
        self.assertEqual(tuple(tabs["TV Shows"][0]), ex.EPISODE_COLUMNS)
        self.assertEqual(tuple(tabs["Movies"][0]), ex.MOVIE_COLUMNS)

    def test_only_tabs_for_the_kinds_included(self):
        _, tabs = self.export(library=["TV Shows"])
        self.assertNotIn("Movies", tabs)
        _, tabs = self.export(library=["Movies"])
        self.assertNotIn("TV Shows", tabs)

    def test_order_and_types(self):
        rows = self.library_rows()
        self.assertEqual([(r["Tab"], r["Title"]) for r in rows], [
            ("Movies", "</t></is></c><c><f>1+1</f>"),
            ("Movies", "=HYPERLINK(\"http://example.invalid\",\"Click\")"),
            ("Movies", "Amélie & <Friends>, \"quoted\""),
            ("Movies", "Night of the Test"),
            ("Movies", "-30-"),  # sorted by its sort title, "Thirty"
            ("TV Shows", "Another Show"),
            ("TV Shows", "Test Show"),
        ])

    def test_episode_rows(self):
        rows = [r for r in self.library_rows(tv="episodes") if r["Tab"] == "TV Shows"]
        self.assertEqual(len(rows), 15)
        another = [(r["Season"], r["Episode"], r["Title"]) for r in rows if r["Show"] == "Another Show"]
        self.assertEqual(another, [(1, 1, "First"), (1, 2, "Second"), (1, None, "Unnumbered Special")])
        self.assertEqual(rows[0]["Show"], "Another Show")

    def test_movie_with_two_versions(self):
        row = self.by_title(self.library_rows())["Night of the Test"]
        self.assertEqual((row["Resolution"], row["Size (GB)"], row["Versions"]), ("4K", 58.0, 2))
        self.assertEqual((row["Video codec"], row["Audio codec"], row["Audio channels"]), ("hevc", "truehd", 8))
        self.assertEqual(row["Container"], "mkv")
        self.assertEqual(row["Length (min)"], 100)
        self.assertEqual(row["Year"], 1987)
        self.assertEqual(row["Added"], datetime.date.fromtimestamp(1760000000))
        self.assertEqual(row["Last watched"], datetime.date.fromtimestamp(1760000000 + 86400))
        self.assertEqual((row["Watched"], row["Content rating"], row["Unavailable"]), ("Yes", "R", "No"))

    def test_movie_whose_file_is_gone(self):
        row = self.by_title(self.library_rows())["=HYPERLINK(\"http://example.invalid\",\"Click\")"]
        self.assertEqual((row["Unavailable"], row["Size (GB)"], row["Versions"]), ("Yes", 0, 0))
        self.assertIsNone(row["Resolution"])
        self.assertIsNone(row["Video codec"])

    def test_year_from_release_date(self):
        row = self.by_title(self.library_rows())["Amélie & <Friends>, \"quoted\""]
        self.assertEqual(row["Year"], 1999)

    def test_watched_states(self):
        rows = self.by_title(self.library_rows())
        self.assertEqual(rows["=HYPERLINK(\"http://example.invalid\",\"Click\")"]["Watched"], "Partly")
        self.assertEqual(rows["-30-"]["Watched"], "No")
        self.assertEqual((rows["Test Show"]["Watched"], rows["Test Show"]["Episodes watched"]), ("Partly", 5))
        self.assertEqual(rows["Another Show"]["Watched"], "Yes")

    def test_show_summary(self):
        row = self.by_title(self.library_rows())["Test Show"]
        self.assertEqual((row["Resolution"], row["Episodes"], row["Episodes unavailable"]), ("1080p", 12, 1))
        self.assertEqual(row["Size (GB)"], 10.5)
        self.assertNotIn("Versions", row)

    def test_most_common_ties(self):
        self.assertEqual(ex.most_common(["720p", "1080p"], lambda r: ex.RESOLUTION_RANK.get(r, 0)), "1080p")
        self.assertEqual(ex.most_common(["mkv", "avi", "mkv", "avi"]), "avi")
        self.assertIsNone(ex.most_common([None, ""]))


class Collections(Base):
    def test_movie_in_two_collections(self):
        rows = self.by_title(self.library_rows())
        self.assertEqual(rows["Night of the Test"]["Collections"], "Award Winners; Test Trilogy")

    def test_collection_names_are_sorted_ignoring_case_and_spaces_kept(self):
        rows = self.by_title(self.library_rows())
        self.assertEqual(rows["-30-"]["Collections"], "+Extras; Award Winners")

    def test_show_through_a_season(self):
        rows = self.by_title(self.library_rows())
        self.assertEqual(rows["Test Show"]["Collections"], "Holiday Specials")
        self.assertIsNone(rows["Another Show"]["Collections"])

    def test_episodes_through_their_season(self):
        rows = [r for r in self.library_rows(tv="episodes") if r.get("Show") == "Test Show"]
        held = {(r["Season"], r["Collections"]) for r in rows}
        self.assertEqual(held, {(1, None), (2, "Holiday Specials")})

    def test_episode_through_its_show(self):
        self.data["children"]["911"] = [{"ratingKey": "201", "type": "show"}]
        self.rebuild()
        rows = [r for r in self.library_rows(tv="episodes") if r.get("Show") == "Test Show"]
        self.assertEqual({r["Collections"] for r in rows}, {"Holiday Specials"})

    def test_collection_list_cant_be_read(self):
        self.server.routes["/library/sections/1/collections"] = Reply("broken", status=500)
        summary, tabs = self.export()
        movies = table(tabs["Movies"])
        self.assertEqual(len(movies), 5)
        self.assertEqual({r["Collections"] for r in movies}, {None})
        self.assertIn({"library": "Movies", "part": "collections"},
                      [{k: u[k] for k in ("library", "part")} for u in summary["unavailable"]])

    def test_collection_contents_cant_be_read(self):
        self.server.routes["/library/collections/901/children"] = Reply("broken", status=500)
        summary, tabs = self.export()
        rows = self.by_title(table(tabs["Movies"]))
        self.assertEqual(rows["Night of the Test"]["Collections"], "Award Winners")
        entry = next(u for u in summary["unavailable"] if u["part"] == "collection contents")
        self.assertEqual((entry["library"], entry["collections"]), ("Movies", 1))
        self.assertNotIn("Test Trilogy", json.dumps(summary))


# ---------------------------------------------------------------- tabs from reports

class ServerTab(Base):
    def items(self, rows):
        return {row[0]: (row[1] if len(row) > 1 else None) for row in rows if row}

    def test_sections_and_values(self):
        _, tabs = self.export()
        items = self.items(tabs["Server"])
        self.assertEqual(items["Name"], "Test Server")
        self.assertEqual(items["Update available"], "Yes (1.41.0.0000-test)")
        self.assertEqual(items["Remote access"], "Working")
        self.assertEqual(items["Hardware-accelerated transcoding"], "Off")
        self.assertEqual(items["Video transcoding"], "On")
        self.assertEqual(items["Remote limit per stream (kbps, 0 means no limit)"], 4000)
        self.assertEqual(items["Watched status"], ex.WATCHED_NOTE)

    def test_worth_a_look(self):
        _, tabs = self.export()
        items = self.items(tabs["Server"])
        self.assertEqual(items["A Plex update is available"], "1.41.0.0000-test")
        self.assertEqual(items["The remote streaming limit is low"], "4000 kbps")
        self.assertFalse(any("slower than real time" in str(k) for k in items))
        self.assertIn("Hardware-accelerated transcoding is off", items)

    def test_nothing_that_changes_moment_to_moment(self):
        _, tabs = self.export()
        text = json.dumps(tabs, default=str)
        for gone in ("Resources", "CPU", "Memory", "91.2", "95.5", "Scanning Movies", "stuck"):
            self.assertNotIn(gone, text)
        items = self.items(tabs["Server"])
        self.assertEqual([k for k in items if k and k in ex.WORTH_A_LOOK.values()],
                         ["A Plex update is available", "The remote streaming limit is low",
                          "Hardware-accelerated transcoding is off"])

    def test_nothing_about_streams_now(self):
        _, tabs = self.export()
        text = json.dumps(tabs, default=str)
        for secret in ("alex-test", "Alex's iPhone", "Secret Stream Title", "Streams right now", "0.8x"):
            self.assertNotIn(secret, text)
        items = self.items(tabs["Server"])
        for gone in ("Streams", "Direct play", "Direct stream", "Transcode", "Bandwidth (kbps)"):
            self.assertNotIn(gone, items)

    def test_unavailable_part(self):
        _, tabs = self.export()
        self.assertEqual(self.items(tabs["Server"])["Stuck task check"], ex.OWNER_ONLY_TEXT)

    def test_libraries_table(self):
        _, tabs = self.export()
        rows = tabs["Server"]
        start = rows.index(list(ex.LIBRARY_TABLE_COLUMNS))
        libraries = rows[start + 1:]
        self.assertEqual(libraries[0], ["Movies", "Movies", 5, 6, 67.0, datetime.date(2026, 10, 1)])
        self.assertEqual(libraries[2][:5], ["Music", "Music", 3, 40, 1.2])

    def test_health_fails(self):
        self.failures["health"] = "Could not reach the Plex server"
        summary, tabs = self.export()
        self.assertIn("Note: Server details couldn't be read: Could not reach the Plex server",
                      [row[0] for row in tabs["Server"] if row])
        self.assertEqual(self.items(tabs["Server"])["Name"], "Test Server")
        self.assertEqual(summary["tabs"][0]["problem"], "Could not reach the Plex server")


class IssuesTab(Base):
    def rows(self):
        return table(self.export()[1]["Issues"])

    def test_issue_kinds_in_order(self):
        kinds = [r["Issue"] for r in self.rows()]
        self.assertEqual(kinds, sorted(kinds, key=ex.ISSUE_ORDER.index))
        self.assertEqual(set(kinds), set(ex.ISSUE_ORDER))

    def test_from_the_listings(self):
        rows = self.rows()
        missing = [(r["Title"], r["Show"], r["Season"], r["Episode"]) for r in rows if r["Issue"] == "File missing"]
        self.assertEqual(missing, [("=HYPERLINK(\"http://example.invalid\",\"Click\")", None, None, None),
                                   ("Holiday 2", "Test Show", 2, 2)])
        self.assertEqual([r["Title"] for r in rows if r["Issue"] == "Unmatched"],
                         ["=HYPERLINK(\"http://example.invalid\",\"Click\")"])
        self.assertEqual([r["Title"] for r in rows if r["Issue"] == "No poster"],
                         ["=HYPERLINK(\"http://example.invalid\",\"Click\")"])

    def test_every_missing_file_is_listed(self):
        for episode in self.data["listings"]["2"]["4"]:
            for media in episode["Media"]:
                media["deletedAt"] = 1
        self.rebuild()
        rows = [r for r in self.rows() if r["Issue"] == "File missing" and r["Show"]]
        self.assertEqual(len(rows), 15)

    def test_from_library_report(self):
        rows = self.rows()
        dup = next(r for r in rows if r["Issue"] == "Duplicate copies")
        self.assertEqual((dup["Title"], dup["Year"], dup["Size (GB)"]), ("Night of the Test", 1987, 8.0))
        self.assertEqual(dup["Details"], "4K hevc 50.0 GB; 1080p h264 8.0 GB")
        cross = next(r for r in rows if r["Issue"] == "In more than one library")
        self.assertEqual(cross["Library"], "Movies; Kids Movies")
        self.assertEqual(cross["Details"], "Movies: 4K 50.0 GB; Kids Movies: 1080p 8.0 GB")
        low = [r for r in rows if r["Issue"] == "Low resolution"]
        self.assertEqual([(r["Title"], r["Year"], r["Details"]) for r in low],
                         [("-30-", 1950, "SD, mpeg4"), ("Test Show", None, "2 episodes: 2 720p")])

    def test_notes_for_examples_left_out(self):
        texts = notes(self.export()[1]["Issues"])
        self.assertIn("Note: 2 more titles with duplicate copies in Movies weren't listed.", texts)
        self.assertIn("Note: 1 more low-resolution titles in Movies weren't listed.", texts)
        self.assertFalse(any("TV Shows" in t for t in texts))

    def test_library_report_fails(self):
        self.failures["library"] = "library-report failed"
        summary, tabs = self.export()
        rows = table(tabs["Issues"])
        self.assertEqual({r["Issue"] for r in rows}, {"File missing", "Unmatched", "No poster"})
        self.assertIn("library-report failed", " ".join(notes(tabs["Issues"])))
        self.assertEqual(next(t for t in summary["tabs"] if t["name"] == "Issues")["problem"], "library-report failed")


class GapsTab(Base):
    def test_rows(self):
        rows = table(self.export()[1]["Episode gaps"])
        self.assertEqual([(r["Season"], r["Missing episodes"], r["Missing count"], r["Unavailable episodes"], r["Note"])
                          for r in rows], [
            (2, None, None, None, "Starts at season 2; Numbering carries on from the previous season"),
            (3, "3, 5-7", 4, "9", None),
            (4, "Whole season", None, None, None),
        ])

    def test_notes(self):
        texts = notes(self.export()[1]["Episode gaps"])
        self.assertEqual(texts, ["Note: 2 more shows with gaps in TV Shows weren't listed.",
                                 "Note: Only gaps between the episodes on the server can be found."])

    def test_nothing_found(self):
        self.reports["gaps"]["libraries"][0].update(listed=[], more_shows=0)
        self.assertIn("Note: No gaps were found.", notes(self.export()[1]["Episode gaps"]))


class PlaybackTab(Base):
    def test_rows(self):
        rows = table(self.export()[1]["Playback"])
        movie, show = rows
        self.assertEqual((movie["Resolution"], movie["Size (GB)"], movie["Bitrate (kbps)"]), ("4K", 50.0, 40000))
        self.assertEqual([movie[c] for c in ("Image subtitles", "TrueHD audio", "DTS audio", "Over bitrate limit")],
                         [1, 1, None, 1])
        self.assertEqual(movie["Details"], "Image subtitles: en, fr; Audio: truehd (no common alternative track)")
        self.assertEqual((show["Episodes"], show["Episodes flagged"], show["DTS audio"]), (30, 12, 12))

    def test_notes(self):
        texts = notes(self.export()[1]["Playback"])
        self.assertEqual(texts, [
            "Note: Files were checked against a remote bitrate limit of 4000 kbps.",
            "Note: 3 more titles in Movies weren't listed.",
            "Note: These are likely causes on common devices, not a promise.",
        ])


class SubtitlesTab(Base):
    def test_rows(self):
        rows = table(self.export()[1]["Subtitles"])
        movie, show = rows
        self.assertEqual(movie["Finding"], "Audio in another language, no English subtitles")
        self.assertEqual((movie["Audio languages"], movie["Subtitle languages"], movie["Forced subtitles"]),
                         ("Japanese, Unknown", "Spanish", "English"))
        self.assertEqual(movie["Resolution"], "1080p")
        self.assertEqual(show["Which episodes"], "S1 E2-3, E7; Bonus (2016-01-02)")
        self.assertEqual((show["Audio languages"], show["Episodes"], show["Episodes flagged"]), ("Spanish", 20, 3))

    def test_notes(self):
        texts = notes(self.export()[1]["Subtitles"])
        self.assertEqual(texts, ["Note: 4 more titles in Movies under \"No English subtitles\" weren't listed.",
                                 "Note: This goes by the language labels on each track."])

    def test_language_problem(self):
        self.reports["subtitles"]["libraries"][1]["language_problem"] = "This library has no language set."
        self.assertIn("Note: TV Shows: This library has no language set.", notes(self.export()[1]["Subtitles"]))


# ---------------------------------------------------------------- the workbook file

class WorkbookFormat(Base):
    def test_valid_parts_listed_in_content_types(self):
        summary, _ = self.export()
        with zipfile.ZipFile(summary["output"]) as archive:
            parts = archive.namelist()
            for part in parts:
                ElementTree.fromstring(archive.read(part))
            types = archive.read("[Content_Types].xml").decode()
        for part in parts:
            if part.endswith(".xml") and part != "[Content_Types].xml":
                self.assertTrue(f'PartName="/{part}"' in types or 'Extension="xml"' in types, part)
        for i in range(1, 8):
            self.assertIn(f'PartName="/xl/worksheets/sheet{i}.xml"', types)

    def test_nothing_that_can_run_or_link(self):
        summary, _ = self.export()
        with zipfile.ZipFile(summary["output"]) as archive:
            names = archive.namelist()
            self.assertEqual(sorted(names), sorted(
                ["[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
                 "xl/styles.xml"] + [f"xl/worksheets/sheet{i}.xml" for i in range(1, 8)]))
            for name in names:
                xml = archive.read(name).decode()
                self.assertNotIn("<f>", xml)
                self.assertNotIn("<f ", xml)
                self.assertNotIn("<hyperlink", xml)
                self.assertNotIn("relationships/hyperlink", xml)
                self.assertNotIn("externalLink", xml)
                self.assertNotIn("vbaProject", xml)

    def test_text_numbers_and_dates(self):
        summary, _ = self.export()
        with zipfile.ZipFile(summary["output"]) as archive:
            sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet2.xml"))
        cells = list(sheet.iter(f"{{{NS['m']}}}c"))
        texts = [c for c in cells if c.get("t") == "inlineStr"]
        others = [c for c in cells if c.get("t") is None]
        self.assertTrue(texts and others)
        self.assertEqual({c.get("t") for c in cells}, {"inlineStr", None})
        self.assertTrue(any(c.get("s") == str(ex.DATE_STYLE) for c in others))

    def test_header_kept_in_view_with_filters(self):
        summary, _ = self.export()
        with zipfile.ZipFile(summary["output"]) as archive:
            library = archive.read("xl/worksheets/sheet2.xml").decode()
            server = archive.read("xl/worksheets/sheet1.xml").decode()
        self.assertIn('state="frozen"', library)
        self.assertIn("<autoFilter ref=\"A1:Q", library)
        self.assertNotIn("autoFilter", server)

    def test_a_title_made_to_be_a_formula_is_text(self):
        rows = self.by_title(self.library_rows())
        self.assertIn("=HYPERLINK(\"http://example.invalid\",\"Click\")", rows)
        self.assertIn("</t></is></c><c><f>1+1</f>", rows)

    def test_characters_not_allowed_in_xml_are_removed(self):
        self.data["listings"]["1"]["1"][0]["title"] = "Bad￾Title\ud800"
        self.rebuild()
        self.assertIn("BadTitle", self.by_title(self.library_rows()))

    def test_control_characters_and_long_titles(self):
        self.data["listings"]["1"]["1"][0]["title"] = "Line\none" + "x" * 200
        self.rebuild()
        titles = [r["Title"] for r in self.library_rows()]
        self.assertIn(("Line one" + "x" * 200)[:120], titles)

    def test_notes_are_not_cut(self):
        long = "A limits sentence. " * 20
        self.reports["gaps"]["limits"] = long
        self.assertIn("Note: " + long.strip(), notes(self.export()[1]["Episode gaps"]))


# ---------------------------------------------------------------- where the file goes

class Saving(Base):
    def data_folder(self):
        return os.path.join(self.tmp, "data", "cinemetric")

    def test_default_place_and_permissions(self):
        summary, _ = self.export()
        self.assertEqual(summary["output"], os.path.join(self.data_folder(), f"plex-export-{TODAY}.xlsx"))
        self.assertTrue(summary["in_data_folder"])
        self.assertEqual(os.stat(self.data_folder()).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(summary["output"]).st_mode & 0o777, 0o600)

    def test_running_twice_the_same_day(self):
        first, _ = self.export()
        second, _ = self.export()
        self.assertFalse(first["replaced"])
        self.assertTrue(second["replaced"])
        self.assertEqual([f for f in os.listdir(self.data_folder()) if f.endswith(".xlsx")],
                         [f"plex-export-{TODAY}.xlsx"])

    def test_file_names(self):
        today = datetime.date(2026, 10, 9)
        self.assertEqual(ex.default_name(["TV Shows"], "episodes", today),
                         "plex-export-tv-shows-episodes-2026-10-09.xlsx")
        self.assertEqual(ex.default_name(["../Kids/Movies"], "shows", today), "plex-export-kids-movies-2026-10-09.xlsx")
        self.assertEqual(ex.default_name(["!!!"], "shows", today), "plex-export-library-2026-10-09.xlsx")
        self.assertEqual(len(ex.library_slug(["a" * 100])), 60)

    def test_library_name_with_slashes_stays_in_the_data_folder(self):
        self.data["/library/sections"]["MediaContainer"]["Directory"][0]["title"] = "../Kids/Movies"
        self.rebuild()
        summary, _ = self.export(library=["../Kids/Movies"])
        self.assertEqual(summary["output"], os.path.join(self.data_folder(), f"plex-export-kids-movies-{TODAY}.xlsx"))

    def test_folder_the_user_names_keeps_its_permissions(self):
        folder = os.path.join(self.tmp, "Documents")
        os.mkdir(folder)
        os.chmod(folder, 0o755)
        summary, _ = self.export(output=folder)
        self.assertEqual(summary["output"], os.path.join(folder, f"plex-export-{TODAY}.xlsx"))
        self.assertFalse(summary["in_data_folder"])
        self.assertEqual(os.stat(folder).st_mode & 0o777, 0o755)
        self.assertEqual(os.stat(summary["output"]).st_mode & 0o777, 0o600)
        self.assertFalse(os.path.exists(self.data_folder()))

    def test_tilde_is_expanded(self):
        os.mkdir(os.path.join(self.tmp, "Documents"))
        summary, _ = self.export(output="~/Documents/plex.xlsx")
        self.assertEqual(summary["output"], os.path.join(self.tmp, "Documents", "plex.xlsx"))

    def test_file_exists_stops_before_plex(self):
        path = os.path.join(self.tmp, "plex.xlsx")
        with open(path, "w") as fh:
            fh.write("keep me")
        with self.assertRaises(ex.ReportError) as caught:
            ex.build(config(), args(output=path), now=NOW)
        self.assertTrue(str(caught.exception).startswith("FILE_EXISTS"))
        self.assertEqual(self.server.requests, [])
        self.assertEqual(self.runs, [])
        with open(path) as fh:
            self.assertEqual(fh.read(), "keep me")

    def test_replace(self):
        path = os.path.join(self.tmp, "plex.xlsx")
        with open(path, "w") as fh:
            fh.write("old")
        summary, tabs = self.export(output=path, replace=True)
        self.assertTrue(summary["replaced"])
        self.assertIn("Movies", tabs)

    def test_file_that_appears_while_exporting_is_kept(self):
        path = os.path.join(self.tmp, "plex.xlsx")
        real = ex.workbook_bytes

        def sneaky(sheets):
            with open(path, "w") as fh:
                fh.write("arrived meanwhile")
            return real(sheets)
        with mock.patch.object(ex, "workbook_bytes", sneaky):
            with self.assertRaises(ex.ReportError) as caught:
                ex.build(config(), args(output=path), now=NOW)
        self.assertTrue(str(caught.exception).startswith("FILE_EXISTS"))
        with open(path) as fh:
            self.assertEqual(fh.read(), "arrived meanwhile")
        self.assertEqual([f for f in os.listdir(self.tmp) if f.startswith(".cinemetric-")], [])

    def test_bad_output(self):
        for output in (os.path.join(self.tmp, "plex.csv"), os.path.join(self.tmp, "no-such-folder", "plex.xlsx")):
            with self.subTest(output=output):
                with self.assertRaises(ex.ReportError) as caught:
                    ex.build(config(), args(output=output), now=NOW)
                self.assertTrue(str(caught.exception).startswith("BAD_OUTPUT"))
        self.assertEqual(self.server.requests, [])

    def test_no_partial_file_on_failure(self):
        with mock.patch.object(ex.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                ex.build(config(), args(), now=NOW)
        self.assertEqual(os.listdir(self.data_folder()), [])


# ---------------------------------------------------------------- the summary

class Summary(Base):
    def test_totals(self):
        summary, _ = self.export()
        self.assertEqual(summary["libraries"], [{"name": "Movies", "kind": "movie", "rows": 5},
                                                {"name": "TV Shows", "kind": "show", "rows": 2}])
        self.assertEqual([(t["name"], t["rows"]) for t in summary["tabs"][1:3]], [("Movies", 5), ("TV Shows", 2)])
        self.assertEqual(summary["tv_rows"], "shows")
        self.assertEqual(summary["watched_note"], ex.WATCHED_NOTE)
        self.assertEqual(summary["size_bytes"], os.path.getsize(summary["output"]))
        self.assertEqual(summary["server"], {"name": "Test Server", "version": "1.40.0.0000-test"})

    def test_no_titles_in_the_summary(self):
        summary, _ = self.export(tv="episodes")
        text = json.dumps(summary)
        for title in ("Night of the Test", "Test Show", "Pilot Part", "Award Winners", "Holiday Specials", "HYPERLINK"):
            self.assertNotIn(title, text)

    def test_no_history_or_accounts_requested(self):
        self.export()
        paths = {seen.path for seen in self.server.requests}
        self.assertFalse(any("history" in p or "accounts" in p for p in paths))
        self.assertTrue(all(any(rule.match(p) for rule in ex.ALLOWED_PATHS) for p in paths))
        self.assertTrue(all(seen.method == "GET" for seen in self.server.requests))

    def test_media_deletion(self):
        def build(answer):
            self.server.routes["/:/prefs"] = answer
            self.server.requests.clear()
            summary = ex.build(config(), args(skip=list(ex.SKIPPABLE)), now=NOW)
            return summary, self.server.requests
        check_media_deletion(self, build)

    def test_check(self):
        result = ex.check(config())
        self.assertEqual(result["plex"]["server"], "Test Server")
        self.assertEqual([seen.path for seen in self.server.requests], ["/"])
        self.assertEqual(self.runs, [])
