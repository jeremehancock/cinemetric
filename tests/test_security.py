"""Security rules shared by the scripts (openspec/specs/security/spec.md).

Shared helpers are copied into each script, so every check runs against every copy. A failure names
the script it came from.
"""

from unittest import mock

from helpers import (FAKE_API_KEY, FAKE_TOKEN, FakeServer, OfflineTestCase, Reply, Unreachable,
                     load_script, plex_container)

PLEX_URL = "http://192.0.2.10:32400"
TAUTULLI_URL = "http://192.0.2.10:8181"

library = load_script("library-report")
health = load_script("server-health")
watch = load_script("watch-activity")
setup = load_script("setup")
shares = load_script("users-and-shares")
unwatched = load_script("unwatched")
picker = load_script("what-to-watch")
gaps = load_script("episode-gaps")
checker = load_script("playback-check")
recap = load_script("year-in-review")
lookup = load_script("title-lookup")

# (script name, address check, error it raises). Each check takes just the address.
ADDRESS_CHECKS = [
    ("library-report", library.validate_url, library.ReportError),
    ("server-health", health.validate_url, health.ReportError),
    ("watch-activity", lambda url: watch.validate_url(url, "plex_url"), watch.ReportError),
    ("users-and-shares", lambda url: shares.validate_url(url, "plex_url"), shares.ReportError),
    ("unwatched", lambda url: unwatched.validate_url(url, "plex_url"), unwatched.ReportError),
    ("what-to-watch", lambda url: picker.validate_url(url, "plex_url"), picker.ReportError),
    ("episode-gaps", lambda url: gaps.validate_url(url, "plex_url"), gaps.ReportError),
    ("playback-check", lambda url: checker.validate_url(url, "plex_url"), checker.ReportError),
    ("year-in-review", lambda url: recap.validate_url(url, "plex_url"), recap.ReportError),
    ("title-lookup", lambda url: lookup.validate_url(url, "plex_url"), lookup.ReportError),
    ("setup", setup.clean_tautulli_url, setup.SetupError),
]
WARNS_ABOUT_PLAIN_HTTP = ADDRESS_CHECKS[:10]
LOOKS_LOCAL = [("library-report", library.looks_local), ("server-health", health.looks_local),
               ("watch-activity", watch.looks_local), ("users-and-shares", shares.looks_local),
               ("unwatched", unwatched.looks_local), ("what-to-watch", picker.looks_local),
               ("episode-gaps", gaps.looks_local), ("playback-check", checker.looks_local),
               ("year-in-review", recap.looks_local), ("title-lookup", lookup.looks_local)]
CLEANERS = [("library-report", library.clean), ("server-health", health.clean),
            ("watch-activity", watch.clean), ("users-and-shares", shares.clean),
            ("unwatched", unwatched.clean), ("what-to-watch", picker.clean), ("episode-gaps", gaps.clean),
            ("playback-check", checker.clean), ("year-in-review", recap.clean), ("title-lookup", lookup.clean),
            ("setup", setup.clean)]


class AddressChecks(OfflineTestCase):
    def test_accepts_http_and_https_with_a_host(self):
        for name, check, _ in ADDRESS_CHECKS:
            for url in ("http://192.168.1.5:32400", "https://plex.example.com", "http://nas:8181/tautulli"):
                with self.subTest(script=name, url=url):
                    self.assertEqual(check(url), url)

    def test_strips_trailing_slash_and_spaces(self):
        for name, check, _ in ADDRESS_CHECKS:
            with self.subTest(script=name):
                self.assertEqual(check("  http://192.168.1.5:32400/  "), "http://192.168.1.5:32400")

    def test_refuses_unsafe_or_malformed_addresses(self):
        bad = [
            "ftp://192.168.1.5",                   # not http or https
            "file:///etc/passwd",                  # no host
            "192.168.1.5:32400",                   # no scheme
            "http://",                             # no host
            "http://user:pass@192.168.1.5:32400",  # credentials in the address
            "http://user@192.168.1.5:32400",
            "http://192.168.1.5:32400/?X-Plex-Token=abc",  # query part
            "http://192.168.1.5:32400/#top",       # fragment
        ]
        for name, check, error in ADDRESS_CHECKS:
            for url in bad:
                with self.subTest(script=name, url=url):
                    with self.assertRaises(error):
                        check(url)

    def test_password_in_address_gets_a_clear_message(self):
        for name, check, error in ADDRESS_CHECKS:
            with self.subTest(script=name):
                with self.assertRaises(error) as caught:
                    check("http://user:pass@host:32400")
                self.assertIn("username", str(caught.exception))
                self.assertNotIn("pass@", str(caught.exception))

    def test_warns_about_plain_http_to_a_public_address(self):
        for name, check, _ in WARNS_ABOUT_PLAIN_HTTP:
            with self.subTest(script=name):
                self.stderr.seek(0)
                self.stderr.truncate()
                check("http://plex.example.com:32400")
                self.assertIn("warning:", self.stderr.getvalue())
                self.stderr.seek(0)
                self.stderr.truncate()
                check("http://192.168.1.5:32400")
                check("https://plex.example.com")
                self.assertEqual(self.stderr.getvalue(), "")


class LooksLocal(OfflineTestCase):
    def test_home_network_addresses(self):
        local = ["192.168.1.5", "10.0.0.2", "172.16.4.4", "127.0.0.1", "169.254.10.10", "::1",
                 "fe80::1", "nas", "plex.local", "media.lan", "box.home.arpa", "srv.internal"]
        for name, looks_local in LOOKS_LOCAL:
            for host in local:
                with self.subTest(script=name, host=host):
                    self.assertTrue(looks_local(host))

    def test_public_addresses(self):
        public = ["8.8.8.8", "93.184.216.34", "plex.example.com",
                  "2606:4700::1111"]
        for name, looks_local in LOOKS_LOCAL:
            for host in public:
                with self.subTest(script=name, host=host):
                    self.assertFalse(looks_local(host))


class CleanText(OfflineTestCase):
    def test_control_characters_become_spaces(self):
        for name, clean in CLEANERS:
            with self.subTest(script=name):
                self.assertEqual(clean("Bad\nTitle\twith\x1b[31mcolour\x7f"), "Bad Title with [31mcolour")

    def test_cut_to_120_characters(self):
        for name, clean in CLEANERS:
            with self.subTest(script=name):
                self.assertEqual(len(clean("x" * 500)), 120)

    def test_missing_text_becomes_empty(self):
        for name, clean in CLEANERS:
            with self.subTest(script=name):
                self.assertEqual(clean(None), "")
                self.assertEqual(clean(42), "42")


# ---------------------------------------------------------------- Plex clients

def plex_clients():
    """(script name, module, function that builds a client wired to a FakeServer)."""
    def builder(module):
        def build(server):
            client = module.PlexClient(PLEX_URL, FAKE_TOKEN, True)
            server.attach(client._opener)
            return client
        return build
    return [(name, module, builder(module))
            for name, module in (("library-report", library), ("server-health", health),
                                 ("watch-activity", watch), ("users-and-shares", shares),
                                 ("unwatched", unwatched), ("what-to-watch", picker),
                                 ("episode-gaps", gaps), ("playback-check", checker),
                                 ("year-in-review", recap), ("title-lookup", lookup))]


class PlexClientRules(OfflineTestCase):
    def test_only_get_requests_with_the_token_in_a_header(self):
        for name, _, build in plex_clients():
            with self.subTest(script=name):
                server = FakeServer({"/": plex_container(friendlyName="Test Server")})
                self.assertEqual(build(server).get("/")["friendlyName"], "Test Server")
                [seen] = server.requests
                self.assertEqual(seen.method, "GET")
                self.assertEqual(seen.headers["x-plex-token"], FAKE_TOKEN)
                self.assertNotIn(FAKE_TOKEN, seen.url)

    def test_paths_outside_the_allowlist_are_blocked_before_any_request(self):
        for name, module, build in plex_clients():
            for path in ("/library/metadata/1/delete", "/:/scrobble", "/../", "/library/sections/1/refresh"):
                with self.subTest(script=name, path=path):
                    server = FakeServer()
                    with self.assertRaises(module.ReportError) as caught:
                        build(server).get(path)
                    self.assertIn("allowlist", str(caught.exception))
                    self.assertEqual(server.requests, [])

    def test_redirects_are_refused(self):
        for name, module, build in plex_clients():
            with self.subTest(script=name):
                server = FakeServer({
                    "/": Reply("", status=302, headers={"Location": "http://elsewhere.test/steal"}),
                })
                with self.assertRaises(module.ReportError) as caught:
                    build(server).get("/")
                self.assertIn("redirect", str(caught.exception).lower())
                self.assertEqual([s.url for s in server.requests], [PLEX_URL + "/"])

    def test_token_is_hidden_in_connection_errors(self):
        for name, module, build in plex_clients():
            with self.subTest(script=name):
                server = FakeServer({"/": Unreachable(f"refused for {FAKE_TOKEN}")})
                with self.assertRaises(module.ReportError) as caught:
                    build(server).get("/")
                self.assertNotIn(FAKE_TOKEN, str(caught.exception))
                self.assertIn("hidden]", str(caught.exception))

    def test_rejected_token(self):
        for name, module, build in plex_clients():
            with self.subTest(script=name):
                server = FakeServer({"/": Reply("", status=401)})
                with self.assertRaises(module.ReportError) as caught:
                    build(server).get("/")
                self.assertIn("401", str(caught.exception))
                self.assertNotIn(FAKE_TOKEN, str(caught.exception))

    def test_other_http_errors(self):
        for name, module, build in plex_clients():
            with self.subTest(script=name):
                server = FakeServer({"/": Reply("", status=500)})
                with self.assertRaises(module.ReportError) as caught:
                    build(server).get("/")
                self.assertIn("HTTP 500", str(caught.exception))

    def test_reply_that_is_not_json(self):
        for name, module, build in plex_clients():
            with self.subTest(script=name):
                server = FakeServer({"/": Reply("<html>login</html>")})
                with self.assertRaises(module.ReportError) as caught:
                    build(server).get("/")
                self.assertIn("not JSON", str(caught.exception))


# ---------------------------------------------------------------- Tautulli

def tautulli_ok(data):
    return {"response": {"result": "success", "message": None, "data": data}}


class WatchActivityTautulliClient(OfflineTestCase):
    module = watch
    allowed = "get_tautulli_info"

    def client(self, server):
        client = self.module.TautulliClient(TAUTULLI_URL, FAKE_API_KEY, True)
        server.attach(client._opener)
        return client

    def test_allowed_command_is_a_get(self):
        server = FakeServer({"/api/v2": tautulli_ok({"tautulli_version": "v2.0"})})
        self.assertEqual(self.client(server).call(self.allowed), {"tautulli_version": "v2.0"})
        [seen] = server.requests
        self.assertEqual(seen.method, "GET")
        self.assertEqual(seen.query["cmd"], self.allowed)

    def test_commands_outside_the_allowlist_are_blocked(self):
        for command in ("delete_all_history", "restart", "get_apikey"):
            with self.subTest(command=command):
                server = FakeServer()
                with self.assertRaises(self.module.ReportError):
                    self.client(server).call(command)
                self.assertEqual(server.requests, [])

    def test_api_key_is_hidden_in_errors(self):
        server = FakeServer({"/api/v2": Unreachable(f"bad url ?apikey={FAKE_API_KEY}")})
        with self.assertRaises(self.module.ReportError) as caught:
            self.client(server).call(self.allowed)
        self.assertNotIn(FAKE_API_KEY, str(caught.exception))

    def test_refusal_message_is_cleaned(self):
        server = FakeServer({"/api/v2": {"response": {"result": "error", "message": "Invalid\napikey"}}})
        with self.assertRaises(self.module.ReportError) as caught:
            self.client(server).call(self.allowed)
        self.assertIn("Invalid apikey", str(caught.exception))

    def test_redirect_is_refused(self):
        server = FakeServer({"/api/v2": Reply("", status=301, headers={"Location": "http://elsewhere.test/"})})
        with self.assertRaises(self.module.ReportError):
            self.client(server).call(self.allowed)
        self.assertEqual(len(server.requests), 1)


class UsersAndSharesTautulliClient(WatchActivityTautulliClient):
    module = shares
    allowed = "get_users_table"


class UnwatchedTautulliClient(WatchActivityTautulliClient):
    module = unwatched
    allowed = "get_history"


class PlaybackCheckTautulliClient(WatchActivityTautulliClient):
    module = checker
    allowed = "get_stream_data"


class YearInReviewTautulliClient(WatchActivityTautulliClient):
    module = recap
    allowed = "get_history"


class TitleLookupTautulliClient(WatchActivityTautulliClient):
    module = lookup
    allowed = "get_history"


class SetupNetworkRules(OfflineTestCase):
    def fake(self, routes):
        server = FakeServer(routes)
        real_opener = setup._opener
        patcher = mock.patch.object(setup, "_opener", lambda verify_tls=True: server.attach(real_opener(verify_tls)))
        patcher.start()
        self.addCleanup(patcher.stop)
        return server

    def test_tautulli_commands_outside_the_allowlist_are_blocked(self):
        server = self.fake({})
        with self.assertRaises(setup.SetupError):
            setup.tautulli_call(TAUTULLI_URL, "delete_all_history")
        self.assertEqual(server.requests, [])

    def test_tautulli_key_is_hidden_in_errors(self):
        self.fake({"/api/v2": Unreachable(f"bad url ?apikey={FAKE_API_KEY}")})
        with self.assertRaises(setup.SetupError) as caught:
            setup.tautulli_call(TAUTULLI_URL, "get_tautulli_info", secret=FAKE_API_KEY, apikey=FAKE_API_KEY)
        self.assertNotIn(FAKE_API_KEY, str(caught.exception))

    def test_plex_tv_allowlist_checks_method_and_address(self):
        blocked = [
            ("GET", "https://plex.tv/api/v2/pins"),            # creating a pin must be a POST
            ("POST", "https://plex.tv/api/v2/pins/12"),        # checking a pin must be a GET
            ("GET", "https://plex.tv/api/v2/user"),            # not on the list at all
            ("GET", "https://evil.test/api/v2/pins/12"),
            ("GET", "http://plex.tv/api/v2/pins/12"),          # must be https
        ]
        server = self.fake({})
        for method, url in blocked:
            with self.subTest(method=method, url=url):
                with self.assertRaises(setup.SetupError) as caught:
                    setup.plex_tv(method, url, "client-id-for-tests")
                self.assertIn("allowlist", str(caught.exception))
        self.assertEqual(server.requests, [])

    def test_plex_tv_allowed_request(self):
        server = self.fake({"https://plex.tv/api/v2/pins": {"id": 7, "code": "abcd"}})
        self.assertEqual(setup.plex_tv("POST", "https://plex.tv/api/v2/pins", "client-id-for-tests"),
                         {"id": 7, "code": "abcd"})
        self.assertEqual(server.requests[0].method, "POST")

    def test_redirect_is_refused(self):
        server = self.fake({
            "https://plex.tv/api/v2/pins/7": Reply("", status=302, headers={"Location": "https://evil.test/"}),
        })
        with self.assertRaises(setup.SetupError) as caught:
            setup.plex_tv("GET", "https://plex.tv/api/v2/pins/7", "client-id-for-tests", token=FAKE_TOKEN)
        self.assertIn("redirect", str(caught.exception).lower())
        self.assertEqual(len(server.requests), 1)
