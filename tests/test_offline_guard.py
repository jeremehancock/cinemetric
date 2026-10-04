"""The test setup itself: no real network, no real settings, and a working fake server."""

import os
import socket
import urllib.error
import urllib.request

from helpers import CLEARED_ENV, FakeServer, NetworkBlocked, OfflineTestCase, Reply


class NetworkIsBlocked(OfflineTestCase):
    def test_socket_connection_fails_the_test(self):
        with self.assertRaises(NetworkBlocked) as caught:
            socket.create_connection(("192.0.2.1", 32400), timeout=1)
        self.assertIn("real network connection", str(caught.exception))

    def test_urllib_request_fails_the_test(self):
        with self.assertRaises(NetworkBlocked):
            urllib.request.urlopen("http://192.0.2.1:32400/", timeout=1)

    def test_name_lookup_fails_the_test(self):
        with self.assertRaises(NetworkBlocked):
            socket.getaddrinfo("plex.tv", 443)


class SettingsAreIsolated(OfflineTestCase):
    def test_config_and_data_folders_are_temporary(self):
        for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "HOME"):
            self.assertTrue(os.environ[name].startswith(self.tmp), name)
        self.assertEqual(os.path.expanduser("~"), self.tmp)

    def test_connection_settings_are_cleared(self):
        for name in CLEARED_ENV:
            self.assertNotIn(name, os.environ)


class FakeServerAnswers(OfflineTestCase):
    def opener(self, routes):
        server = FakeServer(routes)
        return server, server.attach(urllib.request.build_opener())

    def test_known_path_gets_its_reply_and_is_recorded(self):
        server, opener = self.opener({"/hello": {"ok": True}})
        with opener.open("http://plex.test:32400/hello?x=1") as resp:
            self.assertEqual(resp.read(), b'{"ok": true}')
        self.assertEqual(len(server.requests), 1)
        self.assertEqual(server.requests[0].method, "GET")
        self.assertEqual(server.requests[0].query, {"x": "1"})

    def test_unknown_path_is_a_404(self):
        _, opener = self.opener({})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            opener.open("http://plex.test:32400/nothing")
        self.assertEqual(caught.exception.code, 404)

    def test_status_codes_raise_like_a_real_server(self):
        _, opener = self.opener({"/secret": Reply("no", status=401)})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            opener.open("http://plex.test:32400/secret")
        self.assertEqual(caught.exception.code, 401)
