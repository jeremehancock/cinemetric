"""setup (openspec/specs/setup/spec.md) and the private-file rules in the security spec."""

import argparse
import json
import os
import ssl
import stat
from unittest import mock

from helpers import FAKE_API_KEY, FAKE_TOKEN, FakeServer, OfflineTestCase, Reply, Unreachable, load_script

su = load_script("setup")

TAUTULLI_URL = "http://192.0.2.10:8181"
CLIENT_ID = "cinemetric-client-id-for-tests"


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class Faked(OfflineTestCase):
    """Route every request setup makes through one FakeServer."""

    def fake(self, routes):
        server = FakeServer(routes)
        real = su._opener
        patcher = mock.patch.object(su, "_opener", lambda verify_tls=True: server.attach(real(verify_tls)))
        patcher.start()
        self.addCleanup(patcher.stop)
        return server


# ---------------------------------------------------------------- private files

class PrivateFiles(OfflineTestCase):
    def test_written_files_are_private(self):
        path = os.path.join(self.tmp, "config", "cinemetric", "config.json")
        su.write_private(path, {"plex_token": FAKE_TOKEN})
        self.assertEqual(su.read_private(path), {"plex_token": FAKE_TOKEN})
        if os.name == "posix":
            self.assertEqual(mode(path), 0o600)
            self.assertEqual(mode(os.path.dirname(path)), 0o700)

    def test_leftover_temporary_file_is_replaced(self):
        path = os.path.join(self.tmp, "config", "cinemetric", "config.json")
        os.makedirs(os.path.dirname(path))
        with open(path + ".tmp", "w") as fh:
            fh.write("half-written")
        su.write_private(path, {"ok": True})
        self.assertEqual(su.read_private(path), {"ok": True})
        self.assertFalse(os.path.exists(path + ".tmp"))

    def test_missing_file(self):
        self.assertIsNone(su.read_private(os.path.join(self.tmp, "nothing.json")))

    def test_damaged_files(self):
        for content in ("", "{not json", "[1, 2]"):
            with self.subTest(content=content):
                path = self.write_raw(content)
                with self.assertRaises(su.DamagedFile):
                    su.read_private(path)

    def test_file_others_can_read_is_refused(self):
        if os.name != "posix":
            self.skipTest("file permissions are only checked on POSIX")
        path = self.write_raw('{"plex_token": "x"}', mode=0o644)
        with self.assertRaises(su.SetupError) as caught:
            su.read_private(path)
        self.assertNotIsInstance(caught.exception, su.DamagedFile)
        self.assertIn("chmod 600", str(caught.exception))

    def write_raw(self, content, mode=0o600):
        path = os.path.join(self.tmp, "file.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(path, mode)
        return path


class Status(OfflineTestCase):
    def test_not_configured(self):
        self.assertEqual(su.cmd_status(None), {"configured": False})

    def test_never_shows_secrets(self):
        su.write_private(su.config_path(), {"plex_url": "http://192.0.2.10:32400", "plex_token": FAKE_TOKEN,
                                            "tautulli_url": TAUTULLI_URL, "tautulli_api_key": FAKE_API_KEY})
        result = su.cmd_status(None)
        self.assertTrue(result["has_token"])
        self.assertTrue(result["tautulli"]["has_api_key"])
        self.assertNotIn(FAKE_TOKEN, json.dumps(result))
        self.assertNotIn(FAKE_API_KEY, json.dumps(result))

    def test_damaged_config(self):
        os.makedirs(su.config_dir(), mode=0o700)
        with open(su.config_path(), "w") as fh:
            fh.write("{oops")
        os.chmod(su.config_path(), 0o600)
        self.assertEqual(su.cmd_status(None)["damaged"], True)


# ---------------------------------------------------------------- Tautulli

class Tautulli(Faked):
    def test_working_key_returns_the_version(self):
        server = self.fake({"/api/v2": {"response": {"result": "success",
                                                     "data": {"tautulli_version": "v2.14.0\n-test"}}}})
        self.assertEqual(su.test_tautulli(TAUTULLI_URL, FAKE_API_KEY), "v2.14.0 -test")
        [seen] = server.requests
        self.assertEqual(seen.method, "GET")
        self.assertEqual(seen.query["cmd"], "get_tautulli_info")

    def test_rejected_key(self):
        self.fake({"/api/v2": {"response": {"result": "error", "message": "Invalid apikey"}}})
        with self.assertRaises(su.SetupError) as caught:
            su.test_tautulli(TAUTULLI_URL, FAKE_API_KEY)
        self.assertIn("rejected the API key", str(caught.exception))

    def test_login_page_counts_as_a_rejected_key(self):
        self.fake({"/api/v2": Reply("", status=401)})
        with self.assertRaises(su.SetupError) as caught:
            su.test_tautulli(TAUTULLI_URL, FAKE_API_KEY)
        self.assertIn("rejected the API key", str(caught.exception))

    def test_login_required_is_its_own_error(self):
        self.fake({"/api/v2": Reply("", status=403)})
        with self.assertRaises(su.TautulliLoginRequired):
            su.tautulli_call(TAUTULLI_URL, "get_apikey")

    def test_self_signed_certificate(self):
        self.fake({"/api/v2": Unreachable(ssl.SSLCertVerificationError("self-signed certificate"))})
        with self.assertRaises(su.TautulliCertificateError):
            su.test_tautulli("https://192.0.2.10:8181", FAKE_API_KEY)

    def test_address_cleaning(self):
        self.assertEqual(su.clean_tautulli_url(" http://192.0.2.10:8181/tautulli/ "), "http://192.0.2.10:8181/tautulli")
        for bad in ("", None, "192.0.2.10:8181", "http://u:p@host:8181", "http://host:8181/?apikey=1"):
            with self.subTest(url=bad):
                with self.assertRaises(su.SetupError):
                    su.clean_tautulli_url(bad)


# ---------------------------------------------------------------- signing in

RESOURCES = "https://clients.plex.tv/api/v2/resources"


class SigningIn(Faked):
    def start_pending(self, **extra):
        su.write_private(su.pending_path(), dict({"client_id": CLIENT_ID, "pin_id": 7, "code": "abcd",
                                                  "created": 1700000000}, **extra))

    def test_listed_server_names_are_cleaned(self):
        self.start_pending()
        crafted = "Evil\nServer\x1b[2J" + "x" * 300
        self.fake({
            "https://plex.tv/api/v2/pins/7": {"id": 7, "authToken": FAKE_TOKEN},
            RESOURCES: [
                {"name": crafted, "provides": "server", "owned": False, "accessToken": "server-token-for-tests",
                 "connections": [
                     {"uri": "http://192.0.2.10:32400", "local": True, "protocol": "http"},
                     {"uri": "https://relay.test:8443", "local": False, "protocol": "https", "relay": True},
                     {"uri": "https://192-0-2-10.test.plex.direct:32400", "local": True, "protocol": "https"}]},
                {"name": "Phone", "provides": "client,player"},
            ],
        })
        result = su.cmd_finish(None)
        [listed] = result["servers"]
        self.assertEqual(len(listed["name"]), 120)
        self.assertTrue(listed["name"].startswith("Evil Server [2J"))
        self.assertEqual(listed["addresses"], 2)  # the relay is never used
        self.assertFalse(listed["owned_by_you"])
        self.assertNotIn(FAKE_TOKEN, json.dumps(result))
        self.assertNotIn("server-token-for-tests", json.dumps(result))

        saved = su.read_private(su.pending_path())
        self.assertEqual(saved["servers"][0]["connections"],
                         ["https://192-0-2-10.test.plex.direct:32400", "http://192.0.2.10:32400"])

    def test_account_with_no_servers(self):
        self.start_pending(account_token=FAKE_TOKEN)
        self.fake({RESOURCES: [{"name": "Phone", "provides": "player"}]})
        with self.assertRaises(su.SetupError):
            su.cmd_finish(None)

    def test_select_tries_each_address_and_keeps_tautulli(self):
        self.start_pending(servers=[{"name": "Test Server", "owned": True, "token": FAKE_TOKEN,
                                     "connections": ["http://192.0.2.10:32400", "http://192.0.2.11:32400"]}])
        su.write_private(su.config_path(), {"plex_url": "http://old.test", "plex_token": "old",
                                            "tautulli_url": TAUTULLI_URL, "tautulli_api_key": FAKE_API_KEY})
        self.fake({
            "http://192.0.2.10:32400/": Unreachable("timed out"),
            "http://192.0.2.11:32400/": {"MediaContainer": {"friendlyName": "Test Server"}},
        })
        with self.assertRaises(su.SetupError):
            su.cmd_select(argparse.Namespace(number=1, replace=False))

        result = su.cmd_select(argparse.Namespace(number=1, replace=True))
        self.assertEqual((result["server"], result["address"]), ("Test Server", "http://192.0.2.11:32400"))
        config = su.read_private(su.config_path())
        self.assertEqual(config["plex_url"], "http://192.0.2.11:32400")
        self.assertEqual(config["tautulli_api_key"], FAKE_API_KEY)
        self.assertFalse(os.path.exists(su.pending_path()))

    def test_select_out_of_range(self):
        self.start_pending(servers=[{"name": "Test Server", "token": FAKE_TOKEN, "connections": []}])
        with self.assertRaises(su.SetupError):
            su.cmd_select(argparse.Namespace(number=2, replace=False))
