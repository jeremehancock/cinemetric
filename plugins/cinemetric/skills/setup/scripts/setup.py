#!/usr/bin/env python3
"""Cinemetric setup: connect to a Plex server by signing in with Plex.

Steps (each is a separate run, because the user approves in their browser in between):
  start          ask plex.tv for a sign-in link
  finish         after the user approves, collect the token and list their servers
  select N       test server N, then save its address and token to the config file
  status         say whether Cinemetric is configured (never shows the token)
Optional Tautulli steps (the API key never passes through the chat):
  tautulli-auto URL   try to fetch the key from Tautulli itself (works when Tautulli has no login)
  tautulli-form       open a one-time form on this computer (127.0.0.1) to enter the key
  tautulli-wait       after the user submits the form, report whether it was saved
  tautulli            fallback: run in your own terminal; asks for the address and hides the key
  tautulli-remove     forget the saved Tautulli address and key

The token goes straight from plex.tv into a private file; it is never printed.
Uses only the Python standard library. Output is JSON on stdout; errors go to stderr.
"""

import argparse
import getpass
import hashlib
import hmac
import html
import http.server
import json
import os
import re
import secrets
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

VERSION = "0.21.0"
PRODUCT = "Cinemetric"
TIMEOUT_SECONDS = 15
FINISH_WAIT_SECONDS = 60
FORM_LIFETIME_SECONDS = 600
MAX_TITLE_LENGTH = 120

# The only Tautulli API commands this script may run.
TAUTULLI_COMMANDS = {"get_apikey", "get_tautulli_info"}

# Every address this script may contact, apart from the user's chosen server ("/" only).
PLEX_TV_RULES = [
    ("POST", re.compile(r"^https://plex\.tv/api/v2/pins$")),
    ("GET", re.compile(r"^https://plex\.tv/api/v2/pins/\d+$")),
    ("GET", re.compile(r"^https://clients\.plex\.tv/api/v2/resources$")),
]


class SetupError(Exception):
    """An error with a message that is safe to show the user."""


class TautulliLoginRequired(SetupError):
    """Tautulli answered 401/403: it has a login, so the key can't be fetched without one."""


class TautulliCertificateError(SetupError):
    """Tautulli's https certificate couldn't be verified (usually a self-signed certificate)."""


class DamagedFile(SetupError):
    """A config or sign-in file exists but can't be read as JSON."""


# ---------------------------------------------------------------- files

def config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "cinemetric")


def config_path():
    return os.path.join(config_dir(), "config.json")


def pending_path():
    return os.path.join(config_dir(), "pending-signin.json")


def form_status_path():
    return os.path.join(config_dir(), "pending-tautulli.json")


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
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        raise DamagedFile(
            f"{path} is empty or damaged, so the saved connection can't be used. Run setup again "
            "and replace it (select N --replace); for Tautulli, run the tautulli step again too."
        ) from None
    if not isinstance(data, dict):
        raise DamagedFile(f"{path} is damaged (it should contain a JSON object). Run setup again.")
    return data


# ---------------------------------------------------------------- text

def clean(text):
    """Titles are untrusted data: strip control characters and cap the length."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text or "")).strip()
    return text[:MAX_TITLE_LENGTH]


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
            return clean(json.loads(resp.read()).get("MediaContainer", {}).get("friendlyName")) or "?"
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
        owned = bool(res.get("owned"))
        # The account token may only go to the user's own servers, never to someone else's.
        server_token = res.get("accessToken") or (token if owned else None)
        if not server_token:
            continue
        connections = sorted(
            res.get("connections", []) or [],
            # Prefer local, then https, and never relays.
            key=lambda c: (not c.get("local"), c.get("protocol") != "https"),
        )
        servers.append({
            "name": clean(res.get("name")),
            "owned": owned,
            "token": server_token,
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
            try:
                previous = read_private(config_path()) or {}
            except DamagedFile:
                previous = {}
            config.update({k: v for k, v in previous.items() if k.startswith("tautulli_")})
            write_private(config_path(), config)
            os.remove(pending_path())
            return {"step": "done", "server": name, "address": uri, "config_file": config_path()}
    raise SetupError(
        f"Could not reach {server['name']} at any of its {len(server['connections'])} addresses "
        "from this computer. Check that it is running and reachable on your network."
    )


def cmd_status(args):
    try:
        config = read_private(config_path())
    except DamagedFile as exc:
        return {"configured": False, "damaged": True, "message": str(exc)}
    if not config:
        return {"configured": False}
    return {
        "configured": True,
        "address": config.get("plex_url"),
        "has_token": bool(config.get("plex_token")),
        "tautulli": {"address": config.get("tautulli_url"), "has_api_key": bool(config.get("tautulli_api_key")),
                     "certificate_check": config.get("tautulli_verify_tls", True) is not False}
        if config.get("tautulli_url") else None,
    }


def clean_tautulli_url(url):
    parts = urllib.parse.urlsplit(str(url or "").strip())
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password \
            or parts.query or parts.fragment:
        raise SetupError("The Tautulli address must look like http://host:8181 (no username, ? or # parts).")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


CERT_HELP = (
    "Tautulli's https certificate couldn't be verified. This usually means it uses a self-signed "
    "certificate. Either use Tautulli's plain http address on your home network, or choose to skip "
    "the certificate check for this address (only do that on a network you trust)."
)


def tautulli_call(url, command, secret=None, verify_tls=True, **params):
    """Run one allowlisted Tautulli command. Returns the response dict; secrets are kept out of errors."""
    if command not in TAUTULLI_COMMANDS:
        raise SetupError(f"Blocked Tautulli command outside the allowlist: {command}")
    query = urllib.parse.urlencode({"cmd": command, **params})
    request = urllib.request.Request(f"{url}/api/v2?{query}", headers={"Accept": "application/json"})
    try:
        with _opener(verify_tls).open(request, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise TautulliLoginRequired(f"Tautulli asked for a login (HTTP {exc.code}).") from None
        raise SetupError(f"Tautulli returned HTTP {exc.code}. Check the address.") from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        if isinstance(getattr(exc, "reason", exc), ssl.SSLCertVerificationError):
            raise TautulliCertificateError(CERT_HELP) from None
        reason = str(getattr(exc, "reason", exc))
        if secret:
            reason = reason.replace(secret, "[hidden]")
        raise SetupError(f"Could not talk to Tautulli at {url}: {reason}") from None
    return data.get("response", {}) if isinstance(data, dict) else {}


def test_tautulli(url, api_key, verify_tls=True):
    """Return Tautulli's version if the address and key work; raise SetupError otherwise."""
    try:
        response = tautulli_call(url, "get_tautulli_info", secret=api_key, verify_tls=verify_tls,
                                 apikey=api_key)
    except TautulliLoginRequired:
        response = {}
    if response.get("result") != "success":
        raise SetupError("Tautulli rejected the API key. Copy it again from Tautulli: Settings → Web Interface → API.")
    return clean((response.get("data") or {}).get("tautulli_version")) or "?"


def save_tautulli(url, api_key, verify_tls=True):
    try:
        config = read_private(config_path()) or {}
    except DamagedFile:
        config = {}
    config.update({"tautulli_url": url, "tautulli_api_key": api_key})
    # Only ever turned off by the user's explicit choice; any earlier choice is replaced.
    if verify_tls:
        config.pop("tautulli_verify_tls", None)
    else:
        config["tautulli_verify_tls"] = False
    write_private(config_path(), config)


def cmd_tautulli_auto(args):
    """Ask Tautulli for its key directly. Only works when Tautulli has no login set."""
    url = clean_tautulli_url(args.url)
    verify = not args.skip_cert_check
    # Tautulli says "login needed" either as HTTP 401/403 or as an error message, depending on version.
    try:
        response = tautulli_call(url, "get_apikey", verify_tls=verify)
    except TautulliLoginRequired:
        response = {}
    except TautulliCertificateError:
        return {"step": "certificate_problem", "tautulli": url, "message": CERT_HELP}
    key = response.get("data") if response.get("result") == "success" else None
    if not isinstance(key, str) or not key.strip():
        return {
            "step": "needs_form",
            "tautulli": url,
            "reason": "Tautulli has a login, so the key can't be fetched automatically.",
            "certificate_check": verify,
        }
    key = key.strip()
    version = test_tautulli(url, key, verify)
    save_tautulli(url, key, verify)
    return {"step": "done", "tautulli": url, "tautulli_version": version, "how": "fetched automatically",
            "tautulli_has_no_login": True, "certificate_check": verify}


def cmd_tautulli(args):
    if not sys.stdin.isatty():
        raise SetupError(
            "Run this in your own terminal so the API key never passes through the chat: "
            f"python3 {os.path.abspath(__file__)} tautulli"
        )
    print("Add Tautulli to Cinemetric (optional; used for watch history and stats).", file=sys.stderr)
    url = clean_tautulli_url(input("Tautulli address, e.g. http://192.168.1.10:8181: "))
    api_key = getpass.getpass("Tautulli API key (Settings → Web Interface → API; hidden as you type): ").strip()
    if not api_key:
        raise SetupError("No API key entered.")
    verify = True
    try:
        version = test_tautulli(url, api_key)
    except TautulliCertificateError:
        print(CERT_HELP, file=sys.stderr)
        answer = input("Skip the certificate check for this Tautulli address? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            raise SetupError("Not saved. Try again with Tautulli's http address, or answer y to skip the check.")
        verify = False
        version = test_tautulli(url, api_key, verify_tls=False)
    save_tautulli(url, api_key, verify)
    return {"step": "done", "tautulli": url, "tautulli_version": version, "certificate_check": verify}


# ---------------------------------------------------------------- tautulli form

FORM_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Cinemetric: add Tautulli</title>
<style>
 :root {{ color-scheme: light dark; --bg:#f6f6f4; --card:#fff; --ink:#1d1d1b; --muted:#5f5f5a;
          --line:#d8d8d2; --accent:#c26a00; --ok:#1f7a3a; --err:#b3261e; }}
 @media (prefers-color-scheme: dark) {{ :root {{ --bg:#161614; --card:#20201d; --ink:#ededea;
          --muted:#a3a39c; --line:#3a3a35; --accent:#f0a030; --ok:#5cc27a; --err:#ff8a80; }} }}
 body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.5 system-ui, sans-serif; }}
 main {{ max-width:30rem; margin:3rem auto; padding:0 1rem; }}
 .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:1.5rem; }}
 h1 {{ font-size:1.3rem; margin:0 0 .25rem; }}
 p {{ color:var(--muted); margin:.25rem 0 1rem; }}
 label {{ display:block; font-weight:600; margin:1rem 0 .25rem; }}
 input {{ width:100%; box-sizing:border-box; padding:.6rem .7rem; font:inherit; color:inherit;
          background:transparent; border:1px solid var(--line); border-radius:8px; }}
 small {{ color:var(--muted); }}
 button {{ margin-top:1.25rem; width:100%; padding:.7rem; font:inherit; font-weight:600; border:0;
           border-radius:8px; background:var(--accent); color:#fff; cursor:pointer; }}
 .err {{ color:var(--err); font-weight:600; }} .ok {{ color:var(--ok); font-weight:600; }}
 .check {{ display:flex; gap:.6rem; align-items:flex-start; font-weight:400; margin-top:1rem; }}
 .check input {{ width:auto; margin-top:.3rem; }}
</style></head>
<body><main><div class="card">{body}</div></main></body></html>"""

FORM_BODY = """<h1>Add Tautulli to Cinemetric</h1>
<p>This page runs only on your computer. Your API key goes straight into Cinemetric's private
settings file and is never shown to Claude.</p>
{error}
<form method="post" action="{action}" autocomplete="off">
 <label for="url">Tautulli address</label>
 <input id="url" name="url" required placeholder="http://192.168.1.10:8181" value="{url}">
 <label for="key">API key</label>
 <input id="key" name="api_key" type="password" required spellcheck="false">
 <small>In Tautulli: Settings → Web Interface → API (turn on "Enable API" if it's off).</small>
 {cert_option}
 <button type="submit">Test and save</button>
</form>"""

CERT_OPTION = """<label class="check"><input type="checkbox" name="skip_cert_check" value="1">
 <span>Skip the certificate check for this address. Only do this if your Tautulli uses a self-signed
 certificate on a network you trust; otherwise use its plain <code>http://</code> address.</span></label>"""

DONE_BODY = """<h1 class="ok">Tautulli connected ✓</h1>
<p>Cinemetric can now use Tautulli (version {version}). You can close this tab and go back to Claude.</p>"""


def form_session_matches(session_hash):
    try:
        status = read_private(form_status_path())
    except SetupError:
        return False
    return bool(status) and status.get("session") == session_hash


def update_form_status(session_hash, **fields):
    try:
        status = read_private(form_status_path()) or {}
    except SetupError:
        status = {}
    if status.get("session") != session_hash:
        return False
    status.update(fields)
    write_private(form_status_path(), status)
    return True


def serve_tautulli_form(token, prefill_url):
    """Run the one-time form on 127.0.0.1 until it's used, cancelled, or expires."""
    session_hash = hashlib.sha256(token.encode()).hexdigest()
    path = f"/{token}"
    state = {"finished": False}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body):
            data = FORM_PAGE.format(body=body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
            self.end_headers()
            self.wfile.write(data)

        def _allowed(self):
            # Only exact local Host names (blocks DNS-rebinding tricks) and the secret path.
            port = self.server.server_address[1]
            host_ok = self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")
            path_ok = hmac.compare_digest(self.path.split("?")[0].encode(), path.encode())
            return host_ok and path_ok

        def _form(self, error="", url="", cert_option=False):
            msg = f'<p class="err">{html.escape(error)}</p>' if error else ""
            self._send(200, FORM_BODY.format(error=msg, action=html.escape(path),
                                             url=html.escape(url or prefill_url or ""),
                                             cert_option=CERT_OPTION if cert_option else ""))

        def do_GET(self):
            if not self._allowed():
                return self.send_error(404)
            self._form()

        def do_POST(self):
            if not self._allowed():
                return self.send_error(404)
            length = int(self.headers.get("Content-Length") or 0)
            if length > 8192:
                return self.send_error(413)
            fields = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            raw_url = (fields.get("url") or [""])[0]
            api_key = (fields.get("api_key") or [""])[0].strip()
            verify = (fields.get("skip_cert_check") or [""])[0] != "1"
            try:
                url = clean_tautulli_url(raw_url)
                if not api_key:
                    raise SetupError("Enter the API key.")
                version = test_tautulli(url, api_key, verify)
                if not form_session_matches(session_hash):
                    raise SetupError("This form was cancelled or replaced. Ask Claude for a new link.")
                save_tautulli(url, api_key, verify)
            except SetupError as exc:
                message = str(exc).replace(api_key, "[hidden]") if api_key else str(exc)
                update_form_status(session_hash, last_error=message)
                # The skip option only appears once a certificate problem has actually happened.
                return self._form(error=message, url=raw_url,
                                  cert_option=isinstance(exc, TautulliCertificateError))
            update_form_status(session_hash, state="done", tautulli=url, tautulli_version=version,
                               certificate_check=verify, last_error=None)
            self._send(200, DONE_BODY.format(version=html.escape(str(version))))
            state["finished"] = True

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1
    port = server.server_address[1]
    deadline = time.time() + FORM_LIFETIME_SECONDS
    if not update_form_status(session_hash, state="waiting", link=f"http://127.0.0.1:{port}{path}",
                              expires_at=int(deadline), pid=os.getpid()):
        return
    try:
        while not state["finished"] and time.time() < deadline:
            server.handle_request()
            if not form_session_matches(session_hash):
                return
        if not state["finished"]:
            update_form_status(session_hash, state="expired")
    finally:
        server.server_close()


def cmd_tautulli_form(args):
    prefill = clean_tautulli_url(args.url) if args.url else ""
    token = secrets.token_urlsafe(24)
    session_hash = hashlib.sha256(token.encode()).hexdigest()
    write_private(form_status_path(), {"session": session_hash, "state": "starting"})
    env = dict(os.environ, CINEMETRIC_FORM_TOKEN=token)
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "_tautulli-serve", "--url", prefill],
        env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True, close_fds=True,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        status = read_private(form_status_path()) or {}
        if status.get("session") == session_hash and status.get("link"):
            return {"step": "open_form", "form_url": status["link"],
                    "expires_in_minutes": FORM_LIFETIME_SECONDS // 60}
        time.sleep(0.2)
    raise SetupError("The local form didn't start. Use the terminal fallback instead (setup.py tautulli).")


def cmd_tautulli_serve(args):
    token = os.environ.pop("CINEMETRIC_FORM_TOKEN", "")
    if not token:
        raise SetupError("This command is started by tautulli-form; don't run it directly.")
    serve_tautulli_form(token, args.url)
    return {"step": "stopped"}


def cmd_tautulli_wait(args):
    deadline = time.time() + FINISH_WAIT_SECONDS
    while True:
        status = read_private(form_status_path())
        if not status:
            raise SetupError("No Tautulli form in progress. Run tautulli-form first.")
        state = status.get("state")
        if state == "done":
            os.remove(form_status_path())
            return {"step": "done", "tautulli": status.get("tautulli"),
                    "tautulli_version": status.get("tautulli_version"), "how": "form",
                    "certificate_check": status.get("certificate_check", True)}
        if state == "expired" or (status.get("expires_at") and time.time() > status["expires_at"] + 5):
            os.remove(form_status_path())
            return {"step": "expired", "message": "The form expired before it was used. Run tautulli-form again."}
        if time.time() > deadline:
            return {"step": "waiting", "last_error": status.get("last_error"),
                    "message": "Not saved yet. Finish the form in the browser, then run tautulli-wait again."}
        time.sleep(1)


def cmd_tautulli_remove(args):
    config = read_private(config_path()) or {}
    removed = [k for k in list(config) if k.startswith("tautulli_")]
    for key in removed:
        del config[key]
    if removed:
        write_private(config_path(), config)
    return {"step": "done", "removed": bool(removed)}


def cmd_cancel(args):
    # Removing the form's status file also makes a running Tautulli form shut itself down.
    for path in (pending_path(), form_status_path()):
        if os.path.exists(path):
            os.remove(path)
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
    auto = sub.add_parser("tautulli-auto")
    auto.add_argument("url")
    auto.add_argument("--skip-cert-check", action="store_true",
                      help="only after the user explicitly agrees: don't verify Tautulli's https certificate")
    form = sub.add_parser("tautulli-form")
    form.add_argument("--url", default="")
    sub.add_parser("tautulli-wait")
    serve = sub.add_parser("_tautulli-serve")
    serve.add_argument("--url", default="")
    args = parser.parse_args()

    handlers = {"start": cmd_start, "finish": cmd_finish, "select": cmd_select,
                "status": cmd_status, "cancel": cmd_cancel,
                "tautulli": cmd_tautulli, "tautulli-remove": cmd_tautulli_remove,
                "tautulli-auto": cmd_tautulli_auto, "tautulli-form": cmd_tautulli_form,
                "tautulli-wait": cmd_tautulli_wait, "_tautulli-serve": cmd_tautulli_serve}
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
