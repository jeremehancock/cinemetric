"""show-progress (openspec/specs/show-progress/spec.md)."""

import calendar
import inspect
import json
from unittest import mock

from helpers import (FAKE_API_KEY, FAKE_TOKEN, FakeServer, OfflineTestCase, Reply, Unreachable, check_media_deletion,
                     fixture, load_script)

sp = load_script("show-progress")
wa = load_script("watch-activity")

# Kept before any test patches it, so fake servers built one after another don't stack up.
REAL_OPENER = sp.build_opener

PLEX = ("http://192.0.2.10:32400", FAKE_TOKEN, True)
TAUTULLI = ("http://192.0.2.10:8181", FAKE_API_KEY, True)
# Every date in the fixtures is worked out against this moment.
NOW = calendar.timegm((2026, 6, 15, 12, 0, 0))


def args(*argv):
    return sp.parse_args(list(argv))


def config(plex=PLEX, tautulli=TAUTULLI, problem=None):
    return {"plex": plex, "tautulli": tautulli, "tautulli_problem": problem}


# ---------------------------------------------------------------- fake servers

def paged(items, seen):
    start = int(seen.headers.get("x-plex-container-start", 0))
    size = int(seen.headers.get("x-plex-container-size", len(items)))
    return {"MediaContainer": {"Metadata": items[start:start + size], "totalSize": len(items)}}


def listing(data, seen):
    section = seen.path.split("/")[3]
    keys = {s["ratingKey"] for s in data["shows"] if s["librarySectionID"] == section}
    if seen.query["type"] == "2":
        return paged([s for s in data["shows"] if s["ratingKey"] in keys], seen)
    return paged([e for e in data["episodes"] if e["grandparentRatingKey"] in keys], seen)


def plex_entries(rows):
    """Plex's history for the same plays: finished ones only, plus a movie and a song it can't
    filter out."""
    entries = [{"type": "movie", "ratingKey": "300", "accountID": 11, "viewedAt": NOW - 86400},
               {"type": "track", "ratingKey": "400", "accountID": 12, "viewedAt": NOW - 2 * 86400}]
    for row in rows:
        if row["watched_status"] < 1 or row["live"]:
            continue
        entries.append({"type": "episode", "accountID": row["user_id"],
                        "grandparentKey": f"/library/metadata/{row['grandparent_rating_key']}",
                        "parentIndex": row["parent_media_index"], "index": row["media_index"],
                        "ratingKey": str(row["rating_key"]), "title": "An Episode", "viewedAt": row["stopped"]})
    return sorted(entries, key=lambda e: -e["viewedAt"])


def plex_history(rows, honor_filter=True):
    entries = plex_entries(rows)

    def answer(seen):
        found = entries
        key = seen.query.get("metadataItemID")
        if honor_filter and key:
            found = [e for e in entries if e.get("grandparentKey", "").endswith("/" + key)]
        if seen.query.get("sort") == "viewedAt:asc":
            found = found[::-1]
        return paged(found, seen)
    return answer


def tautulli_route(rows, calls=None, users=None):
    def answer(seen):
        cmd = seen.query["cmd"]
        if calls is not None:
            calls.append(dict(seen.query))
        if cmd == "get_tautulli_info":
            result = {"tautulli_version": "v2.18.2"}
        elif cmd == "get_users":
            result = users if users is not None else fixture("show-progress", "tautulli.json")["get_users"]
        else:
            found = [r for r in rows if r["media_type"] == seen.query.get("media_type", r["media_type"])]
            if "user_id" in seen.query:
                found = [r for r in found if str(r["user_id"]) == seen.query["user_id"]]
            if "grandparent_rating_key" in seen.query:
                found = [r for r in found if str(r["grandparent_rating_key"]) == seen.query["grandparent_rating_key"]]
            if seen.query.get("order_dir") == "asc":
                found = found[::-1]
            start, length = int(seen.query["start"]), int(seen.query["length"])
            result = {"data": found[start:start + length], "recordsFiltered": len(found)}
        return {"response": {"result": "success", "message": None, "data": result}}
    return answer


class Network(FakeServer):
    """One FakeServer for every client the script builds."""

    def __init__(self, test, routes):
        super().__init__(routes)
        patcher = mock.patch.object(sp, "build_opener", lambda url, verify: self.attach(REAL_OPENER(url, verify)))
        patcher.start()
        test.addCleanup(patcher.stop)


class Base(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.plex = fixture("show-progress", "plex.json")
        self.rows = fixture("show-progress", "tautulli.json")["get_history"]

    def network(self, tautulli=True, history=None, prefs=None, calls=None, honor_filter=True, users=None):
        routes = {
            "/": self.plex["/"],
            "/library/sections": self.plex["/library/sections"],
            "/accounts": {"MediaContainer": {"Account": self.plex["accounts"]}},
            "/status/sessions/history/all": history or plex_history(self.rows, honor_filter),
            "/:/prefs": prefs or {"MediaContainer": {"Setting": []}},
        }
        for section in ("1", "2", "3", "4"):
            routes[f"/library/sections/{section}/all"] = lambda seen: listing(self.plex, seen)
        if tautulli:
            routes["/api/v2"] = tautulli_route(self.rows, calls, users) if tautulli is True else tautulli
        return Network(self, routes)

    def report(self, *argv, cfg=None, now=NOW):
        return sp.build_report(cfg or config(), args(*argv), now=now)

    def show(self, report, title):
        [found] = [s for s in report["shows"] if s["title"] == title]
        return found

    def person(self, report, title, name):
        [found] = [p for p in self.show(report, title)["people"] if p["name"] == name]
        return found


# ---------------------------------------------------------------- sources

class Sources(Base):
    def test_only_allowed_paths_and_commands(self):
        for source in ("tautulli", "plex"):
            with self.subTest(source=source):
                server = self.network()
                self.report("--source", source, "--user", "sam tester")
                paths = {s.path for s in server.requests if not s.path.startswith("/api/")}
                self.assertTrue(paths <= {"/", "/library/sections", "/library/sections/1/all",
                                          "/library/sections/2/all", "/status/sessions/history/all",
                                          "/accounts", "/:/prefs"}, paths)
                self.assertTrue(all(s.method == "GET" for s in server.requests))
                commands = {s.query["cmd"] for s in server.requests if s.path == "/api/v2"}
                self.assertTrue(commands <= {"get_tautulli_info", "get_history", "get_users"})

    def test_allowlist(self):
        self.assertEqual(len(sp.ALLOWED_PATHS), 6)
        for path in ("/library/metadata/1", "/library/metadata/1/allLeaves", "/status/sessions",
                     "/library/sections/1/refresh"):
            with self.subTest(path=path):
                self.assertFalse(any(rule.match(path) for rule in sp.ALLOWED_PATHS))
        self.assertEqual(sp.TAUTULLI_COMMANDS, {"get_tautulli_info", "get_history", "get_users"})

    def test_get_users_only_for_user(self):
        calls = []
        self.network(calls=calls)
        self.report()
        self.assertNotIn("get_users", [c["cmd"] for c in calls])

    def test_tautulli_asks_for_episodes_grouped(self):
        calls = []
        self.network(calls=calls)
        self.report()
        history = [c for c in calls if c["cmd"] == "get_history"]
        self.assertTrue(history)
        for call in history:
            self.assertEqual(call["media_type"], "episode")
            self.assertEqual(call["grouping"], "1")

    def test_media_deletion_setting(self):
        def build(answer):
            server = self.network(prefs=answer)
            return self.report(), server.requests
        check_media_deletion(self, build)

    def test_needs_plex(self):
        with self.assertRaises(sp.ReportError) as caught:
            self.report(cfg=config(plex=None))
        self.assertIn("NOT_CONFIGURED", str(caught.exception))


class ChoosingASource(Base):
    def test_tautulli_when_set_up(self):
        self.network()
        report = self.report()
        self.assertEqual(report["source"], "tautulli")
        self.assertIsNone(report["fallback_reason"])
        self.assertNotIn("plex_history_note", report)

    def test_plex_when_tautulli_is_not_set_up(self):
        self.network(tautulli=False)
        report = self.report(cfg=config(tautulli=None))
        self.assertEqual(report["source"], "plex")
        self.assertEqual(report["fallback_reason"], "Tautulli is not set up")
        self.assertIn("finished", report["plex_history_note"])

    def test_tautulli_down_falls_back_to_plex(self):
        self.network(tautulli=Unreachable("connection refused"))
        report = self.report()
        self.assertEqual(report["source"], "plex")
        self.assertIn("Tautulli is configured but failed", report["fallback_reason"])
        self.assertIn("plex_history_note", report)

    def test_nothing_from_a_failed_tautulli_read_is_kept(self):
        def half_then_fail(seen):
            if seen.query["cmd"] == "get_history" and seen.query["start"] != "0":
                return Reply("", status=500)
            return tautulli_route(self.rows)(seen)
        self.network(tautulli=half_then_fail)
        with mock.patch.object(sp, "TAUTULLI_PAGE_SIZE", 10):
            report = self.report()
        self.assertEqual(report["source"], "plex")
        # Alex's unfinished play of an episode the server lacks is only in Tautulli's history.
        self.assertEqual(self.show(report, "Night Garden")["unmatched_plays"], 0)

    def test_source_tautulli_failing_stops_the_report(self):
        self.network(tautulli=Unreachable("connection refused"))
        with self.assertRaises(sp.ReportError):
            self.report("--source", "tautulli")

    def test_source_tautulli_not_set_up(self):
        self.network(tautulli=False)
        with self.assertRaises(sp.ReportError) as caught:
            self.report("--source", "tautulli", cfg=config(tautulli=None))
        self.assertIn("TAUTULLI_NOT_CONFIGURED", str(caught.exception))

    def test_tautulli_settings_unreadable(self):
        self.network(tautulli=False)
        report = self.report(cfg=config(tautulli=None, problem="Could not read config.json"))
        self.assertEqual(report["source"], "plex")
        self.assertIn("couldn't be read", report["fallback_reason"])

    def test_source_choice_copied_from_watch_activity(self):
        self.assertEqual(inspect.getsource(sp.pick_person), inspect.getsource(wa.pick_person))
        self.assertEqual(inspect.getsource(sp.tautulli_person), inspect.getsource(wa.tautulli_person))


class OwnerOnly(Base):
    def test_history_refused(self):
        self.network(tautulli=False, history=Reply("", status=403))
        with self.assertRaises(sp.ReportError) as caught:
            self.report(cfg=config(tautulli=None))
        self.assertIn("OWNER_ONLY", str(caught.exception))


# ---------------------------------------------------------------- episodes on the server

class EpisodesOnTheServer(Base):
    def test_unavailable_and_unnumbered_episodes_and_two_copies(self):
        self.network()
        report = self.report()
        valley = self.show(report, "Copper Valley")
        # S01E01-E06 minus S01E04 (Plex can't find its file); the second copy of E05 and the
        # unnumbered extra don't add episodes.
        self.assertEqual(valley["episodes_on_server"], 5)
        sam = self.person(report, "Copper Valley", "Sam Tester")
        self.assertEqual(sam["episodes_left"], 2)
        self.assertEqual(sam["next_episode"]["episode"], 5)
        self.assertEqual(self.person(report, "Copper Valley", "Jo Sample")["status"], "caught_up")

    def test_second_copy_keeps_the_first_added_date(self):
        self.network()
        report = self.report()
        self.assertNotIn("Copper Valley", [r["title"] for r in report["recently_added"]])

    def test_specials_are_left_out(self):
        self.network()
        report = self.report()
        lights = self.show(report, "Harbor Lights")
        self.assertEqual(lights["episodes_on_server"], 20)
        self.assertNotIn("Jo Sample", [p["name"] for p in lights["people"]])
        self.assertEqual(lights["unmatched_plays"], 0)

    def test_other_libraries_are_skipped(self):
        server = self.network()
        report = self.report()
        self.assertEqual(report["skipped_libraries"], [{"name": "Movies", "type": "movie"},
                                                       {"name": "Music", "type": "artist"}])
        self.assertFalse(any(s.path.startswith(("/library/sections/3", "/library/sections/4"))
                             for s in server.requests))

    def test_library_option(self):
        self.network()
        report = self.report("--library", "kids tv")
        self.assertEqual([s["title"] for s in report["shows"]], ["Puddle Patrol"])

    def test_library_errors(self):
        self.network()
        for name in ("Nope", "Movies"):
            with self.subTest(library=name):
                with self.assertRaises(sp.ReportError) as caught:
                    self.report("--library", name)
                self.assertIn("No TV library matched", str(caught.exception))


# ---------------------------------------------------------------- reading history

class ReadingHistory(Base):
    def test_plays_are_matched_by_numbers_not_rating_key(self):
        self.network()
        report = self.report()
        # Sam's S01E04 was played under a rating key that no longer exists.
        self.assertEqual(self.person(report, "Harbor Lights", "Sam Tester")["episodes_finished"], 15)

    def test_unfinished_play_counts_as_last_play_only(self):
        self.network()
        alex = self.person(self.report(), "Harbor Lights", "Alex Example")
        self.assertEqual(alex["furthest"], {"season": 1, "episode": 2})
        self.assertEqual(alex["last_played_at"], "2026-01-10")

    def test_plays_that_match_no_episode(self):
        self.network()
        night = self.show(self.report(), "Night Garden")
        self.assertEqual(night["unmatched_plays"], 1)

    def test_live_tv_and_shows_no_longer_on_the_server(self):
        self.network()
        report = self.report()
        self.assertEqual(self.show(report, "Harbor Lights")["last_played_at"], "2026-06-10")
        self.assertEqual(report["show_count"], 5)

    def test_private_tautulli_fields_are_dropped(self):
        self.network()
        text = json.dumps(self.report("--user", "sam tester"))
        for private in ("192.0.2.55", "Living Room Test TV", "TestOS", "machine-id-for-tests",
                        "example.invalid", "samtester", '"user_id"', "accountID"):
            with self.subTest(value=private):
                self.assertNotIn(private, text)

    def test_history_cap(self):
        self.network()
        with mock.patch.object(sp, "HISTORY_CAP", 10), mock.patch.object(sp, "TAUTULLI_PAGE_SIZE", 4):
            report = self.report()
        self.assertTrue(report["history_capped"])

    def test_plex_counts_every_row_towards_the_cap(self):
        self.network(tautulli=False)
        entries = len(plex_entries(self.rows))
        with mock.patch.object(sp, "HISTORY_CAP", entries):
            report = self.report(cfg=config(tautulli=None))
        self.assertTrue(report["history_capped"])
        self.assertFalse(self.report(cfg=config(tautulli=None))["history_capped"])

    def test_history_since(self):
        self.network()
        self.assertEqual(self.report()["history_since"], "2025-12-01")

    def test_history_since_with_one_show_or_person(self):
        # The whole history's oldest row, not the oldest of this show's or this person's plays.
        self.network()
        self.assertEqual(self.report("--show", "night garden")["history_since"], "2025-12-01")
        self.assertEqual(self.report("--user", "jo")["history_since"], "2025-12-01")
        self.assertEqual(self.report("--show", "puddle", "--user", "jo")["history_since"], "2025-12-01")
        self.network(tautulli=False)
        plex = config(tautulli=None)
        oldest = self.report(cfg=plex)["history_since"]
        self.assertEqual(self.report("--show", "night garden", cfg=plex)["history_since"], oldest)

    def test_history_since_skips_live_tv(self):
        oldest = dict(self.rows[-1], live=1, stopped=self.rows[-1]["stopped"] - 86400 * 400)
        self.rows.append(oldest)
        self.network()
        self.assertEqual(self.report("--show", "night garden")["history_since"], "2025-12-01")

    def test_capped_history_since_is_the_oldest_row_read(self):
        self.network()
        with mock.patch.object(sp, "HISTORY_CAP", 4):
            report = self.report("--show", "night garden")
        self.assertTrue(report["history_capped"])
        self.assertEqual(report["history_since"], "2026-05-29")

    def test_plex_history_only_finished_episodes(self):
        self.network(tautulli=False)
        report = self.report(cfg=config(tautulli=None))
        alex = self.person(report, "Harbor Lights", "Alex Example")
        self.assertEqual(alex["last_played_at"], "2025-12-02")
        self.assertEqual(alex["status"], "stopped")
        self.assertEqual(self.show(report, "Night Garden")["unmatched_plays"], 0)

    def test_empty_history(self):
        self.network(tautulli=False, history=lambda seen: paged([], seen))
        report = self.report(cfg=config(tautulli=None))
        self.assertEqual(report["shows"], [])
        self.assertEqual(report["show_count"], 0)
        self.assertIsNone(report["history_since"])


# ---------------------------------------------------------------- places in shows

class Places(Base):
    def test_a_rewatch_of_season_1(self):
        self.network()
        sam = self.person(self.report(), "Harbor Lights", "Sam Tester")
        self.assertEqual(sam["furthest"], {"season": 2, "episode": 5})
        self.assertEqual(sam["episodes_left"], 5)
        self.assertEqual(sam["next_episode"], {"season": 2, "episode": 6, "title": "Episode 6"})
        self.assertEqual(sam["status"], "in_progress")
        self.assertEqual(sam["last_played_at"], "2026-06-10")

    def test_started_partway_in(self):
        self.network()
        alex = self.person(self.report(), "Night Garden", "Alex Example")
        self.assertEqual(alex["furthest"], {"season": 3, "episode": 4})
        self.assertEqual(alex["episodes_left"], 6)
        self.assertEqual(alex["episodes_finished"], 4)

    def test_caught_up(self):
        self.network()
        jo = self.person(self.report(), "Copper Valley", "Jo Sample")
        self.assertEqual(jo["status"], "caught_up")
        self.assertEqual(jo["episodes_left"], 0)
        self.assertIsNone(jo["next_episode"])

    def test_new_episodes_even_after_months(self):
        self.network()
        jo = self.person(self.report(), "The Clockmakers", "Jo Sample")
        self.assertEqual(jo["status"], "new_episodes")
        self.assertEqual(jo["new_since_last_play"], 3)
        self.assertEqual(jo["next_episode"]["title"], "New Season Part 1")

    def test_stopped(self):
        self.network()
        alex = self.person(self.report(), "Harbor Lights", "Alex Example")
        self.assertEqual(alex["status"], "stopped")
        self.assertEqual(alex["episodes_left"], 18)

    def test_stopped_months_option(self):
        self.network()
        alex = self.person(self.report("--stopped-months", "12"), "Harbor Lights", "Alex Example")
        self.assertEqual(alex["status"], "in_progress")

    def test_new_episodes_before_last_play_are_in_progress(self):
        self.network()
        sam = self.person(self.report(), "Puddle Patrol", "Sam Tester")
        self.assertEqual(sam["status"], "in_progress")
        self.assertEqual(sam["new_since_last_play"], 0)

    def test_status_order(self):
        show = sp.Show({"ratingKey": "1", "title": "Order Test"}, {"title": "TV", "key": "1"})
        for number, added in (((1, 1), 100), ((1, 2), 100), ((1, 3), 5000)):
            show.episodes[number] = {"title": "", "added": added}
        cutoff = 3000
        cases = [
            ({(1, 3): 10}, 10, "caught_up"),
            ({(1, 2): 10}, 200, "new_episodes"),     # only E03 is left, added after the last play
            ({(1, 1): 10}, 200, "stopped"),          # E02 was there, nothing since before the cutoff
            ({(1, 1): 10}, 4000, "in_progress"),
        ]
        for finished, last, status in cases:
            with self.subTest(status=status):
                progress = sp.Progress("Test")
                progress.finished, progress.last_played = dict(finished), last
                self.assertEqual(sp.place(show, progress, cutoff)["status"], status)


# ---------------------------------------------------------------- recently added

class RecentlyAdded(Base):
    def test_shows_with_new_episodes(self):
        self.network()
        report = self.report()
        recent = report["recently_added"]
        self.assertEqual([r["title"] for r in recent], ["Puddle Patrol", "The Clockmakers"])
        clock = recent[1]
        self.assertEqual(clock["new_episodes"], 3)
        self.assertEqual(clock["added_since"], "2026-05-20")
        self.assertEqual(clock["people"], [{"name": "Jo Sample", "finished_new": 0, "was_following": True}])
        self.assertTrue(clock["nobody_started"])
        puddle = recent[0]
        self.assertEqual(puddle["people"], [{"name": "Sam Tester", "finished_new": 1, "was_following": True}])
        self.assertFalse(puddle["nobody_started"])

    def test_people_who_started_after_the_new_episodes_arrived(self):
        self.network()
        # 200 days back, the window starts in November 2025: everything Sam and Jo finished came later.
        recent = {r["title"]: r for r in self.report("--new-days", "200")["recently_added"]}
        puddle = recent["Puddle Patrol"]
        self.assertEqual(puddle["people"], [{"name": "Sam Tester", "finished_new": 1, "was_following": False}])
        self.assertFalse(puddle["nobody_started"])
        clock = recent["The Clockmakers"]
        self.assertEqual(clock["people"], [{"name": "Jo Sample", "finished_new": 0, "was_following": False}])
        self.assertTrue(clock["nobody_started"])

    def test_new_days_option(self):
        self.network()
        report = self.report("--new-days", "15")
        self.assertEqual([r["title"] for r in report["recently_added"]], ["Puddle Patrol"])

    def test_limit(self):
        self.network()
        report = self.report("--top", "1")
        self.assertEqual(len(report["recently_added"]), 1)
        self.assertEqual(report["recently_added_count"], 2)


# ---------------------------------------------------------------- one person or show

class OnePerson(Base):
    def test_exact_name_with_tautulli(self):
        calls = []
        self.network(calls=calls)
        report = self.report("--user", "SAM TESTER")
        self.assertEqual(report["user"], "Sam Tester")
        self.assertEqual({p["name"] for s in report["shows"] for p in s["people"]}, {"Sam Tester"})
        history = [c for c in calls if c["cmd"] == "get_history"]
        # Every page is filtered; one unfiltered oldest-first call finds how far the history goes.
        self.assertEqual([c for c in history if "user_id" not in c and c["order_dir"] == "asc"], history[-1:])
        self.assertTrue(all(c["user_id"] == "11" for c in history[:-1]))

    def test_part_of_a_name_with_plex(self):
        self.network(tautulli=False)
        report = self.report("--user", "alex", cfg=config(tautulli=None))
        self.assertEqual(report["user"], "Alex Example")
        self.assertEqual({p["name"] for s in report["shows"] for p in s["people"]}, {"Alex Example"})
        self.assertEqual(report["status_counts"], {"caught_up": 0, "new_episodes": 0, "in_progress": 1,
                                                   "stopped": 1})

    def test_two_people_match(self):
        self.network()
        with self.assertRaises(sp.ReportError) as caught:
            self.report("--user", "sam")
        self.assertIn("USER_AMBIGUOUS", str(caught.exception))

    def test_nobody_matches_without_falling_back(self):
        server = self.network()
        with self.assertRaises(sp.ReportError) as caught:
            self.report("--user", "nobody")
        self.assertIn("USER_NOT_FOUND", str(caught.exception))
        self.assertFalse(any(s.path == "/status/sessions/history/all" for s in server.requests))


class OneShow(Base):
    def test_one_show(self):
        calls = []
        server = self.network(calls=calls)
        report = self.report("--show", "harbor")
        self.assertEqual(report["show"], "Harbor Lights")
        self.assertEqual([s["title"] for s in report["shows"]], ["Harbor Lights"])
        history = [c for c in calls if c["cmd"] == "get_history"]
        self.assertEqual([c for c in history if "grandparent_rating_key" not in c and c["order_dir"] == "asc"],
                         history[-1:])
        self.assertTrue(all(c["grandparent_rating_key"] == "101" for c in history[:-1]))
        # Only that show's library is read for episodes.
        self.assertFalse(any(s.path == "/library/sections/2/all" and s.query["type"] == "4"
                             for s in server.requests))

    def test_plex_filter_and_check(self):
        server = self.network(tautulli=False, honor_filter=False)
        report = self.report("--show", "night garden", cfg=config(tautulli=None))
        self.assertEqual(len(report["shows"]), 1)
        self.assertEqual([p["name"] for p in report["shows"][0]["people"]], ["Alex Example"])
        history = [s for s in server.requests if s.path == "/status/sessions/history/all"]
        self.assertEqual([s.query for s in history if "metadataItemID" not in s.query],
                         [{"sort": "viewedAt:asc"}])
        self.assertTrue(all(s.query["metadataItemID"] == "103" for s in history[:-1]))

    def test_punctuation_and_exact_match(self):
        self.network()
        self.assertEqual(self.report("--show", "the clockmakers!")["show"], "The Clockmakers")
        self.assertEqual(self.report("--show", "office hours us")["show"], "Office Hours (US)")

    def test_several_match(self):
        self.network()
        with self.assertRaises(sp.ReportError) as caught:
            self.report("--show", "office")
        message = str(caught.exception)
        self.assertIn("SHOW_AMBIGUOUS", message)
        self.assertIn("Office Hours (UK) (2016, TV Shows)", message)
        self.assertIn("Office Hours (US) (2018, TV Shows)", message)

    def test_none_match(self):
        self.network()
        with self.assertRaises(sp.ReportError) as caught:
            self.report("--show", "zzz")
        self.assertIn("SHOW_NOT_FOUND", str(caught.exception))

    def test_a_show_nobody_watches(self):
        self.network()
        report = self.report("--show", "office hours uk")
        self.assertEqual(report["show_count"], 1)
        self.assertEqual(report["shows"][0]["people"], [])


# ---------------------------------------------------------------- report contents

class ReportContents(Base):
    def test_sorting_and_counts(self):
        self.network()
        report = self.report()
        self.assertEqual([s["title"] for s in report["shows"]],
                         ["Harbor Lights", "Puddle Patrol", "Copper Valley", "Night Garden", "The Clockmakers"])
        self.assertEqual([p["name"] for p in self.show(report, "Harbor Lights")["people"]],
                         ["Sam Tester", "Alex Example"])
        self.assertEqual(report["status_counts"], {"caught_up": 1, "new_episodes": 1, "in_progress": 4,
                                                   "stopped": 1})
        self.assertEqual(report["stopped_after_months"], 3)
        self.assertEqual(report["new_days"], 30)
        self.assertIsNone(report["user"])
        self.assertIsNone(report["show"])

    def test_top_limit_counts_everything(self):
        self.network()
        report = self.report("--top", "2")
        self.assertEqual(len(report["shows"]), 2)
        self.assertEqual(report["show_count"], 5)
        self.assertEqual(sum(report["status_counts"].values()), 7)

    def test_show_fields(self):
        self.network()
        lights = self.show(self.report(), "Harbor Lights")
        self.assertEqual(lights["year"], 2019)
        self.assertEqual(lights["library"], "TV Shows")
        self.assertEqual(lights["last_added_at"], "2025-01-10")

    def test_server_text_is_cleaned(self):
        self.plex["shows"][0]["title"] = "Harbor\nLights\x1b[31m"
        self.network()
        titles = [s["title"] for s in self.report()["shows"]]
        self.assertIn("Harbor Lights [31m", titles)


class Options(OfflineTestCase):
    def test_numbers(self):
        for option in ("--stopped-months", "--new-days", "--top"):
            for value in ("0", "-1"):
                with self.subTest(option=option, value=value):
                    with self.assertRaises(SystemExit):
                        sp.parse_args([option, value])
        parsed = sp.parse_args([])
        self.assertEqual((parsed.stopped_months, parsed.new_days, parsed.top, parsed.source), (3, 30, 25, "auto"))

    def test_empty_names(self):
        for option in ("--show", "--user"):
            with self.subTest(option=option):
                with self.assertRaises(SystemExit):
                    sp.parse_args([option, "  "])


class Check(Base):
    def test_check(self):
        server = self.network()
        result = sp.check(config())
        self.assertTrue(result["ok"])
        self.assertEqual(result["plex"]["server"], "Test Server")
        self.assertFalse(any(s.path == "/:/prefs" for s in server.requests))
