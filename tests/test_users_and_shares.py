"""users-and-shares (openspec/specs/users-and-shares/spec.md)."""

import argparse
import io
import contextlib
import json
import os
import re
import sys
import time
from unittest import mock

from helpers import (FAKE_API_KEY, FAKE_TOKEN, FIXTURES_DIR, FakeServer, OfflineTestCase, Reply,
                     Unreachable, fixture, load_script)

us = load_script("users-and-shares")

PLEX = ("http://192.0.2.10:32400", FAKE_TOKEN, True)
TAUTULLI = ("http://192.0.2.10:8181", FAKE_API_KEY, True)
MACHINE_ID = "abc123def456"
USERS_URL = "https://plex.tv/api/users"
SHARED_URL = f"https://plex.tv/api/servers/{MACHINE_ID}/shared_servers"
INVITES_URL = "https://plex.tv/api/invites/requested"
DAY = 86400

# Private details in the fixtures that must never reach the output.
SECRETS = ["@example.com", "friend-token-", "SECRET", "avatar", "contentRating", "901", "101"]


def args(**overrides):
    values = {"inactive_days": 90}
    values.update(overrides)
    return argparse.Namespace(**values)


def config(tautulli=None, problem=None, plex=PLEX):
    return {"plex": plex, "tautulli": tautulli, "tautulli_problem": problem}


def xml(name):
    """A plex.tv sample with DAYS:n turned into a timestamp n days ago."""
    with open(os.path.join(FIXTURES_DIR, "users-and-shares", name), encoding="utf-8") as fh:
        text = fh.read()
    now = int(time.time())
    text = re.sub(r"DAYS:(\d+)", lambda m: str(now - int(m.group(1)) * DAY), text)
    return text.replace("LASTSEEN", str(now))


def history_route(days_ago):
    """Plex watch history: the newest play for the requested account, if any."""
    now = int(time.time())

    def answer(seen):
        days = days_ago.get(seen.query.get("accountID"))
        views = [] if days is None else [{"viewedAt": now - days * DAY, "accountID": seen.query["accountID"]}]
        return {"MediaContainer": {"Metadata": views}}
    return answer


def tautulli_route(days_ago):
    now = int(time.time())
    rows = [{"user_id": int(uid), "friendly_name": "x", "last_seen": None if d is None else now - d * DAY}
            for uid, d in days_ago.items()]

    def answer(seen):
        if seen.query.get("cmd") != "get_users_table":
            return {"response": {"result": "error", "message": "unexpected command"}}
        return {"response": {"result": "success", "message": None,
                             "data": {"recordsTotal": len(rows), "data": rows}}}
    return answer


def routes():
    activity = fixture("users-and-shares", "activity.json")
    r = dict(fixture("users-and-shares", "server.json"))
    r["/status/sessions/history/all"] = history_route(activity["plex"])
    r[USERS_URL] = Reply(xml("users.xml"))
    r[SHARED_URL] = Reply(xml("shared_servers.xml"))
    r[INVITES_URL] = Reply(xml("invites.xml"))
    r["/api/v2"] = tautulli_route(activity["tautulli"])
    return r


class Network:
    """Route every client the script builds through one FakeServer, and remember how each was built."""

    def __init__(self, test, routes):
        self.server = FakeServer(routes)
        self.openers = []
        real = us.build_opener

        def build(url, verify):
            self.openers.append((url, verify))
            return self.server.attach(real(url, verify))
        patcher = mock.patch.object(us, "build_opener", build)
        patcher.start()
        test.addCleanup(patcher.stop)

    def urls(self):
        return [s.url.split("?")[0] for s in self.server.requests]


class Base(OfflineTestCase):
    def report(self, r=None, cfg=None, **options):
        self.net = Network(self, r or routes())
        return us.build_report(cfg or config(), args(**options))

    def person(self, report, name):
        [match] = [p for p in report["people"] if p["name"] == name]
        return match

    def flag(self, report, kind):
        found = [f for f in report["worth_a_look"] if f["kind"] == kind]
        return found[0] if found else None


# ---------------------------------------------------------------- requests

class Requests(Base):
    def test_only_allowed_addresses_all_get(self):
        self.report(cfg=config(tautulli=TAUTULLI))
        allowed_paths = {"/", "/library/sections", "/status/sessions/history/all", "/api/v2"}
        for seen in self.net.server.requests:
            with self.subTest(url=seen.url):
                self.assertEqual(seen.method, "GET")
                if seen.url.startswith("https://plex.tv"):
                    self.assertIn(seen.url.split("?")[0], {USERS_URL, SHARED_URL, INVITES_URL})
                else:
                    self.assertIn(seen.path, allowed_paths)
                if seen.path == "/api/v2":
                    self.assertEqual(seen.query["cmd"], "get_users_table")

    def test_token_only_in_header_for_plex_tv(self):
        self.report()
        plex_tv = [s for s in self.net.server.requests if s.url.startswith("https://plex.tv")]
        self.assertEqual(len(plex_tv), 3)
        for seen in plex_tv:
            self.assertEqual(seen.headers["x-plex-token"], FAKE_TOKEN)
            self.assertNotIn(FAKE_TOKEN, seen.url)

    def test_strange_machine_id_stops_before_plex_tv(self):
        r = routes()
        r["/"] = {"MediaContainer": {"friendlyName": "x", "machineIdentifier": "abc/../users?x=1"}}
        with self.assertRaises(us.ReportError):
            self.report(r)
        self.assertFalse([u for u in self.net.urls() if "plex.tv" in u])

    def test_plex_tv_rules_check_method_and_address(self):
        net = Network(self, {})
        client = us.PlexTvClient(FAKE_TOKEN)
        for url in ("https://plex.tv/api/v2/user", "https://plex.tv/api/servers/abc/shared_servers/1",
                    "http://plex.tv/api/users", "https://evil.test/api/users",
                    "https://plex.tv/api/servers/a/../shared_servers"):
            with self.subTest(url=url):
                with self.assertRaises(us.ReportError) as caught:
                    client.get(url)
                self.assertIn("allowlist", str(caught.exception))
        self.assertEqual(net.server.requests, [])
        self.assertTrue(all(method == "GET" for method, _ in us.PLEX_TV_RULES))

    def test_plex_tv_certificate_is_always_checked(self):
        self.report(cfg=config(plex=("https://192.0.2.10:32400", FAKE_TOKEN, False)))
        self.assertIn(("https://plex.tv", True), self.net.openers)
        self.assertIn(("https://192.0.2.10:32400", False), self.net.openers)

    def test_entity_declaration_is_not_parsed(self):
        r = routes()
        r[INVITES_URL] = Reply('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><MediaContainer/>')
        report = self.report(r)
        self.assertEqual([u["part"] for u in report["unavailable"]], ["pending invites"])

    def test_oversized_response_is_not_parsed(self):
        r = routes()
        r[USERS_URL] = Reply("<MediaContainer>" + " " * (5 * 1024 * 1024) + "</MediaContainer>")
        with self.assertRaises(us.ReportError) as caught:
            self.report(r)
        self.assertIn("5 MB", str(caught.exception))

    def test_redirect_from_plex_tv_is_refused(self):
        r = routes()
        r[SHARED_URL] = Reply("", status=302, headers={"Location": "https://evil.test/"})
        with self.assertRaises(us.ReportError) as caught:
            self.report(r)
        self.assertIn("redirect", str(caught.exception).lower())


# ---------------------------------------------------------------- owner only and errors

class OwnerOnly(Base):
    def test_shared_server_refused_means_owner_only(self):
        for status in (401, 403):
            with self.subTest(status=status):
                r = routes()
                r[SHARED_URL] = Reply("", status=status)
                with self.assertRaises(us.ReportError) as caught:
                    self.report(r)
                self.assertTrue(str(caught.exception).startswith("OWNER_ONLY:"))

    def test_rejected_token_at_the_server(self):
        r = routes()
        r["/"] = Reply("", status=401)
        with self.assertRaises(us.ReportError) as caught:
            self.report(r)
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("OWNER_ONLY", str(caught.exception))

    def test_required_parts(self):
        for url in (USERS_URL, "/library/sections"):
            with self.subTest(url=url):
                r = routes()
                r[url] = Unreachable("timed out")
                with self.assertRaises(us.ReportError):
                    self.report(r)


# ---------------------------------------------------------------- private details

class PrivateDetails(Base):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["users_and_shares.py"] + argv), \
                mock.patch.object(us, "load_config", lambda: config(tautulli=TAUTULLI)), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = us.main()
        return code, out.getvalue(), err.getvalue()

    def test_no_email_token_or_id_in_the_output(self):
        Network(self, routes())
        code, out, err = self.run_main([])
        self.assertEqual(code, 0)
        for secret in SECRETS:
            with self.subTest(secret=secret):
                self.assertNotIn(secret, out)
                self.assertNotIn(secret, err)

    def test_no_private_details_in_error_paths(self):
        for url in (INVITES_URL, USERS_URL):
            with self.subTest(url=url):
                r = routes()
                r[url] = Reply("<not xml " + xml("shared_servers.xml"))
                Network(self, r)
                code, out, err = self.run_main([])
                for secret in SECRETS:
                    self.assertNotIn(secret, out + err)

    def test_email_only_invite_is_named_invited_by_email(self):
        report = self.report()
        self.assertEqual(self.person(report, "invited by email")["status"], "pending")


# ---------------------------------------------------------------- people and libraries

class People(Base):
    def test_friend_with_two_libraries(self):
        report = self.report()
        alex = self.person(report, "alex")
        self.assertEqual((alex["kind"], alex["status"]), ("friend", "accepted"))
        self.assertEqual(alex["libraries"], ["Movies", "TV Shows"])  # deleted library 99 left out
        libraries = {l["title"]: l for l in report["libraries"]}
        self.assertIn("alex", libraries["Movies"]["shared_with"])
        self.assertIn("alex", libraries["TV Shows"]["shared_with"])
        self.assertNotIn("alex", libraries["Music"]["shared_with"])

    def test_friend_with_all_libraries(self):
        report = self.report()
        self.assertEqual(self.person(report, "blair")["libraries"], "all")
        for library in report["libraries"]:
            self.assertIn("blair", library["shared_with"])

    def test_kinds_and_sorting(self):
        report = self.report()
        kinds = {p["name"]: p["kind"] for p in report["people"]}
        self.assertEqual(kinds["casey"], "home")
        self.assertEqual(kinds["Kids"], "managed")
        self.assertEqual(kinds["alex"], "friend")
        order = [p["kind"] for p in report["people"]]
        self.assertEqual(order, sorted(order, key=us.KIND_ORDER.get))
        friends = [p["name"].lower() for p in report["people"] if p["kind"] == "friend"]
        self.assertEqual(friends, sorted(friends))

    def test_managed_user_details(self):
        kids = self.person(self.report(), "Kids")
        self.assertTrue(kids["content_restrictions"])
        self.assertFalse(kids["allow_downloads"])

    def test_library_shared_with_nobody(self):
        r = routes()
        r[SHARED_URL] = Reply(xml("shared_servers.xml").replace('allLibraries="1"', 'allLibraries="0"')
                              .replace('key="4" title="Home Videos" type="movie" shared="1"',
                                       'key="4" title="Home Videos" type="movie" shared="0"'))
        report = self.report(r)
        home = [l for l in report["libraries"] if l["title"] == "Home Videos"][0]
        self.assertEqual((home["shared_with"], home["shared_with_count"]), ([], 0))

    def test_nobody_to_share_with(self):
        r = routes()
        r[SHARED_URL] = Reply("<MediaContainer size='0'/>")
        r[USERS_URL] = Reply("<MediaContainer size='0'/>")
        r[INVITES_URL] = Reply("<MediaContainer size='0'/>")
        report = self.report(r)
        self.assertEqual(report["people"], [])
        self.assertTrue(all(l["shared_with_count"] == 0 for l in report["libraries"]))
        self.assertEqual(report["worth_a_look"], [])

    def test_pending_share_without_accepted_date(self):
        drew = self.person(self.report(), "drew")
        self.assertEqual(drew["status"], "pending")
        self.assertIsNone(drew["last_played"])

    def test_pending_people_are_not_in_shared_with(self):
        report = self.report()
        tv = [l for l in report["libraries"] if l["title"] == "TV Shows"][0]
        self.assertNotIn("drew", tv["shared_with"])

    def test_friend_request_with_no_server_is_left_out(self):
        names = [p["name"] for p in self.report()["people"]]
        self.assertNotIn("gale", names)

    def test_invite_sharing_the_server_is_pending(self):
        report = self.report()
        frankie = self.person(report, "frankie")
        self.assertEqual((frankie["status"], frankie["libraries"]), ("pending", None))
        self.assertEqual(len([p for p in report["people"] if p["name"] == "drew"]), 1)

    def test_owner_and_other_servers_are_not_listed(self):
        names = [p["name"] for p in self.report()["people"]]
        self.assertNotIn("other", names)

    def test_invites_unavailable(self):
        r = routes()
        r[INVITES_URL] = Unreachable("timed out")
        report = self.report(r)
        self.assertIn("alex", [p["name"] for p in report["people"]])
        self.assertNotIn("frankie", [p["name"] for p in report["people"]])
        self.assertEqual([u["part"] for u in report["unavailable"]], ["pending invites"])

    def test_totals(self):
        totals = self.report()["totals"]
        self.assertEqual(totals["people"], 8)
        self.assertEqual(totals["by_kind"], {"friend": 6, "home": 1, "managed": 1})
        self.assertEqual(totals["by_status"], {"accepted": 5, "pending": 3})


# ---------------------------------------------------------------- last played

class LastPlayed(Base):
    def history_accounts(self):
        return [s.query.get("accountID") for s in self.net.server.requests
                if s.path == "/status/sessions/history/all"]

    def test_tautulli_knows_the_person(self):
        report = self.report(cfg=config(tautulli=TAUTULLI))
        alex = self.person(report, "alex")
        self.assertEqual(alex["last_played_source"], "tautulli")
        self.assertEqual(alex["last_played"], time.strftime("%Y-%m-%d", time.localtime(time.time() - DAY)))
        self.assertNotIn("101", self.history_accounts())
        # Tautulli has no date for blair, so Plex's history is used for them.
        self.assertEqual(self.person(report, "blair")["last_played_source"], "plex")

    def test_no_tautulli(self):
        report = self.report()
        alex = self.person(report, "alex")
        self.assertEqual(alex["last_played_source"], "plex")
        self.assertEqual(alex["last_played"], time.strftime("%Y-%m-%d", time.localtime(time.time() - 2 * DAY)))
        self.assertNotIn("/api/v2", [s.path for s in self.net.server.requests])

    def test_tautulli_is_down(self):
        r = routes()
        r["/api/v2"] = Unreachable("timed out")
        report = self.report(r, cfg=config(tautulli=TAUTULLI))
        accepted = [p for p in report["people"] if p["status"] == "accepted"]
        self.assertTrue(all(p["last_played_source"] in ("plex", None) for p in accepted))
        self.assertEqual([u["part"] for u in report["unavailable"]], ["Tautulli last played dates"])

    def test_no_requests_for_pending_people(self):
        self.report()
        self.assertNotIn("105", self.history_accounts())
        self.assertNotIn("107", self.history_accounts())

    def test_never_played(self):
        emery = self.person(self.report(), "emery")
        self.assertEqual((emery["last_played"], emery["last_played_source"]), (None, None))

    def test_history_failure(self):
        r = routes()
        r["/status/sessions/history/all"] = Reply("", status=500)
        report = self.report(r)
        self.assertEqual([u["part"] for u in report["unavailable"]], ["Plex watch history"])
        self.assertIsNone(self.flag(report, "inactive"))


# ---------------------------------------------------------------- worth a look

class WorthALook(Base):
    def test_flags(self):
        report = self.report()
        self.assertEqual(self.flag(report, "old_pending_invite")["people"], ["drew", "invited by email"])
        self.assertEqual(self.flag(report, "inactive")["people"], ["blair", "emery"])
        self.assertEqual(self.flag(report, "all_libraries")["people"], ["blair"])
        self.assertEqual(self.flag(report, "downloads_allowed")["people"], ["alex", "blair"])
        kinds = [f["kind"] for f in report["worth_a_look"]]
        self.assertEqual(len(kinds), len(set(kinds)))

    def test_custom_inactive_threshold(self):
        report = self.report(inactive_days=4)
        self.assertEqual(self.flag(report, "inactive")["people"], ["Kids", "blair", "emery"])

    def test_nothing_known_is_not_inactive(self):
        r = routes()
        r[SHARED_URL] = Reply(re.sub(r'invitedAt="\d+"', 'invitedAt=""', xml("shared_servers.xml")))
        report = self.report(r)
        self.assertEqual(self.flag(report, "inactive")["people"], ["blair"])

    def test_empty_kinds_are_left_out(self):
        r = routes()
        r[INVITES_URL] = Reply("<MediaContainer size='0'/>")
        r[SHARED_URL] = Reply(xml("shared_servers.xml").replace('acceptedAt=""', 'acceptedAt="1700000000"'))
        r[USERS_URL] = Reply(xml("users.xml").replace('pending="1"', 'pending="0"'))
        report = self.report(r)
        self.assertIsNone(self.flag(report, "old_pending_invite"))


# ---------------------------------------------------------------- options

class Options(Base):
    def test_check(self):
        net = Network(self, routes())
        result = us.check(config())
        self.assertEqual(result["plex"], {"server": "Test Server", "version": "1.41.0"})
        self.assertEqual(net.urls(), ["http://192.0.2.10:32400/", USERS_URL])

    def test_not_configured(self):
        with self.assertRaises(us.ReportError) as caught:
            us.load_config()
        self.assertTrue(str(caught.exception).startswith("NOT_CONFIGURED"))
