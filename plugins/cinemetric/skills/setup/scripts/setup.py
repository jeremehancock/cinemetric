#!/usr/bin/env python3
"""Cinemetric setup: connect to a Plex server by signing in with Plex.

Steps (each is a separate run, because the user approves in their browser in between):
  start          ask plex.tv for a sign-in link
  finish         after the user approves, collect the token and list their servers
  select N       test server N, then save its address and token to the config file
  status         say whether Cinemetric is configured (never shows the token)
  tautulli       optional: add Tautulli. Run it in your own terminal; it asks for the
                 address and hides the API key as you type it
  tautulli-remove  forget the saved Tautulli address and key

The token goes straight from plex.tv into a private file; it is never printed.
Uses only the Python standard library. Output is JSON on stdout; errors go to stderr.
"""

import argparse
import getpass
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

VERSION = "0.2.0"
PRODUCT = "Cinemetric"
TIMEOUT_SECONDS = 15
FINISH_WAIT_SECONDS = 60

# Every address this script may contact, apart from the user's chosen server ("/" only).
PLEX_TV_RULES = [
    ("POST", re.compile(r"^https://plex\.tv/api/v2/pins$")),
    ("GET", re.compile(r"^https://plex\.tv/api/v2/pins/\d+$")),
    ("GET", re.compile(r"^https://clients\.plex\.tv/api/v2/resources$")),
]


class SetupError(Exception):
    """An error with a message that is safe to show the user."""


# ---------------------------------------------------------------- files

def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "cinemetric")


def config_path():
    return os.path.join(config_dir(), "config.json")


def pending_path():
    return os.path.join(config_dir(), "pending-signin.json")


def write_private(path, data):
    """Write JSON so that only the current user can ever read it (no window with looser permissions)."""
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    os.chmod(os.path.dirname(path), 0o700)
    tmp = path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def read_private(path):
    try:
        info = os.stat(path)
    except FileNotFoundError:
        return None
    if os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise SetupError(f"Refusing to read {path}: other users can access it. Fix with: chmod 600 {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------- http

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SetupError(f"Unexpected redirect (HTTP {code}); stopping so the token is not sent elsewhere.")


def _opener(verify_tls=True):
    context = ssl.create_default_context() if verify_tls else ssl._create_unverified_context()
    return urllib.request.build_opener(_NoRedirect(), urllib.request.HTTPSHandler(context=context))


def plex_headers(client_id, token=None):
    headers = {
        "Accept": "application/json",
        "X-Plex-Product": PRODUCT,
        "X-Plex-Version": VERSION,
        "X-Plex-Client-Identifier": client_id,
        "X-Plex-Device-Name": PRODUCT,
    }
    if token:
        headers["X-Plex-Token"] = token
    return headers


def plex_tv(method, url, client_id, token=None, params=None):
    if not any(m == method and rule.match(url) for m, rule in PLEX_TV_RULES):
        raise SetupError(f"Blocked request outside the allowlist: {method} {url}")
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    data = b"" if method == "POST" else None
    request = urllib.request.Request(full, data=data, headers=plex_headers(client_id, token), method=method)
    try:
        with _opener().open(request, timeout=TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise SetupError("The sign-in request expired. Run setup again.") from None
        raise SetupError(f"plex.tv returned HTTP {exc.code}.") from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        raise SetupError(f"Could not talk to plex.tv: {reason}") from None


def test_server(uri, token, client_id):
    """Return the server's name if `uri` answers with this token, else None."""
    request = urllib.request.Request(
        uri.rstrip("/") + "/", headers=plex_headers(client_id, token), method="GET"
    )
    try:
        with _opener().open(request, timeout=5) as resp:
            return json.loads(resp.read()).get("MediaContainer", {}).get("friendlyName") or "?"
    except Exception:
        return None


# ---------------------------------------------------------------- steps

def cmd_start(args):
    client_id = "cinemetric-" + str(uuid.uuid4())
    pin = plex_tv("POST", "https://plex.tv/api/v2/pins", client_id, params={"strong": "true"})
    write_private(pending_path(), {"client_id": client_id, "pin_id": pin["id"], "code": pin["code"],
                                   "created": int(time.time())})
    query = urllib.parse.urlencode({
        "clientID": client_id,
        "code": pin["code"],
        "context[device][product]": PRODUCT,
    })
    return {
        "step": "approve_in_browser",
        "sign_in_url": "https://app.plex.tv/auth#?" + query,
        "expires_in_minutes": int(pin.get("expiresIn", 1800)) // 60,
    }


def cmd_finish(args):
    pending = read_private(pending_path())
    if not pending or "pin_id" not in pending:
        raise SetupError("No sign-in in progress. Run setup start first.")
    client_id = pending["client_id"]

    token = pending.get("account_token")
    deadline = time.time() + FINISH_WAIT_SECONDS
    while not token:
        pin = plex_tv("GET", f"https://plex.tv/api/v2/pins/{pending['pin_id']}", client_id)
        token = pin.get("authToken")
        if token:
            break
        if time.time() > deadline:
            return {"step": "waiting", "message": "Not approved yet. Approve in the browser, then run finish again."}
        time.sleep(2)

    resources = plex_tv(
        "GET", "https://clients.plex.tv/api/v2/resources", client_id, token,
        params={"includeHttps": 1, "includeRelay": 0},
    )
    servers = []
    for res in resources:
        if "server" not in str(res.get("provides", "")):
            continue
        connections = sorted(
            res.get("connections", []) or [],
            # Prefer local, then https, and never relays.
            key=lambda c: (not c.get("local"), c.get("protocol") != "https"),
        )
        servers.append({
            "name": res.get("name"),
            "owned": bool(res.get("owned")),
            "token": res.get("accessToken") or token,
            "connections": [c["uri"] for c in connections if c.get("uri") and not c.get("relay")],
        })
    if not servers:
        raise SetupError("Signed in, but this Plex account has no servers it can access.")

    pending["account_token"] = token
    pending["servers"] = servers
    write_private(pending_path(), pending)
    return {
        "step": "choose_server",
        "servers": [
            {"number": i + 1, "name": s["name"], "owned_by_you": s["owned"], "addresses": len(s["connections"])}
            for i, s in enumerate(servers)
        ],
    }


def cmd_select(args):
    pending = read_private(pending_path())
    if not pending or "servers" not in pending:
        raise SetupError("Run setup finish first.")
    if os.path.exists(config_path()) and not args.replace:
        raise SetupError("Cinemetric is already configured. Re-run select with --replace to overwrite it.")
    servers = pending["servers"]
    if not 1 <= args.number <= len(servers):
        raise SetupError(f"Choose a server number from 1 to {len(servers)}.")
    server = servers[args.number - 1]

    for uri in server["connections"]:
        name = test_server(uri, server["token"], pending["client_id"])
        if name:
            config = {
                "plex_url": uri,
                "plex_token": server["token"],
                "client_id": pending["client_id"],
            }
            # Keep an existing Tautulli setup when switching Plex servers.
            config.update({k: v for k, v in (read_private(config_path()) or {}).items()
                           if k.startswith("tautulli_")})
            write_private(config_path(), config)
            os.remove(pending_path())
            return {"step": "done", "server": name, "address": uri, "config_file": config_path()}
    raise SetupError(
        f"Could not reach {server['name']} at any of its {len(server['connections'])} addresses "
        "from this computer. Check that it is running and reachable on your network."
    )


def cmd_status(args):
    config = read_private(config_path())
    if not config:
        return {"configured": False}
    return {
        "configured": True,
        "address": config.get("plex_url"),
        "has_token": bool(config.get("plex_token")),
        "tautulli": {"address": config.get("tautulli_url"), "has_api_key": bool(config.get("tautulli_api_key"))}
        if config.get("tautulli_url") else None,
    }


def test_tautulli(url, api_key):
    """Return Tautulli's version if the address and key work; raise SetupError otherwise."""
    query = urllib.parse.urlencode({"apikey": api_key, "cmd": "get_tautulli_info"})
    request = urllib.request.Request(f"{url}/api/v2?{query}", headers={"Accept": "application/json"})
    try:
        with _opener().open(request, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise SetupError(f"Tautulli returned HTTP {exc.code}. Check the address.") from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = str(getattr(exc, "reason", exc)).replace(api_key, "[hidden]")
        raise SetupError(f"Could not talk to Tautulli at {url}: {reason}") from None
    response = data.get("response", {}) if isinstance(data, dict) else {}
    if response.get("result") != "success":
        raise SetupError("Tautulli rejected the API key. Copy it again from Tautulli: Settings → Web Interface → API.")
    return (response.get("data") or {}).get("tautulli_version") or "?"


def cmd_tautulli(args):
    if not sys.stdin.isatty():
        raise SetupError(
            "Run this in your own terminal so the API key never passes through the chat: "
            f"python3 {os.path.abspath(__file__)} tautulli"
        )
    config = read_private(config_path()) or {}
    print("Add Tautulli to Cinemetric (optional; used for watch history and stats).", file=sys.stderr)
    url = input("Tautulli address, e.g. http://192.168.1.10:8181: ").strip()
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.query:
        raise SetupError("The address must look like http://host:8181 (no username, ? or # parts).")
    url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    api_key = getpass.getpass("Tautulli API key (Settings → Web Interface → API; hidden as you type): ").strip()
    if not api_key:
        raise SetupError("No API key entered.")
    version = test_tautulli(url, api_key)
    config.update({"tautulli_url": url, "tautulli_api_key": api_key})
    write_private(config_path(), config)
    return {"step": "done", "tautulli": url, "tautulli_version": version}


def cmd_tautulli_remove(args):
    config = read_private(config_path()) or {}
    removed = [k for k in list(config) if k.startswith("tautulli_")]
    for key in removed:
        del config[key]
    if removed:
        write_private(config_path(), config)
    return {"step": "done", "removed": bool(removed)}


def cmd_cancel(args):
    if os.path.exists(pending_path()):
        os.remove(pending_path())
    return {"step": "cancelled"}


def main():
    parser = argparse.ArgumentParser(description="Cinemetric setup via Sign in with Plex.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("start")
    sub.add_parser("finish")
    select = sub.add_parser("select")
    select.add_argument("number", type=int)
    select.add_argument("--replace", action="store_true", help="overwrite an existing config")
    sub.add_parser("status")
    sub.add_parser("cancel")
    sub.add_parser("tautulli")
    sub.add_parser("tautulli-remove")
    args = parser.parse_args()

    handlers = {"start": cmd_start, "finish": cmd_finish, "select": cmd_select,
                "status": cmd_status, "cancel": cmd_cancel,
                "tautulli": cmd_tautulli, "tautulli-remove": cmd_tautulli_remove}
    try:
        result = handlers[args.command](args)
    except SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    json.dump(result, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
