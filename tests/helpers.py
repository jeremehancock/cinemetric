"""Shared tools for Cinemetric's tests: loading scripts, a fake server, and an offline test base.

Tests never talk to a real Plex, plex.tv or Tautulli server, and never touch the real settings in
~/.config/cinemetric or ~/.local/share/cinemetric. See tests/README.md.
"""

import contextlib
import email.message
import importlib.util
import io
import json
import os
import socket
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(ROOT, "plugins", "cinemetric", "skills")
FIXTURES_DIR = os.path.join(ROOT, "tests", "fixtures")

# Skill folder -> script file name.
SCRIPTS = {
    "changes": "changes.py",
    "dashboard": "dashboard.py",
    "episode-gaps": "episode_gaps.py",
    "library-report": "library_report.py",
    "server-health": "server_health.py",
    "setup": "setup.py",
    "unwatched": "unwatched.py",
    "users-and-shares": "users_and_shares.py",
    "watch-activity": "watch_activity.py",
    "what-to-watch": "what_to_watch.py",
}

# Settings a test must never pick up from the developer's own environment.
CLEARED_ENV = (
    "PLEX_URL", "PLEX_TOKEN", "TAUTULLI_URL", "TAUTULLI_API_KEY", "CINEMETRIC_DATA_DIR",
)

FAKE_TOKEN = "token-for-tests"
FAKE_API_KEY = "tautulli-key-for-tests"

_loaded = {}


def load_script(skill):
    """Import a skill's script from its file. Importing runs nothing: each script guards main()."""
    if skill not in _loaded:
        path = os.path.join(SKILLS_DIR, skill, "scripts", SCRIPTS[skill])
        name = "cinemetric_" + skill.replace("-", "_")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        _loaded[skill] = module
    return _loaded[skill]


def fixture(*parts):
    """Load a JSON sample response from tests/fixtures/."""
    with open(os.path.join(FIXTURES_DIR, *parts), encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- fake server

class Reply:
    """One canned answer. `body` may be a dict or list (sent as JSON), str or bytes."""

    def __init__(self, body=None, status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = headers or {}


class Unreachable:
    """Make a request fail as if the server couldn't be reached, with `reason` as the error text."""

    def __init__(self, reason):
        self.reason = reason


class Seen:
    """A request the fake server received."""

    def __init__(self, request):
        parts = urllib.parse.urlsplit(request.full_url)
        self.method = request.get_method()
        self.url = request.full_url
        self.path = parts.path
        self.query = dict(urllib.parse.parse_qsl(parts.query))
        self.headers = {k.lower(): v for k, v in request.header_items()}

    def __repr__(self):
        return f"<{self.method} {self.url}>"


class FakeServer(urllib.request.BaseHandler):
    """Answers a script's requests from canned replies instead of the network.

    It plugs into the script's own urllib opener as the very first handler, so the script's real
    client code (allowlists, headers, redirect refusal, error handling) still runs. Routes are keyed
    by path ("/library/sections") or, for plex.tv, by full URL without the query string. A route's
    value is a Reply, an Unreachable, a dict or list (a 200 JSON reply), or a function that takes the
    Seen request and returns one of those. Paths with no route get a 404.
    """

    handler_order = 0

    def __init__(self, routes=None):
        self.routes = dict(routes or {})
        self.requests = []

    def attach(self, opener):
        opener.add_handler(self)
        return opener

    def default_open(self, request):
        seen = Seen(request)
        self.requests.append(seen)
        route = self.routes.get(seen.url.split("?")[0], self.routes.get(seen.path))
        if callable(route):
            route = route(seen)
        if route is None:
            route = Reply("not found", status=404)
        if isinstance(route, Unreachable):
            raise urllib.error.URLError(route.reason)
        if not isinstance(route, Reply):
            route = Reply(route)

        body = route.body
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        headers = email.message.Message()
        for key, value in route.headers.items():
            headers[key] = value
        response = urllib.response.addinfourl(io.BytesIO(body or b""), headers, request.full_url, route.status)
        response.msg = "OK" if route.status < 300 else "Error"
        return response


def plex_container(**fields):
    """Wrap fields the way Plex does: {"MediaContainer": {...}}."""
    return {"MediaContainer": fields}


# ---------------------------------------------------------------- base test case

class NetworkBlocked(AssertionError):
    pass


def _refuse(*args, **kwargs):
    raise NetworkBlocked(
        "a test tried to open a real network connection; give the code a FakeServer instead"
    )


class OfflineTestCase(unittest.TestCase):
    """Every test runs with the network blocked and with settings pointed at a temporary folder.

    self.tmp is the temporary home folder; self.stderr collects what the code printed to stderr.
    """

    def setUp(self):
        super().setUp()
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "socket.getaddrinfo"):
            patcher = mock.patch(target, _refuse)
            patcher.start()
            self.addCleanup(patcher.stop)

        folder = tempfile.TemporaryDirectory(prefix="cinemetric-test-")
        self.addCleanup(folder.cleanup)
        self.tmp = folder.name
        env = mock.patch.dict(os.environ, {
            "HOME": self.tmp,
            "USERPROFILE": self.tmp,
            "XDG_CONFIG_HOME": os.path.join(self.tmp, "config"),
            "XDG_DATA_HOME": os.path.join(self.tmp, "data"),
            "LOCALAPPDATA": os.path.join(self.tmp, "data"),
        })
        env.start()
        self.addCleanup(env.stop)
        for name in CLEARED_ENV:
            os.environ.pop(name, None)

        self.stderr = io.StringIO()
        quiet = contextlib.redirect_stderr(self.stderr)
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def config_file(self):
        return os.path.join(self.tmp, "config", "cinemetric", "config.json")

    def write_config(self, data, mode=0o600):
        """Write a Cinemetric config file inside the temporary folder."""
        path = self.config_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.chmod(path, mode)
        return path


# ---------------------------------------------------------------- snapshots

TEST_SERVER_ID = "machineidfortests"


def snapshot_path(home, day, server_id=TEST_SERVER_ID):
    """Where a snapshot for `day` (a datetime.date) lives under the test's temporary folder."""
    return os.path.join(home, "data", "cinemetric", "snapshots", server_id, f"{day.isoformat()}.json")


def write_snapshot(home, days_ago, server_id=TEST_SERVER_ID, raw=None, **areas):
    """Save a format 1 snapshot dated `days_ago` days before today, with the given areas.

    `raw` writes that exact text instead, for testing damaged files. Returns the file's path.
    """
    import datetime
    day = datetime.date.today() - datetime.timedelta(days=days_ago)
    path = snapshot_path(home, day, server_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if raw is None:
        raw = json.dumps(dict({"format": 1, "date": day.isoformat(), "server_name": "Test Server"}, **areas))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(raw)
    return path
