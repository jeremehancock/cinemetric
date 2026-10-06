"""year-in-review (openspec/specs/year-in-review/spec.md)."""

import contextlib
import io
import json
import os
import re
import stat
import sys
import time
from unittest import mock

from helpers import FAKE_API_KEY, FAKE_TOKEN, FakeServer, OfflineTestCase, Reply, fixture, load_script

yr = load_script("year-in-review")

PLEX_URL = "http://192.0.2.10:32400"
TAUTULLI_URL = "http://192.0.2.10:8181"
NAMES = ("alex-test", "sam-test", "jo-test", "Alex's iPhone", "Living Room TV")


def epoch(when):
    return int(time.mktime(time.strptime(when, "%Y-%m-%d %H:%M")))


def history():
    data = fixture("year-in-review", "history.json")
    for p in data["plays"]:
        p["started"] = epoch(p["when"])
    return data


# ---------------------------------------------------------------- fake servers

def tautulli_rows(data, play_duration=True):
    people = {int(p["account"]): p for p in data["people"]}
    rows = []
    for i, p in enumerate(sorted(data["plays"], key=lambda p: -p["started"])):
        person = people[p["user"]]
        paused = p.get("paused", 0)
        row = {
            "user_id": person["user_id"], "user": person["username"], "friendly_name": person["friendly_name"],
            "player": data["devices"][i % 2], "platform": "Roku", "ip_address": "192.0.2.50",
            "media_type": p["kind"], "title": p["title"], "full_title": p["title"],
            "grandparent_title": p.get("show") or p.get("artist") or "", "year": p.get("year", ""),
            "started": p["started"], "date": p["started"], "stopped": p["started"] + p["played"] + paused,
            "paused_counter": paused, "live": p.get("live", 0),
        }
        if play_duration:
            row["play_duration"] = row["duration"] = p["played"]
        else:
            row["duration"] = p["played"]
        rows.append(row)
    return rows


def tautulli_route(data, admin=True, play_duration=True):
    rows = tautulli_rows(data, play_duration)
    users = [dict(p, is_admin=p["is_admin"] if admin else 0) for p in data["people"]]

    def answer(seen):
        cmd = seen.query["cmd"]
        if cmd == "get_users":
            result = users
        elif cmd == "get_tautulli_info":
            result = {"tautulli_version": "v2.18.2"}
        elif cmd == "get_history":
            # Like Tautulli, but ignoring the dates: the script must keep rows by their start time.
            found = [r for r in rows if "user_id" not in seen.query or str(r["user_id"]) == seen.query["user_id"]]
            start, length = int(seen.query["start"]), int(seen.query["length"])
            result = {"data": found[start:start + length], "recordsFiltered": len(found)}
        else:
            return {"response": {"result": "error", "message": f"no sample for {cmd}"}}
        return {"response": {"result": "success", "message": None, "data": result}}
    return answer


def plex_routes(data):
    entries = []
    for p in sorted(data["plays"], key=lambda p: -p["started"]):
        entry = {"accountID": p["user"],
                 "deviceID": 7, "viewedAt": p["started"], "type": p["kind"], "title": p["title"]}
        if p["kind"] == "movie":
            entry["year"] = p["year"]
        else:
            entry["grandparentTitle"] = p.get("show") or p.get("artist")
        entries.append(entry)

    def page(seen):
        start = int(seen.headers.get("x-plex-container-start", 0))
        size = int(seen.headers.get("x-plex-container-size", len(entries)))
        return {"MediaContainer": {"Metadata": entries[start:start + size]}}

    accounts = [{"id": 0, "name": ""}] + [{"id": int(p["account"]), "name": p["username"]} for p in data["people"]]
    return {
        "/": {"MediaContainer": {"friendlyName": "Test Server", "version": "1.40.0"}},
        "/accounts": {"MediaContainer": {"Account": accounts}},
        "/status/sessions/history/all": page,
    }


class Recaps(OfflineTestCase):
    """Runs the script's main() against fake Plex and Tautulli servers."""

    def setUp(self):
        super().setUp()
        self.data = history()
        self.write_config({"plex_url": PLEX_URL, "plex_token": FAKE_TOKEN,
                           "tautulli_url": TAUTULLI_URL, "tautulli_api_key": FAKE_API_KEY})
        routes = plex_routes(self.data)
        routes["/api/v2"] = tautulli_route(self.data)
        self.server = FakeServer(routes)
        self.routes = self.server.routes  # tests change answers here
        real = yr.build_opener
        patcher = mock.patch.object(yr, "build_opener", lambda url, verify: self.server.attach(real(url, verify)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_script(self, *argv):
        """Return (exit code, parsed stdout or None)."""
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["year_in_review.py", *argv]), contextlib.redirect_stdout(out):
            code = yr.main()
        return code, (json.loads(out.getvalue()) if out.getvalue().strip() else None)

    def recap(self, *argv):
        code, report = self.run_script(*argv)
        self.assertEqual(code, 0, self.stderr.getvalue())
        return report

    def error(self, *argv):
        code, _ = self.run_script(*argv)
        self.assertEqual(code, 1)
        return self.stderr.getvalue()

    def page(self, report):
        with open(report["output"], encoding="utf-8") as fh:
            return fh.read()

    def history_requests(self):
        return [s for s in self.server.requests
                if s.query.get("cmd") == "get_history" or s.path == "/status/sessions/history/all"]


# ---------------------------------------------------------------- sources and options

class Sources(Recaps):
    def test_only_allowed_paths_and_commands(self):
        self.recap("--year", "2025")
        self.recap("--year", "2025", "--source", "plex", "--user", "sam")
        for seen in self.server.requests:
            self.assertEqual(seen.method, "GET")
            if seen.path == "/api/v2":
                self.assertIn(seen.query["cmd"], yr.TAUTULLI_COMMANDS)
            else:
                self.assertTrue(any(rule.match(seen.path) for rule in yr.ALLOWED_PATHS), seen.path)

    def test_tautulli_down_falls_back_to_plex(self):
        self.routes["/api/v2"] = Reply("down", status=500)
        report = self.recap("--year", "2025")
        self.assertEqual(report["source"], "plex")
        self.assertIn("Tautulli is configured but failed", report["fallback_reason"])

    def test_tautulli_source_without_tautulli(self):
        self.write_config({"plex_url": PLEX_URL, "plex_token": FAKE_TOKEN})
        self.assertIn("TAUTULLI_NOT_CONFIGURED", self.error("--year", "2025", "--source", "tautulli"))

    def test_owner_only(self):
        self.routes["/status/sessions/history/all"] = Reply("no", status=403)
        self.assertIn("OWNER_ONLY", self.error("--year", "2025", "--source", "plex"))

    def test_year_out_of_range(self):
        this_year = time.localtime().tm_year
        message = self.error("--year", str(this_year + 5))
        self.assertIn(f"from 2000 to {this_year}", message)
        self.assertEqual(self.server.requests, [])

    def test_me_and_user_together(self):
        self.assertIn("not both", self.error("--me", "--user", "alex-test"))

    def test_check_reports_tautulli_failure(self):
        self.routes["/api/v2"] = {"response": {"result": "error", "message": "Invalid apikey"}}
        report = self.recap("--check")
        self.assertFalse(report["ok"])
        self.assertFalse(report["tautulli"]["ok"])
        self.assertEqual(report["plex"]["server"], "Test Server")


# ---------------------------------------------------------------- counting

class Counting(Recaps):
    def test_whole_server_from_tautulli(self):
        report = self.recap("--year", "2025")
        self.assertEqual((report["scope"], report["source"], report["user"]), ("server", "tautulli", None))
        self.assertFalse(report["partial_year"])
        # New Year edges count, the plays just outside don't, and live TV is left out.
        self.assertEqual(report["totals"], {"plays": 8, "hours": 9.1, "titles": 5, "active_days": 8})
        self.assertEqual(report["people"], 3)
        self.assertEqual(report["by_type"], {"movies": {"plays": 5, "hours": 8.0}, "tv": {"plays": 2, "hours": 1.0},
                                             "music": {"plays": 1, "hours": 0.1}})
        self.assertEqual([m["plays"] for m in report["months"]], [1, 0, 3, 0, 0, 1, 0, 2, 0, 0, 0, 1])
        self.assertFalse(any(m["future"] for m in report["months"]))
        self.assertEqual(report["busiest_month"], {"month": 3, "plays": 3, "hours": 4.5})
        # 5 and 6 March tie at two hours each; the earlier day wins.
        self.assertEqual(report["busiest_day"], {"date": "2025-03-05", "plays": 1, "hours": 2.0})
        self.assertIsNone(report["hours_unavailable"])

    def test_tautulli_dates_only_narrow_the_request(self):
        self.recap("--year", "2025")
        for seen in self.history_requests():
            self.assertEqual((seen.query["after"], seen.query["before"]), ("2024-12-30", "2026-01-03"))
            self.assertEqual(seen.query["grouping"], "1")

    def test_paused_time_is_left_out(self):
        report = self.recap("--year", "2025", "--me")
        movie = next(m for m in report["top_movies"]["entries"] if m["title"] == "Shared Movie (2010)")
        self.assertEqual(movie["hours"], 2.0)

    def test_older_tautulli_uses_duration(self):
        self.routes["/api/v2"] = tautulli_route(self.data, play_duration=False)
        self.assertEqual(self.recap("--year", "2025")["totals"]["hours"], 9.1)

    def test_plex_counts_plays_without_hours(self):
        report = self.recap("--year", "2025", "--source", "plex")
        self.assertEqual(report["source"], "plex")
        # Plex doesn't mark live TV, so that play counts here.
        self.assertEqual(report["totals"], {"plays": 9, "hours": None, "titles": 6, "active_days": 9})
        self.assertIn("finished plays", report["hours_unavailable"])
        self.assertTrue(all(m["hours"] is None for m in report["months"]))
        self.assertTrue(all(e["hours"] is None for e in report["top_movies"]["entries"]))
        # Ranked by plays, ties broken by title.
        self.assertEqual([e["title"] for e in report["top_movies"]["entries"]],
                         ["<b>Test</b> (2020)", "Shared Movie (2010)"])

    def test_plex_paging_stops_at_the_years_start(self):
        older = [{"when": f"2023-0{m}-01 12:00", "user": 1, "kind": "movie", "title": "Old", "year": 1990,
                  "played": 60} for m in range(1, 6)]
        for p in older:
            p["started"] = epoch(p["when"])
        self.data["plays"].extend(older)
        self.routes.update(plex_routes(self.data))
        with mock.patch.object(yr, "PAGE_SIZE", 2):
            report = self.recap("--year", "2025", "--source", "plex")
        self.assertEqual(report["totals"]["plays"], 9)
        # Six pages reach back to 31 December 2024; the 2023 pages are never asked for.
        self.assertEqual(len(self.history_requests()), 6)

    def test_history_cap(self):
        with mock.patch.object(yr, "HISTORY_CAP", 3):
            report = self.recap("--year", "2025")
        self.assertTrue(report["history_capped"])
        self.assertEqual(report["totals"]["plays"], 3)

    def test_ranking_by_hours(self):
        plays = ([yr.play(1, "episode", "Show A", epoch("2025-02-01 10:00"), 1080)] * 40
                 + [yr.play(2, "episode", "Show B", epoch("2025-02-01 11:00"), 7200)] * 10)
        args = mock.Mock(top=10, min_viewers=1)
        summary = yr.summarize(plays, args, "server", True, 2025, epoch("2026-01-01 00:00"), False)
        self.assertEqual([e["title"] for e in summary["top_shows"]["entries"]], ["Show B", "Show A"])

    def test_two_months_tie(self):
        plays = [yr.play(1, "movie", "A", epoch("2025-03-02 10:00"), 3600),
                 yr.play(1, "movie", "B", epoch("2025-07-02 10:00"), 3600)]
        summary = yr.summarize(plays, mock.Mock(top=10, min_viewers=1), "me", True, 2025,
                               epoch("2026-01-01 00:00"), False)
        self.assertEqual(summary["busiest_month"]["month"], 3)

    def test_partial_year(self):
        now = epoch("2026-10-06 12:00")
        start, end, partial = yr.year_window(2026, now)
        self.assertEqual((start, end, partial), (epoch("2026-01-01 00:00"), now, True))
        self.assertFalse(yr.year_window(2025, now)[2])
        summary = yr.summarize([], mock.Mock(top=10, min_viewers=2), "server", True, 2026, end, partial)
        self.assertEqual([m["month"] for m in summary["months"] if m["future"]], [11, 12])
        self.assertEqual(len(summary["months"]), 12)

    def test_nothing_played(self):
        report = self.recap("--year", "2019")
        self.assertEqual(report["totals"], {"plays": 0, "hours": 0.0, "titles": 0, "active_days": 0})
        self.assertIsNone(report["busiest_month"])
        self.assertIsNone(report["busiest_day"])
        self.assertEqual(report["top_movies"], {"entries": [], "held_back": 0})
        self.assertIn("Nothing was played in 2019.", self.page(report))


# ---------------------------------------------------------------- whose plays

class Scopes(Recaps):
    def test_my_year_with_tautulli(self):
        report = self.recap("--year", "2025", "--me")
        self.assertEqual((report["scope"], report["user"], report["people"], report["min_viewers"]),
                         ("me", None, None, None))
        for seen in self.history_requests():
            self.assertEqual(seen.query["user_id"], "1001")
        self.assertEqual(report["totals"]["plays"], 4)
        # A title only the owner played is listed in their own recap.
        self.assertIn("Solo Artist", [e["title"] for e in report["top_artists"]["entries"]])
        self.assertNotIn("viewers", report["top_movies"]["entries"][0])
        self.assertIn("Your year", self.page(report))

    def test_my_year_with_plex(self):
        report = self.recap("--year", "2025", "--me", "--source", "plex")
        self.assertEqual(report["totals"]["plays"], 4)

    def test_my_year_without_an_owner(self):
        self.routes["/api/v2"] = tautulli_route(self.data, admin=False)
        self.assertIn("USER_NOT_FOUND", self.error("--year", "2025", "--me"))

    def test_one_person_with_plex(self):
        report = self.recap("--year", "2025", "--user", "sam", "--source", "plex")
        self.assertEqual((report["scope"], report["user"]), ("user", "sam-test"))
        self.assertEqual(report["totals"]["plays"], 4)
        self.assertIn("sam-test", self.page(report))

    def test_nobody_matches_and_no_fallback(self):
        self.assertIn("USER_NOT_FOUND", self.error("--year", "2025", "--user", "nobody"))
        self.assertFalse([s for s in self.server.requests if s.path.startswith("/status")])


# ---------------------------------------------------------------- care with other people's viewing

class Privacy(Recaps):
    def body(self, report):
        return self.page(report).split("</style>", 1)[1]

    def test_whole_server_recap_names_no_one(self):
        for source in ("tautulli", "plex"):
            with self.subTest(source=source):
                report = self.recap("--year", "2025", "--source", source)
                text = json.dumps(report) + self.body(report)
                for name in NAMES + ("Alex&#x27;s iPhone", "192.0.2.50"):
                    self.assertNotIn(name, text)
                for key in ("user_id", "accountID", "player", "started", "viewedAt", "friendly_name"):
                    self.assertNotIn(f'"{key}"', json.dumps(report))
                self.assertEqual(report["people"], 3)

    def test_titles_one_person_watched_stay_out(self):
        report = self.recap("--year", "2025")
        self.assertEqual(report["min_viewers"], 2)
        self.assertEqual(report["top_movies"]["entries"], [
            {"title": "Shared Movie (2010)", "plays": 2, "hours": 4.0, "viewers": 2},
            {"title": "<b>Test</b> (2020)", "plays": 2, "hours": 3.0, "viewers": 2},
        ])
        self.assertEqual(report["top_movies"]["held_back"], 1)
        self.assertEqual(report["top_shows"], {"entries": [
            {"title": "Shared Show", "plays": 2, "hours": 1.0, "viewers": 2}], "held_back": 0})
        self.assertEqual(report["top_artists"], {"entries": [], "held_back": 1})
        text = json.dumps(report) + self.body(report)
        self.assertNotIn("New Year Movie", text)
        self.assertNotIn("Solo Artist", text)
        # Still counted in the totals.
        self.assertEqual(report["by_type"]["music"]["plays"], 1)
        self.assertIn("None played by at least 2 people.", self.body(report))
        self.assertIn("1 movie and 1 artist watched by only one person were left out to keep each "
                      "person's viewing private.", self.body(report))

    def test_min_viewers_one_lists_everything(self):
        report = self.recap("--year", "2025", "--min-viewers", "1")
        self.assertIn("New Year Movie (1999)", [e["title"] for e in report["top_movies"]["entries"]])
        self.assertEqual(report["top_movies"]["held_back"], 0)

    def test_min_viewers_is_limited(self):
        self.assertEqual(self.recap("--year", "2025", "--min-viewers", "50", "--json-only")["min_viewers"], 10)

    def test_fewer_people_than_min_viewers(self):
        report = self.recap("--year", "2025", "--min-viewers", "4")
        self.assertEqual(report["top_shows"]["entries"], [])
        self.assertIn("Fewer than 4 people watched anything this year", self.body(report))


# ---------------------------------------------------------------- the page and where it goes

def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class Page(Recaps):
    def test_page_is_self_contained_and_escaped(self):
        page = self.page(self.recap("--year", "2025"))
        self.assertTrue(page.split("<head>", 1)[1].startswith('<meta http-equiv="Content-Security-Policy" '
                                                             'content="default-src \'none\''))
        self.assertNotIn("<script", page.lower())
        self.assertIsNone(re.search(r"https?://", page))
        self.assertIn("&lt;b&gt;Test&lt;/b&gt; (2020)", page)
        self.assertNotIn("<b>Test</b>", page)
        self.assertIn("Everyone&#x27;s year: 2025", page)

    def test_file_names_and_permissions(self):
        report = self.recap("--year", "2025")
        self.assertEqual(os.path.basename(report["output"]), "year-in-review-2025.html")
        self.assertEqual(report["recap_id"], "2025")
        self.assertEqual(mode(report["output"]), 0o600)
        self.assertEqual(mode(os.path.dirname(report["output"])), 0o700)
        again = self.recap("--year", "2025")
        self.assertEqual(again["output"], report["output"])
        pages = [f for f in os.listdir(os.path.dirname(report["output"])) if f.endswith(".html")]
        self.assertEqual(pages, ["year-in-review-2025.html"])

    def test_person_file_has_no_name(self):
        report = self.recap("--year", "2025", "--user", "sam-test")
        self.assertRegex(report["recap_id"], r"^2025-person-[0-9a-f]{8}$")
        self.assertNotIn("sam", report["recap_id"])
        self.assertNotIn("sam", os.path.basename(report["output"]))
        self.assertEqual(self.recap("--year", "2025", "--me")["recap_id"], "2025-me")

    def test_same_person_same_recap_from_either_source(self):
        for name in ("sam-test", "alex-test"):  # alex-test is the owner
            with self.subTest(person=name):
                ids = {self.recap("--year", "2025", "--user", name, "--source", source, "--json-only")["recap_id"]
                       for source in ("tautulli", "plex")}
                self.assertEqual(len(ids), 1)

    def test_json_only_writes_nothing(self):
        report = self.recap("--year", "2025", "--json-only")
        self.assertIsNone(report["output"])
        self.assertFalse(os.path.exists(yr.default_output("2025")))

    def test_output_option_keeps_the_recap_id(self):
        path = os.path.join(self.tmp, "elsewhere", "recap.html")
        report = self.recap("--year", "2025", "--output", path)
        self.assertEqual((report["output"], report["recap_id"]), (path, "2025"))
        self.assertTrue(os.path.exists(path))


class SavedChoices(Recaps):
    LINK = "https://claude.ai/code/artifact/0b8f2c1e-4d2a-4f7e-9a51-3c6d7e8f9a0b"
    OTHER = "https://claude.ai/artifact/abc-123"

    def test_first_recap_asks_where_it_goes(self):
        report = self.recap("--year", "2025")
        self.assertEqual((report["destination"], report["ask"], report["online_page"]), (None, ["destination"], None))

    def test_saved_choice_applies_to_every_recap(self):
        self.recap("destination", "both")
        self.assertEqual(mode(yr.state_path()), 0o600)
        for argv in (("--year", "2025"), ("--year", "2025", "--me")):
            report = self.recap(*argv)
            self.assertEqual((report["destination"], report["ask"]), ("both", []))

    def test_dashboard_choice_is_separate(self):
        folder = os.path.dirname(yr.state_path())
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "dashboard-state.json"), "w", encoding="utf-8") as fh:
            json.dump({"destination": "online"}, fh)
        self.assertIsNone(self.recap("--year", "2025")["destination"])

    def test_each_recap_keeps_its_own_link(self):
        self.recap("online-page", "--recap", "2025", "--url", self.LINK)
        self.recap("online-page", "--recap", "2025-me", "--url", self.OTHER)
        self.assertEqual(self.recap("--year", "2025")["online_page"], self.LINK)
        self.assertEqual(self.recap("--year", "2025", "--me")["online_page"], self.OTHER)
        self.recap("destination", "local")
        self.assertEqual(self.recap("--year", "2025")["online_page"], self.LINK)
        self.recap("online-page", "--recap", "2025-me", "--forget")
        self.assertIsNone(self.recap("--year", "2025", "--me")["online_page"])
        self.assertEqual(self.recap("--year", "2025")["online_page"], self.LINK)

    def test_link_to_somewhere_else(self):
        self.recap("online-page", "--recap", "2025", "--url", self.LINK)
        self.assertIn("claude.ai page link", self.error("online-page", "--recap", "2025", "--url",
                                                        "https://example.com/page"))
        self.assertEqual(self.recap("--year", "2025")["online_page"], self.LINK)

    def test_crafted_recap_id(self):
        self.assertIn("isn't a recap id", self.error("online-page", "--recap", "../dashboard", "--url", self.LINK))
        self.assertFalse(os.path.exists(yr.state_path()))
