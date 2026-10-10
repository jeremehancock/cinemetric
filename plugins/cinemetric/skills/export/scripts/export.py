#!/usr/bin/env python3
"""Cinemetric export: save a Plex server's libraries and their issues as a spreadsheet workbook.

Writes one Excel workbook (.xlsx) with a tab for the server's details, the full list of movies and
shows (or episodes), and tabs for issues, episode gaps, files likely to transcode and subtitle
languages. The library list is read here; the other tabs come from running the matching Cinemetric
skills' scripts, as the dashboard does, so each tab says exactly what that skill says. Read-only
toward Plex. Uses only the Python standard library. Prints a short JSON summary to stdout (no
titles); errors go to stderr.

Safety rules: see openspec/specs/security/spec.md in the Cinemetric repository.
"""

import argparse
import datetime
import ipaddress
import json
import os
import re
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from xml.sax.saxutils import escape

VERSION = "0.32.0"
TIMEOUT_SECONDS = 60
MAX_TITLE_LENGTH = 120
LIBRARY_PAGE_SIZE = 500
SCRIPT_TIMEOUT_SECONDS = 1800

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.normpath(os.path.join(HERE, "..", ".."))

# The only Plex server paths this script may request. All of them are read with GET.
ALLOWED_PATHS = [
    re.compile(r"^/$"),
    re.compile(r"^/library/sections$"),
    re.compile(r"^/library/sections/\d+/all$"),
    re.compile(r"^/library/sections/\d+/collections$"),
    re.compile(r"^/library/collections/\d+/children$"),
    re.compile(r"^/:/prefs$"),
]

# Plex metadata type numbers used with /library/sections/{id}/all?type=N
TYPE_MOVIE, TYPE_SHOW, TYPE_EPISODE = 1, 2, 4
EXPORTED_TYPES = ("movie", "show")

TABS = ("Server", "Movies", "TV Shows", "Issues", "Episode gaps", "Playback", "Subtitles")
LIST_TABS = {"Movies": "movie", "TV Shows": "show"}
SKIPPABLE = {"server": "Server", "issues": "Issues", "gaps": "Episode gaps", "playback": "Playback",
             "subtitles": "Subtitles"}

# The other skills' scripts, the options they're run with and the tabs that use them. Lists go up
# to 500, the most each script allows; a note in the tab says how many more there were.
SOURCES = {
    "health": ("server-health", "server_health.py", ["--stuck-wait", "0"], ("Server",)),
    "library": ("library-report", "library_report.py",
                ["--recent", "0", "--growth-months", "0", "--music-examples", "0",
                 "--duplicate-examples", "500", "--upgrade-examples", "500"], ("Server", "Issues")),
    "gaps": ("episode-gaps", "episode_gaps.py", ["--limit", "500"], ("Episode gaps",)),
    # --days 0 skips the transcode history, so no people, devices or Tautulli request.
    "playback": ("playback-check", "playback_check.py", ["--limit", "500", "--days", "0"], ("Playback",)),
    "subtitles": ("subtitles-and-languages", "subtitles_and_languages.py", ["--limit", "500"], ("Subtitles",)),
}
TAKES_LIBRARY = ("library", "gaps", "playback", "subtitles")
ERROR_CODE = re.compile(r"^[A-Z_]+: ")
OWNER_ONLY_TEXT = "Only the server owner's account can see this."

# Everything worked out for a movie, show or episode; each list tab shows the columns that fit it.
ROW_FIELDS = (
    "Library", "Type", "Title", "Show", "Season", "Episode", "Year", "Added", "Length (min)", "Resolution",
    "Video codec", "Audio codec", "Audio channels", "Container", "Size (GB)", "Versions", "Unavailable",
    "Episodes", "Episodes unavailable", "Content rating", "Watched", "Episodes watched", "Last watched",
    "Collections",
)
MOVIE_COLUMNS = (
    "Library", "Title", "Year", "Added", "Length (min)", "Resolution", "Video codec", "Audio codec",
    "Audio channels", "Container", "Size (GB)", "Versions", "Unavailable", "Content rating", "Watched",
    "Last watched", "Collections",
)
SHOW_COLUMNS = (
    "Library", "Title", "Year", "Added", "Resolution", "Video codec", "Audio codec", "Audio channels",
    "Container", "Size (GB)", "Episodes", "Episodes unavailable", "Content rating", "Watched",
    "Episodes watched", "Last watched", "Collections",
)
EPISODE_COLUMNS = (
    "Library", "Show", "Season", "Episode", "Title", "Year", "Added", "Length (min)", "Resolution",
    "Video codec", "Audio codec", "Audio channels", "Container", "Size (GB)", "Versions", "Unavailable",
    "Content rating", "Watched", "Last watched", "Collections",
)
ISSUE_COLUMNS = ("Library", "Issue", "Title", "Show", "Season", "Episode", "Year", "Size (GB)", "Details")
GAP_COLUMNS = ("Library", "Show", "Year", "Season", "Missing episodes", "Missing count",
               "Unavailable episodes", "Note")
PLAYBACK_COLUMNS = ("Library", "Type", "Title", "Year", "Episodes", "Episodes flagged", "Resolution",
                    "Size (GB)", "Bitrate (kbps)", "Image subtitles", "TrueHD audio", "DTS audio",
                    "Over bitrate limit", "Details")
SUBTITLE_COLUMNS = ("Library", "Finding", "Type", "Title", "Year", "Episodes", "Episodes flagged",
                    "Which episodes", "Resolution", "Audio languages", "Subtitle languages", "Forced subtitles")
LIBRARY_TABLE_COLUMNS = ("Library", "Type", "Items", "Files", "Size (GB)", "Last scanned")

RESOLUTION_RANK = {"SD": 1, "720p": 2, "1080p": 3, "2K": 4, "4K": 5}
ISSUE_ORDER = ("File missing", "Unmatched", "No poster", "Duplicate copies", "In more than one library",
               "Low resolution")
CAUSES = ("image_subtitles", "truehd_audio", "dts_audio", "over_bitrate_limit")
FINDINGS = ("foreign_no_subtitles", "no_subtitles", "unknown_language")
LIBRARY_KINDS = {"movie": "Movies", "show": "TV", "artist": "Music", "photo": "Photos"}

WATCHED_NOTE = ("Watched status is for the Plex account Cinemetric is signed in with, not for everyone "
                "who uses the server.")

STREAMING_LABELS = (
    ("hardware_acceleration", "Hardware-accelerated transcoding"),
    ("hardware_encoding", "Hardware encoding"),
    ("video_transcoding_disabled", "Video transcoding"),
    ("remote_stream_limit_kbps", "Remote limit per stream (kbps, 0 means no limit)"),
    ("remote_total_upload_limit_kbps", "Remote upload limit in total (kbps, 0 means no limit)"),
    ("custom_transcoder_temp_folder", "Own folder for transcoder temporary files"),
)
MAINTENANCE_LABELS = (
    ("scan_on_folder_change", "Scan when a folder changes"),
    ("scheduled_scans_enabled", "Scheduled library scans"),
    ("scheduled_scan_interval_seconds", "Scheduled scan interval (seconds)"),
    ("empty_trash_after_scan", "Empty trash after every scan"),
    ("maintenance_start_hour", "Maintenance starts (hour of the day)"),
    ("maintenance_end_hour", "Maintenance ends (hour of the day)"),
)
WORTH_A_LOOK = {
    "update_available": "A Plex update is available",
    "remote_access_not_working": "Remote access isn't working",
    "scheduled_scans_not_running": "Scheduled library scans haven't run lately",
    "automatic_scans_off": "Automatic library scans are off",
    "important_maintenance_disabled": "Important maintenance tasks are switched off",
    "hardware_transcoding_off": "Hardware-accelerated transcoding is off",
    "video_transcoding_off": "Video transcoding is turned off",
    "remote_stream_limit_low": "The remote streaming limit is low",
}
# Worth-a-look items about this moment (a stream, CPU or memory use, a running task). A workbook is
# kept, so it holds only what describes the server itself.
MOMENT_KINDS = ("transcode_too_slow", "high_cpu", "high_memory", "task_not_progressing")
FINDING_LABELS = {
    "foreign_no_subtitles": "Audio in another language, no {} subtitles",
    "no_subtitles": "No {} subtitles",
    "unknown_language": "Tracks with no language set",
}


class ReportError(Exception):
    """An error with a message that is safe to show the user."""


# ---------------------------------------------------------------- config

def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "cinemetric", "config.json")


def read_config_file():
    path = config_path()
    if not os.path.exists(path):
        return {}
    info = os.stat(path)
    if os.name == "posix":
        if info.st_uid != os.getuid():
            raise ReportError(f"Refusing to read {path}: it is owned by another user.")
        if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise ReportError(
                f"Refusing to read {path}: other users can access it. Fix with: chmod 600 {path}"
            )
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ReportError(f"Could not read {path}: {exc.__class__.__name__}") from None
    if not isinstance(data, dict):
        raise ReportError(f"{path} must contain a JSON object.")
    return data


def load_config():
    """Return {"plex": (url, token, verify) or None, "tautulli": (url, key, verify) or None,
    "tautulli_problem": reason or None}.

    Environment variables win over the config file, and the file is only read when the
    environment leaves something missing. If Plex is fully set up from the environment, a
    problem with the file only makes Tautulli unavailable (with the reason) instead of failing.
    """
    env = os.environ.get
    plex_from_env = bool(env("PLEX_URL") and env("PLEX_TOKEN"))
    tautulli_from_env = bool(env("TAUTULLI_URL") and env("TAUTULLI_API_KEY"))
    data, problem = {}, None
    if not (plex_from_env and tautulli_from_env):
        try:
            data = read_config_file()
        except ReportError as exc:
            if not plex_from_env:
                raise
            problem = str(exc)

    plex_url = env("PLEX_URL") or data.get("plex_url")
    plex_token = env("PLEX_TOKEN") or data.get("plex_token")
    taut_url = env("TAUTULLI_URL") or data.get("tautulli_url")
    taut_key = env("TAUTULLI_API_KEY") or data.get("tautulli_api_key")

    config = {"plex": None, "tautulli": None, "tautulli_problem": problem}
    if plex_url and plex_token:
        # Plex from the environment keeps certificate checks on, like the other report scripts.
        verify = True if plex_from_env else data.get("verify_tls", True) is not False
        config["plex"] = (validate_url(plex_url, "plex_url"), str(plex_token).strip(), verify)
    if taut_url and taut_key:
        config["tautulli"] = (validate_url(taut_url, "tautulli_url"), str(taut_key).strip(),
                              data.get("tautulli_verify_tls", True) is not False)
    if not config["plex"] and not config["tautulli"]:
        raise ReportError(
            "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN)."
        )
    return config


def validate_url(url, name):
    parts = urllib.parse.urlsplit(str(url).strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ReportError(f"{name} must look like http://host:port or https://host")
    if parts.username or parts.password:
        raise ReportError(f"{name} must not contain a username or password.")
    if parts.query or parts.fragment:
        raise ReportError(f"{name} must not contain ? or # parts.")
    if parts.scheme == "http" and not looks_local(parts.hostname):
        print(
            f"warning: {name} uses plain http to a non-local address, so your credentials travel "
            "unencrypted. Prefer https for anything outside your home network.",
            file=sys.stderr,
        )
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def looks_local(host):
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return "." not in host or host.endswith((".local", ".lan", ".home.arpa", ".internal"))


# ---------------------------------------------------------------- http

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReportError(
            f"The server answered with a redirect (HTTP {code}). Cinemetric does not follow "
            "redirects so your credentials stay with your server. Use the final address instead."
        )


def build_opener(base_url, verify_tls):
    if base_url.startswith("https://") and not verify_tls:
        print("warning: TLS certificate checking is OFF for " + base_url, file=sys.stderr)
        context = ssl._create_unverified_context()
    else:
        context = ssl.create_default_context()
    return urllib.request.build_opener(_NoRedirect(), urllib.request.HTTPSHandler(context=context))


def fetch_json(opener, request, what, secret):
    def scrub(text):
        return str(text).replace(secret, "[hidden]") if secret else str(text)

    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise ReportError(f"{what} rejected the credentials (HTTP 401 Unauthorized).") from None
        raise ReportError(f"{what} returned HTTP {exc.code}.") from None
    except urllib.error.URLError as exc:
        raise ReportError(f"Could not reach {what}: {scrub(exc.reason)}") from None
    except (TimeoutError, OSError) as exc:
        raise ReportError(f"Network error talking to {what}: {scrub(exc)}") from None
    try:
        return json.loads(body)
    except ValueError:
        raise ReportError(f"{what} sent a response that was not JSON.") from None


class PlexClient:
    def __init__(self, base_url, token, verify_tls):
        self.base_url = base_url
        self._token = token
        self._opener = build_opener(base_url, verify_tls)

    def get(self, path, params=None, start=None, size=None):
        if not any(rule.match(path) for rule in ALLOWED_PATHS):
            raise ReportError(f"Blocked request to a path outside the allowlist: {path}")
        url = self.base_url + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {
            "Accept": "application/json",
            "X-Plex-Token": self._token,
            "X-Plex-Product": "Cinemetric",
            "X-Plex-Version": VERSION,
            "X-Plex-Client-Identifier": "cinemetric-export",
        }
        if start is not None:
            headers["X-Plex-Container-Start"] = str(start)
            headers["X-Plex-Container-Size"] = str(size)
        request = urllib.request.Request(url, headers=headers, method="GET")
        data = fetch_json(self._opener, request, f"the Plex server ({path})", self._token)
        return data.get("MediaContainer", {}) if isinstance(data, dict) else {}


# ---------------------------------------------------------------- helpers

def clean(text):
    """Titles and names are untrusted data: strip control characters and cap the length."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text or "")).strip()
    return text[:MAX_TITLE_LENGTH]


def clean_long(text):
    """Longer fixed text from a report (a limits sentence, an error reason): control characters
    removed, but not cut."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(text or "")).strip()


def as_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes")


def resolution_bucket(value):
    value = str(value or "").lower()
    if value in ("4k", "2160"):
        return "4K"
    if value == "2k":
        return "2K"
    if value == "1080":
        return "1080p"
    if value == "720":
        return "720p"
    if value in ("480", "576", "sd"):
        return "SD"
    return "unknown" if not value else value


def data_dir():
    if os.environ.get("CINEMETRIC_DATA_DIR"):
        return os.environ["CINEMETRIC_DATA_DIR"]
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "cinemetric")


def ensure_private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    if os.name == "posix":
        os.chmod(path, 0o700)


def two_places(size_bytes):
    return round(size_bytes / 1e9, 2)


def number(value):
    """A number from a report, or None when it isn't one."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def local_date(epoch):
    seconds = as_int(epoch, None)
    if not seconds:
        return None
    try:
        return datetime.date.fromtimestamp(seconds)
    except (OverflowError, OSError, ValueError):
        return None


def text_date(text):
    """The date at the start of "YYYY-MM-DD ..." text, or None."""
    try:
        return datetime.date(*(int(part) for part in str(text)[:10].split("-")))
    except (TypeError, ValueError):
        return None


def year_from(item):
    year = as_int(item.get("year"), None)
    if year:
        return year
    found = re.match(r"(\d{4})-", str(item.get("originallyAvailableAt") or ""))
    return int(found.group(1)) if found else None


def sort_title(item):
    return clean(item.get("titleSort") or item.get("title")).lower()


def number_ranges(numbers):
    """[3, 5, 6, 7] -> [[3, 3], [5, 7]]. Anything that isn't a whole number is left out."""
    groups = []
    for n in sorted(n for n in numbers if isinstance(n, int) and not isinstance(n, bool)):
        if groups and n == groups[-1][1] + 1:
            groups[-1][1] = n
        elif not groups or n != groups[-1][1]:
            groups.append([n, n])
    return groups


def range_text(pairs):
    """[[3, 3], [5, 7]] -> "3, 5-7"."""
    parts = []
    for pair in pairs or []:
        if isinstance(pair, (list, tuple)) and len(pair) == 2 and all(number(n) is not None for n in pair):
            first, last = int(pair[0]), int(pair[1])
            parts.append(str(first) if first == last else f"{first}-{last}")
    return ", ".join(parts)


def without_code(reason):
    reason = clean_long(reason)
    if reason.startswith("OWNER_ONLY"):
        return OWNER_ONLY_TEXT
    return ERROR_CODE.sub("", reason)


# ---------------------------------------------------------------- media deletion
#
# Shared helper: the same code is in every script that reads from Plex. Keep every copy in step.

def media_deletion_allowed(read_prefs):
    """Whether Plex's "Allow media deletion" setting is on: True, False, or None when it can't be
    told. read_prefs returns the /:/prefs answer. Only this one setting is looked at, since /:/prefs
    also holds values that must never be printed. Never raises: a failed check mustn't stop a report."""
    try:
        prefs = read_prefs()
        settings = prefs.get("Setting", []) if isinstance(prefs, dict) else []
        for setting in settings or []:
            if isinstance(setting, dict) and setting.get("id") == "allowMediaDeletion":
                value = str(setting.get("value")).strip().lower()
                return True if value in ("1", "true") else False if value in ("0", "false") else None
    except Exception:
        pass
    return None


# ---------------------------------------------------------------- where the file goes

def library_slug(names):
    parts = [re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-") for name in names]
    slug = "-".join(part for part in parts if part)[:60].strip("-")
    return slug or "library"


def default_name(libraries, tv, today):
    name = "plex-export"
    if libraries:
        name += "-" + library_slug(libraries)
    if tv == "episodes":
        name += "-episodes"
    return f"{name}-{today.isoformat()}.xlsx"


def resolve_output(args, today):
    """Returns (path, in_data_folder). Checked before Plex is contacted, so a file the user would
    rather keep stops the export straight away."""
    name = default_name(args.library, args.tv, today)
    if not args.output:
        return os.path.join(data_dir(), name), True
    path = os.path.expanduser(args.output)
    if os.path.isdir(path):
        target = os.path.join(path, name)
    else:
        if not path.lower().endswith(".xlsx"):
            raise ReportError("BAD_OUTPUT: --output must be a folder that exists or a file name ending "
                              "in .xlsx.")
        folder = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(folder):
            raise ReportError(f"BAD_OUTPUT: The folder {folder} doesn't exist.")
        target = path
    target = os.path.abspath(target)
    if os.path.isdir(target):
        raise ReportError(f"BAD_OUTPUT: {target} is a folder.")
    if os.path.exists(target) and not args.replace:
        raise ReportError(f"FILE_EXISTS: {target} already exists. Run again with --replace to replace it.")
    return target, False


def write_export(path, content, may_replace):
    """Write the workbook in one step, readable only by the user. The folder must exist already: a
    folder the user named keeps its own permissions. Without may_replace, a file that has appeared
    at the path since it was checked is left alone. Returns whether an earlier file was replaced."""
    folder = os.path.dirname(os.path.abspath(path))
    existed = os.path.exists(path)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".cinemetric-", suffix=".tmp")
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        if may_replace:
            os.replace(tmp, path)
            return existed
        try:
            os.link(tmp, path)
        except FileExistsError:
            raise ReportError(f"FILE_EXISTS: {path} already exists. Run again with --replace to replace it.") from None
        except (OSError, NotImplementedError):
            # No hard links here (some shared or Windows folders): check once more and move.
            if os.path.exists(path):
                raise ReportError(f"FILE_EXISTS: {path} already exists. Run again with --replace to replace it.") from None
            os.replace(tmp, path)
            return False
        os.remove(tmp)
        return False
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# ---------------------------------------------------------------- the workbook

# Characters XML 1.0 doesn't allow. A file containing one won't open.
NOT_IN_XML = re.compile("[^\u0009\u000a\u000d -퟿-�\U00010000-\U0010ffff]")
DATE_STYLE, BOLD_STYLE, DECIMAL_STYLE = 2, 1, 3
EXCEL_EPOCH = datetime.date(1899, 12, 30)


class Sheet:
    """One tab: rows of cells (text, numbers, dates or None), which rows are bold, and whether the
    first row is a row of column names (kept in view, with filter buttons)."""

    def __init__(self, name, columns=None):
        self.name = name
        self.rows = []
        self.bold = set()
        self.header = columns is not None
        self.data_rows = 0
        self.notes = []
        self.problem = None
        if columns:
            self.add(columns, bold=True, data=False)

    def add(self, cells, bold=False, data=True):
        if bold:
            self.bold.add(len(self.rows))
        self.rows.append(list(cells))
        if data:
            self.data_rows += 1

    def note(self, text):
        self.notes.append("Note: " + clean_long(text))

    def finished_rows(self):
        rows = list(self.rows)
        if self.notes:
            rows.append([])
            rows.extend([text] for text in self.notes)
        return rows


def column_letter(index):
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def xml_text(value):
    return escape(NOT_IN_XML.sub("", str(value)), {'"': "&quot;", "'": "&apos;"})


def cell_xml(ref, value, style):
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        value = "Yes" if value else "No"
    if isinstance(value, datetime.date):
        serial = (value - EXCEL_EPOCH).days
        return f'<c r="{ref}" s="{DATE_STYLE}"><v>{serial}</v></c>'
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            return ""
        s = f' s="{style or DECIMAL_STYLE}"' if isinstance(value, float) else (f' s="{style}"' if style else "")
        return f'<c r="{ref}"{s}><v>{value!r}</v></c>'
    # Text is always an inline string: a spreadsheet program shows it as written and never runs it.
    s = f' s="{style}"' if style else ""
    return f'<c r="{ref}" t="inlineStr"{s}><is><t xml:space="preserve">{xml_text(value)}</t></is></c>'


def sheet_xml(sheet, first):
    rows = sheet.finished_rows()
    width = max([len(row) for row in rows] or [1])
    sizes = [8] * width
    for r, row in enumerate(rows[:2000]):
        # Column names get room for their filter button as well.
        extra = 5 if sheet.header and r == 0 else 2
        for i, value in enumerate(row):
            if value is not None and not (sheet.notes and len(row) == 1 and str(value).startswith("Note: ")):
                sizes[i] = max(sizes[i], min(len(str(value)) + extra, 50))
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(sizes))
    pane = ('<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
            if sheet.header else "")
    selected = ' tabSelected="1"' if first else ""
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
           f'<sheetViews><sheetView workbookViewId="0"{selected}>{pane}</sheetView></sheetViews>',
           '<sheetFormatPr defaultRowHeight="15"/>', f"<cols>{cols}</cols>", "<sheetData>"]
    for r, row in enumerate(rows, start=1):
        style = BOLD_STYLE if (r - 1) in sheet.bold else 0
        cells = "".join(cell_xml(f"{column_letter(c)}{r}", value, style) for c, value in enumerate(row))
        out.append(f'<row r="{r}">{cells}</row>')
    out.append("</sheetData>")
    if sheet.header:
        out.append(f'<autoFilter ref="{filter_range(sheet)}"/>')
    out.append("</worksheet>")
    return "".join(out)


def filter_range(sheet):
    return f"A1:{column_letter(max(len(sheet.rows[0]), 1) - 1)}{max(len(sheet.rows), 1)}"


STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<numFmts count="2"><numFmt numFmtId="164" formatCode="yyyy-mm-dd"/>'
    '<numFmt numFmtId="165" formatCode="0.00"/></numFmts>'
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
    '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
    '<fills count="2"><fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill></fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
    '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
    '</styleSheet>'
)


def workbook_bytes(sheets):
    """The .xlsx file: a zip of a few XML parts, with nothing in it that can run or link out."""
    import io
    count = len(sheets)
    types = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, count + 1))
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{types}</Types>")
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>')
    sheet_list = "".join(f'<sheet name="{xml_text(s.name)}" sheetId="{i}" r:id="rId{i}"/>'
                         for i, s in enumerate(sheets, start=1))
    filters = "".join(
        f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
        f"'{xml_text(s.name)}'!{absolute(filter_range(s))}</definedName>"
        for i, s in enumerate(sheets) if s.header)
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<bookViews><workbookView activeTab="0"/></bookViews>'
        f"<sheets>{sheet_list}</sheets>"
        + (f"<definedNames>{filters}</definedNames>" if filters else "")
        + "</workbook>")
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{i}" '
                  'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                  f'Target="worksheets/sheet{i}.xml"/>' for i in range(1, count + 1))
        + f'<Relationship Id="rId{count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/></Relationships>')

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", STYLES)
        for i, sheet in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(sheet, i == 1))
    return buffer.getvalue()


def absolute(ref):
    """A1:X9 -> $A$1:$X$9."""
    return re.sub(r"([A-Z]+)(\d+)", r"$\1$\2", ref)


# ---------------------------------------------------------------- running the other reports

def run_source(name, extra):
    folder, script, options, _ = SOURCES[name]
    path = os.path.join(SKILLS_DIR, folder, "scripts", script)
    if not os.path.exists(path):
        return name, None, f"the {folder} script is missing"
    try:
        proc = subprocess.run(
            [sys.executable, path, *options, *extra], capture_output=True, text=True,
            timeout=SCRIPT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return name, None, f"{folder} took longer than {SCRIPT_TIMEOUT_SECONDS // 60} minutes"
    if proc.returncode != 0:
        errors = [line[7:] for line in proc.stderr.splitlines() if line.startswith("error: ")]
        return name, None, without_code(errors[-1]) if errors else f"{folder} failed"
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return name, None, f"{folder} produced unreadable output"
    return name, data, None


def needed_sources(tabs, has_tv):
    names = [name for name, (_, _, _, used_by) in SOURCES.items() if any(tab in tabs for tab in used_by)]
    return [name for name in names if name != "gaps" or has_tv]


def source_options(name, args):
    extra = []
    if name in TAKES_LIBRARY:
        for library in args.library or []:
            extra += ["--library", library]
    if name == "subtitles":
        for code in args.language or []:
            extra += ["--language", code]
    return extra


# ---------------------------------------------------------------- reading the libraries

def need_plex(config):
    if not config["plex"]:
        raise ReportError(
            "NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the "
            "cinemetric:setup skill (or set PLEX_URL and PLEX_TOKEN)."
        )
    return PlexClient(*config["plex"])


def get_all(client, section_id, type_number, extra=None):
    """Every item of one type in a section, fetched in pages."""
    path = f"/library/sections/{section_id}/all"
    params = {"type": type_number, **(extra or {})}
    items, start = [], 0
    while True:
        page = client.get(path, params, start=start, size=LIBRARY_PAGE_SIZE)
        batch = page.get("Metadata", []) or []
        items.extend(batch)
        total = as_int(page.get("totalSize", page.get("size", len(items))))
        start += len(batch)
        if not batch or start >= total:
            return items


def get_pages(client, path):
    """Every entry of a collection's listing, fetched in pages. These listings don't always give
    totalSize, so a short page also means the end."""
    items, start = [], 0
    while True:
        page = client.get(path, start=start, size=LIBRARY_PAGE_SIZE)
        batch = page.get("Metadata", []) or []
        items.extend(batch)
        start += len(batch)
        total = page.get("totalSize")
        if len(batch) < LIBRARY_PAGE_SIZE or (total is not None and start >= as_int(total)):
            return items


def choose_sections(sections, wanted):
    exportable = [s for s in sections if s.get("type") in EXPORTED_TYPES]
    if wanted:
        names = {name.lower() for name in wanted}
        matched = [s for s in sections if str(s.get("title", "")).lower() in names]
        if not matched:
            listed = ", ".join(clean(s.get("title")) for s in exportable) or "none"
            raise ReportError(f"No library matched --library. Movie and TV libraries: {listed}.")
        if not any(s.get("type") in EXPORTED_TYPES for s in matched):
            raise ReportError("Only movie and TV libraries can be exported.")
        sections = matched
    included = [s for s in sections if s.get("type") in EXPORTED_TYPES]
    skipped = [{"name": clean(s.get("title")), "type": clean(s.get("type"))}
               for s in sections if s.get("type") not in EXPORTED_TYPES]
    return included, skipped


def available_media(item):
    return [m for m in item.get("Media", []) or [] if isinstance(m, dict) and not m.get("deletedAt")]


def best_media(versions):
    if not versions:
        return None
    return max(versions, key=lambda m: (RESOLUTION_RANK.get(resolution_bucket(m.get("videoResolution")), 0),
                                        as_int(m.get("bitrate"))))


def media_details(item):
    """(size in bytes, versions Plex can find, details of the best one) for a movie or episode."""
    versions = available_media(item)
    size = sum(as_int(part.get("size")) for m in versions for part in m.get("Part", []) or [])
    best = best_media(versions)
    details = {"resolution": None, "video": None, "audio": None, "channels": None, "container": None}
    if best:
        bucket = resolution_bucket(best.get("videoResolution"))
        details = {
            "resolution": None if bucket == "unknown" else clean(bucket),
            "video": clean(best.get("videoCodec")) or None,
            "audio": clean(best.get("audioCodec")) or None,
            "channels": as_int(best.get("audioChannels"), None),
            "container": clean(best.get("container")) or None,
        }
    return size, len(versions), details


def most_common(values, better=None):
    counts = Counter(v for v in values if v not in (None, ""))
    if not counts:
        return None
    top = max(counts.values())
    tied = [v for v, n in counts.items() if n == top]
    if better:
        return max(tied, key=better)
    return min(tied, key=lambda v: str(v).lower())


def watched(item):
    if as_int(item.get("viewCount")) >= 1:
        return "Yes"
    return "Partly" if as_int(item.get("viewOffset")) > 0 else "No"


def show_watched(item):
    total, seen = as_int(item.get("leafCount")), as_int(item.get("viewedLeafCount"))
    if total > 0 and seen >= total:
        return "Yes"
    return "Partly" if seen > 0 else "No"


def unmatched(item):
    guid = str(item.get("guid") or "")
    return not guid or guid.startswith("local://")


def minutes(item):
    duration = as_int(item.get("duration"), None)
    return int(round(duration / 60000)) if duration else None


def read_collections(client, section, unavailable, name):
    """Collection names per rating key held directly by a collection (a movie, show, season or
    episode)."""
    names = defaultdict(set)
    try:
        listing = get_pages(client, f"/library/sections/{section['key']}/collections")
    except ReportError as exc:
        unavailable.append({"library": name, "part": "collections", "reason": str(exc)})
        return names
    failed, reason = 0, None
    for col in listing:
        title = clean(col.get("title"))
        try:
            children = get_pages(client, f"/library/collections/{as_int(col.get('ratingKey'))}/children")
        except ReportError as exc:
            failed, reason = failed + 1, reason or str(exc)
            continue
        for child in children:
            if title:
                names[str(child.get("ratingKey"))].add(title)
    if failed:
        # Counted, not named: the summary holds no collection names.
        unavailable.append({"library": name, "part": "collection contents", "collections": failed,
                            "reason": reason})
    return names


def joined_collections(names):
    return "; ".join(sorted(names, key=lambda n: (n.lower(), n))) or None


def read_library(client, section, tv, unavailable):
    """Returns (rows for the Movies or TV Shows tab, issue rows) for one library, or None if its listing
    couldn't be read."""
    name = clean(section.get("title"))
    kind = section.get("type")
    try:
        if kind == "movie":
            movies, shows, episodes = get_all(client, section["key"], TYPE_MOVIE), [], []
        else:
            movies = []
            shows = get_all(client, section["key"], TYPE_SHOW)
            episodes = get_all(client, section["key"], TYPE_EPISODE)
    except ReportError as exc:
        unavailable.append({"library": name, "part": "listing", "reason": str(exc)})
        return None
    collections = read_collections(client, section, unavailable, name)
    rows, issues = [], []

    for movie in sorted(movies, key=lambda m: (sort_title(m), year_from(m) or 0)):
        size, versions, d = media_details(movie)
        title = clean(movie.get("title"))
        rows.append([name, "Movie", title, None, None, None, year_from(movie), local_date(movie.get("addedAt")),
                     minutes(movie), d["resolution"], d["video"], d["audio"], d["channels"], d["container"],
                     two_places(size), versions, "No" if versions else "Yes", None, None,
                     clean(movie.get("contentRating")) or None, watched(movie), None,
                     local_date(movie.get("lastViewedAt")),
                     joined_collections(collections.get(str(movie.get("ratingKey")), ()))])
        add_title_issues(issues, name, movie, title, year_from(movie), versions)

    show_by_key = {str(s.get("ratingKey")): s for s in shows}
    per_show = defaultdict(list)
    for episode in episodes:
        per_show[str(episode.get("grandparentRatingKey") or "")].append(episode)

    def episode_collections(episode):
        found = set()
        for key in (episode.get("ratingKey"), episode.get("parentRatingKey"), episode.get("grandparentRatingKey")):
            found |= collections.get(str(key), set())
        return found

    def show_order(key):
        show = show_by_key.get(key)
        if show:
            return (sort_title(show), year_from(show) or 0)
        eps = per_show.get(key) or [{}]
        return (clean(eps[0].get("grandparentTitle")).lower(), 0)

    def episode_order(episode):
        season, number = as_int(episode.get("parentIndex"), None), as_int(episode.get("index"), None)
        return (season is None, season or 0, number is None, number or 0)

    for key in sorted(set(show_by_key) | set(per_show), key=show_order):
        show = show_by_key.get(key)
        eps = sorted(per_show.get(key, []), key=episode_order)
        details = []
        for episode in eps:
            size, versions, d = media_details(episode)
            details.append((episode, size, versions, d))
            show_title = clean(episode.get("grandparentTitle") or (show or {}).get("title"))
            if not versions:
                issues.append([name, "File missing", clean(episode.get("title")), show_title,
                               as_int(episode.get("parentIndex"), None), as_int(episode.get("index"), None),
                               year_from(episode), None, None])
            if tv == "episodes":
                rows.append([name, "Episode", clean(episode.get("title")), show_title,
                             as_int(episode.get("parentIndex"), None), as_int(episode.get("index"), None),
                             year_from(episode), local_date(episode.get("addedAt")), minutes(episode),
                             d["resolution"], d["video"], d["audio"], d["channels"], d["container"],
                             two_places(size), versions, "No" if versions else "Yes", None, None,
                             clean(episode.get("contentRating")) or None, watched(episode), None,
                             local_date(episode.get("lastViewedAt")),
                             joined_collections(episode_collections(episode))])
        if show is None:
            continue
        title = clean(show.get("title"))
        add_title_issues(issues, name, show, title, year_from(show), None)
        if tv == "episodes":
            continue
        found = set(collections.get(key, set()))
        for episode, _, _, _ in details:
            found |= episode_collections(episode)
        found_d = [d for _, _, versions, d in details if versions]
        pick = lambda field, better=None: most_common([d[field] for d in found_d], better)
        rows.append([name, "Show", title, None, None, None, year_from(show), local_date(show.get("addedAt")), None,
                     pick("resolution", lambda r: RESOLUTION_RANK.get(r, 0)), pick("video"), pick("audio"),
                     pick("channels"), pick("container"), two_places(sum(size for _, size, _, _ in details)),
                     None, None, len(details), sum(1 for _, _, versions, _ in details if not versions),
                     clean(show.get("contentRating")) or None, show_watched(show),
                     as_int(show.get("viewedLeafCount")), local_date(show.get("lastViewedAt")),
                     joined_collections(found)])
    return rows, issues


def add_title_issues(issues, library, item, title, year, versions):
    """Issues found in the listing itself, by the same rules as library-report."""
    if versions == 0:
        issues.append([library, "File missing", title, None, None, None, year, None, None])
    if unmatched(item):
        issues.append([library, "Unmatched", title, None, None, None, year, None, None])
    if not item.get("thumb"):
        issues.append([library, "No poster", title, None, None, None, year, None, None])


# ---------------------------------------------------------------- the tabs from reports

def yes_no(value):
    return "On" if value else "Off"


def server_sheet(root, health, library, errors, args, now):
    sheet = Sheet("Server")

    def heading(text):
        sheet.add([text, None], bold=True, data=False)

    def row(item, value):
        if value is not None and value != "":
            sheet.add([item, value])

    heading("Export")
    row("Made", time.strftime("%Y-%m-%d %H:%M", time.localtime(now)))
    row("Cinemetric version", VERSION)
    row("Tabs left out", ", ".join(SKIPPABLE[s] for s in args.skip) if args.skip else "None")
    row("Watched status", WATCHED_NOTE)

    server = (health or {}).get("server") or {}
    heading("Server")
    row("Name", clean(server.get("name") or root.get("friendlyName")))
    row("Version", clean(server.get("version") or root.get("version")))
    row("Platform", clean(server.get("platform") or root.get("platform")))
    if health:
        update = server.get("update")
        if isinstance(update, dict):
            available = update.get("update_available")
            row("Update available", (f"Yes ({clean(update.get('available_version'))})"
                                     if available and update.get("available_version") else
                                     "Yes" if available else "No"))
        remote = server.get("remote_access")
        if isinstance(remote, dict) and remote.get("state"):
            state = clean(remote.get("state"))
            row("Remote access", "Working" if state == "mapped" else f"Not working ({state})")

        for title, values, labels in (
                ("Streaming settings", server.get("streaming_settings"), STREAMING_LABELS),
                ("Maintenance settings", (health.get("background") or {}).get("maintenance_settings"),
                 MAINTENANCE_LABELS)):
            if isinstance(values, dict) and values:
                heading(title)
                for key, label in labels:
                    if key in values:
                        value = values[key]
                        if key == "video_transcoding_disabled" and isinstance(value, bool):
                            value = not value  # shown as whether video transcoding is allowed
                        row(label, yes_no(value) if isinstance(value, bool) else number(value))

        heading("Worth a look")
        items = [i for i in health.get("worth_a_look") or []
                 if isinstance(i, dict) and i.get("kind") not in MOMENT_KINDS]
        for item in items:
            sheet.add([WORTH_A_LOOK.get(item.get("kind"), clean(item.get("kind"))), worth_value(item) or None])
        if not items:
            sheet.add(["Nothing", None])

        missing = [u for u in health.get("unavailable") or [] if isinstance(u, dict)]
        if missing:
            heading("Not available")
            for part in missing:
                row(clean(part.get("part")).capitalize() or "Part", without_code(part.get("reason")))
    else:
        reason = errors.get("health") or "server-health wasn't run"
        sheet.note(f"Server details couldn't be read: {reason}")
        sheet.problem = reason

    sheet.add([], data=False)
    sheet.add(LIBRARY_TABLE_COLUMNS, bold=True, data=False)
    if library:
        scans = {clean(s.get("name")): text_date(s.get("last_scanned"))
                 for s in ((health or {}).get("background") or {}).get("library_scans") or [] if isinstance(s, dict)}
        for lib in library.get("libraries") or []:
            counts = lib.get("counts") or {}
            media = lib.get("media") or {}
            name = clean(lib.get("name"))
            sheet.add([name, LIBRARY_KINDS.get(lib.get("type"), clean(lib.get("type"))),
                       number(next(iter(counts.values()), None)), number(media.get("files")),
                       number(media.get("size_gb")), scans.get(name)])
    else:
        reason = errors.get("library") or "library-report wasn't run"
        sheet.note(f"Library sizes couldn't be read: {reason}")
        sheet.problem = "; ".join(p for p in (sheet.problem, reason) if p)
    return sheet


def worth_value(item):
    kind = item.get("kind")
    if kind == "update_available":
        return clean(item.get("version"))
    if kind == "remote_access_not_working":
        return clean(item.get("state"))
    if kind == "scheduled_scans_not_running":
        libraries = ", ".join(clean(n) for n in item.get("libraries") or [])
        return f"{libraries} (more than {as_int(item.get('days'))} days)"
    if kind == "important_maintenance_disabled":
        return ", ".join(clean(t) for t in item.get("tasks") or [])
    if kind == "remote_stream_limit_low":
        return f"{as_int(item.get('limit_kbps'))} kbps"
    return ""


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


LABEL_YEAR = re.compile(r"^(.*) \((\d{4})\)$")


def title_and_year(label):
    """library-report labels movies "Title (1998)"; split the year into its own column."""
    label = clean(label)
    found = LABEL_YEAR.match(label)
    return (found.group(1), int(found.group(2))) if found else (label, None)


def copies_text(copies):
    parts = []
    for copy in copies or []:
        if isinstance(copy, dict):
            bits = [resolution_bucket(copy.get("resolution")) if copy.get("resolution") else "",
                    clean(copy.get("video_codec")),
                    f"{number(copy.get('gb'))} GB" if number(copy.get("gb")) is not None else ""]
            parts.append(" ".join(b for b in bits if b and b != "unknown"))
    return "; ".join(p for p in parts if p)


def episode_count(examples):
    return sum(as_int(e.get("episodes"), 1) or 1 for e in examples if isinstance(e, dict))


def issues_sheet(own_issues, library_order, library, error):
    sheet = Sheet("Issues", ISSUE_COLUMNS)
    rows = list(own_issues)
    notes = []
    if library:
        for lib in library.get("libraries") or []:
            name = clean(lib.get("name"))
            unit = "episodes" if lib.get("type") == "show" else "titles"
            dup = lib.get("duplicates") or {}
            examples = [e for e in dup.get("examples") or [] if isinstance(e, dict)]
            for e in examples:
                details = (plural(as_int(e.get("episodes")), "episode") + " with more than one copy"
                           if "episodes" in e else copies_text(e.get("copies")))
                title, year = title_and_year(e.get("title")) if "episodes" not in e else (clean(e.get("title")), None)
                rows.append([name, "Duplicate copies", title, None, None, None, year,
                             number(e.get("extra_gb")), details or None])
            left = as_int(dup.get("titles")) - (episode_count(examples) if unit == "episodes" else len(examples))
            if left > 0:
                notes.append((ISSUE_ORDER.index("Duplicate copies"),
                              f"{left} more {unit} with duplicate copies in {name} weren't listed."))
            up = lib.get("upgrades") or {}
            examples = [e for e in up.get("examples") or [] if isinstance(e, dict)]
            for e in examples:
                if "episodes" in e:
                    by = e.get("by_resolution") or {}
                    split = ", ".join(f"{as_int(n)} {clean(r)}" for r, n in by.items() if as_int(n))
                    details = f"{plural(as_int(e.get('episodes')), 'episode')}: {split}" if split else None
                    size, title, year = None, clean(e.get("title")), None
                else:
                    details = ", ".join(b for b in (resolution_bucket(e.get("resolution")),
                                                    clean(e.get("video_codec"))) if b and b != "unknown")
                    size = number(e.get("gb"))
                    title, year = title_and_year(e.get("title"))
                rows.append([name, "Low resolution", title, None, None, None, year, size, details or None])
            left = as_int(up.get("titles")) - (episode_count(examples) if unit == "episodes" else len(examples))
            if left > 0:
                notes.append((ISSUE_ORDER.index("Low resolution"),
                              f"{left} more low-resolution {unit} in {name} weren't listed."))
        cross = library.get("cross_library_duplicates") or {}
        examples = [e for e in cross.get("examples") or [] if isinstance(e, dict)]
        for e in examples:
            libs = e.get("libraries") or []
            if libs and isinstance(libs[0], dict):
                names = "; ".join(clean(l.get("library")) for l in libs)
                details = "; ".join(
                    " ".join(b for b in (clean(l.get("library")) + ":", resolution_bucket(l.get("resolution")),
                                         f"{number(l.get('gb'))} GB" if number(l.get("gb")) is not None else "")
                             if b and b != "unknown") for l in libs)
            else:
                names = "; ".join(clean(l) for l in libs)
                details = plural(as_int(e.get("episodes")), "episode")
            title, year = title_and_year(e.get("title")) if "episodes" not in e else (clean(e.get("title")), None)
            rows.append([names, "In more than one library", title, None, None, None, year,
                         number(e.get("extra_gb")), details or None])
        left = as_int(cross.get("titles")) - len(examples)
        if left > 0 and not any("episodes" in e for e in examples):
            notes.append((ISSUE_ORDER.index("In more than one library"),
                          f"{left} more titles in more than one library weren't listed."))
    else:
        reason = error or "library-report wasn't run"
        sheet.problem = reason
        notes.append((ISSUE_ORDER.index("Duplicate copies"),
                      f"Duplicate copies, titles in more than one library and low-resolution titles "
                      f"couldn't be read: {reason}"))

    order = {name: i for i, name in enumerate(library_order)}
    rows.sort(key=lambda r: (ISSUE_ORDER.index(r[1]), order.get(r[0], len(order)),
                             str(r[3] or r[2] or "").lower(), r[4] if isinstance(r[4], int) else 0,
                             r[5] if isinstance(r[5], int) else 0, str(r[2] or "").lower()))
    for r in rows:
        sheet.add(r)
    if not rows and not notes:
        sheet.note("No issues were found.")
    for _, text in sorted(notes, key=lambda n: n[0]):
        sheet.note(text)
    return sheet


def report_failed(sheet, reason):
    sheet.problem = reason
    sheet.note(f"This tab couldn't be built: {reason}")
    return sheet


def gaps_sheet(gaps, error, has_tv):
    sheet = Sheet("Episode gaps", GAP_COLUMNS)
    if not has_tv:
        sheet.note("No TV library was included, so episode gaps weren't checked.")
        return sheet
    if not gaps:
        return report_failed(sheet, error or "episode-gaps wasn't run")
    notes = []
    for lib in gaps.get("libraries") or []:
        name = clean(lib.get("name"))
        for show in lib.get("listed") or []:
            if not isinstance(show, dict):
                continue
            title, year = clean(show.get("title")), number(show.get("year"))
            seasons = []
            for season in show.get("seasons") or []:
                if not isinstance(season, dict):
                    continue
                missing = season.get("missing") or []
                count = sum(as_int(p[1]) - as_int(p[0]) + 1 for p in missing
                            if isinstance(p, (list, tuple)) and len(p) == 2)
                unavailable = range_text(number_ranges(season.get("unavailable") or []))
                note = "Numbering carries on from the previous season" if season.get("continues_numbering") else None
                seasons.append([name, title, year, number(season.get("season")), range_text(missing) or None,
                                count or None, unavailable or None, note])
            for number_ in show.get("missing_seasons") or []:
                seasons.append([name, title, year, number(number_), "Whole season", None, None, None])
            seasons.sort(key=lambda r: r[3] if isinstance(r[3], int) else 0)
            first = as_int(show.get("first_season"), 1)
            if seasons and first > 1:
                start = f"Starts at season {first}"
                seasons[0][7] = f"{start}; {seasons[0][7]}" if seasons[0][7] else start
            for r in seasons:
                sheet.add(r)
        more = as_int(lib.get("more_shows"))
        if more > 0:
            notes.append(f"{more} more shows with gaps in {name} weren't listed.")
    if not sheet.data_rows:
        sheet.note("No gaps were found.")
    for text in notes:
        sheet.note(text)
    if gaps.get("limits"):
        sheet.note(gaps["limits"])
    return sheet


def playback_sheet(playback, error):
    sheet = Sheet("Playback", PLAYBACK_COLUMNS)
    if not playback:
        return report_failed(sheet, error or "playback-check wasn't run")
    notes = []
    for lib in playback.get("libraries") or []:
        name = clean(lib.get("name"))
        for title in lib.get("listed") or []:
            if not isinstance(title, dict):
                continue
            if lib.get("type") == "movie":
                for f in title.get("files") or []:
                    if not isinstance(f, dict):
                        continue
                    causes = set(f.get("causes") or [])
                    bucket = resolution_bucket(f.get("resolution"))
                    details = []
                    langs = ", ".join(clean(code) for code in f.get("image_subtitle_languages") or [])
                    if "image_subtitles" in causes and langs:
                        details.append(f"Image subtitles: {langs}")
                    audio = f.get("audio")
                    if isinstance(audio, dict) and audio.get("codec"):
                        codec = " ".join(clean(b) for b in (audio.get("codec"), audio.get("profile")) if b)
                        other = "has" if audio.get("common_alternative") else "no"
                        details.append(f"Audio: {codec} ({other} common alternative track)")
                    sheet.add([name, "Movie", clean(title.get("title")), number(title.get("year")), None, None,
                               None if bucket == "unknown" else clean(bucket), number(f.get("size_gb")),
                               number(f.get("bitrate_kbps"))]
                              + [1 if cause in causes else None for cause in CAUSES]
                              + ["; ".join(details) or None])
            else:
                sheet.add([name, "Show", clean(title.get("title")), number(title.get("year")),
                           number(title.get("episodes")), number(title.get("episodes_flagged")), None, None, None]
                          + [as_int(title.get(cause)) or None for cause in CAUSES] + [None])
        more = as_int(lib.get("more"))
        if more > 0:
            notes.append(f"{more} more titles in {name} weren't listed.")
    if not sheet.data_rows:
        sheet.note("No files likely to transcode were found.")
    limit = playback.get("bitrate_limit")
    if isinstance(limit, dict) and number(limit.get("kbps")):
        sheet.note(f"Files were checked against a remote bitrate limit of {as_int(limit.get('kbps'))} kbps.")
    else:
        sheet.note("No remote bitrate limit is set, so files weren't checked against one.")
    if playback.get("bitrate_limit_problem"):
        sheet.note(playback["bitrate_limit_problem"])
    for text in notes:
        sheet.note(text)
    if playback.get("limits"):
        sheet.note(playback["limits"])
    return sheet


def language_names(codes, names):
    out = []
    for code in codes:
        code = clean(code)
        label = "Unknown" if code == "unknown" else clean(names.get(code) or code)
        if label and label not in out:
            out.append(label)
    return ", ".join(out) or None


def which_episodes(title):
    parts = []
    for season in title.get("seasons") or []:
        if isinstance(season, dict):
            text = ", ".join("E" + chunk for chunk in range_text(season.get("episodes")).split(", ") if chunk)
            if text:
                parts.append(f"S{as_int(season.get('season'))} {text}")
    for episode in title.get("unnumbered") or []:
        if isinstance(episode, dict):
            aired = f" ({clean(episode.get('aired'))})" if episode.get("aired") else ""
            parts.append(clean(episode.get("title")) + aired)
    more = as_int(title.get("ranges_more")) + as_int(title.get("unnumbered_more"))
    if more:
        parts.append(f"and {more} more")
    return "; ".join(parts) or None


def subtitles_sheet(subs, error):
    sheet = Sheet("Subtitles", SUBTITLE_COLUMNS)
    if not subs:
        return report_failed(sheet, error or "subtitles-and-languages wasn't run")
    names = {str(k): v for k, v in (subs.get("language_names") or {}).items()}
    libraries = [lib for lib in subs.get("libraries") or [] if isinstance(lib, dict)]
    notes = []
    for finding in FINDINGS:
        for lib in libraries:
            name = clean(lib.get("name"))
            codes = ((lib.get("language") or {}).get("codes")) or []
            label = FINDING_LABELS[finding].format(
                " or ".join(language_names([c], names) or clean(c) for c in codes) or "your language")
            for title in (lib.get("listed") or {}).get(finding) or []:
                if not isinstance(title, dict):
                    continue
                if lib.get("type") == "movie":
                    for f in title.get("files") or []:
                        if not isinstance(f, dict):
                            continue
                        bucket = resolution_bucket(f.get("resolution"))
                        sheet.add([name, label, "Movie", clean(title.get("title")), number(title.get("year")),
                                   None, None, None, None if bucket == "unknown" else clean(bucket),
                                   language_names(f.get("audio_languages") or [], names),
                                   language_names(f.get("subtitle_languages") or [], names),
                                   language_names(f.get("forced_subtitle_languages") or [], names)])
                else:
                    audio = title.get("audio_languages") or {}
                    ordered = sorted(audio, key=lambda c: (-as_int(audio[c]), str(c)))
                    sheet.add([name, label, "Show", clean(title.get("title")), number(title.get("year")),
                               number(title.get("episodes")), number(title.get("episodes_flagged")),
                               which_episodes(title), None, language_names(ordered, names), None, None])
            more = as_int((lib.get("more") or {}).get(finding))
            if more > 0:
                notes.append(f"{more} more titles in {name} under \"{label}\" weren't listed.")
    if not sheet.data_rows:
        sheet.note("Nothing was found.")
    for lib in libraries:
        if lib.get("language_problem"):
            sheet.note(f"{clean(lib.get('name'))}: {lib['language_problem']}")
    for text in notes:
        sheet.note(text)
    if subs.get("limits"):
        sheet.note(subs["limits"])
    return sheet


# ---------------------------------------------------------------- building the export

def build(config, args, now=None):
    now = time.time() if now is None else now
    today = datetime.date.fromtimestamp(now)
    path, in_data_folder = resolve_output(args, today)
    client = need_plex(config)
    root = client.get("/")
    sections = client.get("/library/sections").get("Directory", []) or []
    included, skipped = choose_sections(sections, args.library)
    has_tv = any(s.get("type") == "show" for s in included)
    kinds = {s.get("type") for s in included}
    tabs = [tab for tab in TABS if tab not in {SKIPPABLE[s] for s in args.skip}
            and (tab not in LIST_TABS or LIST_TABS[tab] in kinds)]

    # The other reports run while this script reads the libraries.
    sources = needed_sources(tabs, has_tv)
    pool = ThreadPoolExecutor(max_workers=max(len(sources), 1))
    futures = [pool.submit(run_source, name, source_options(name, args)) for name in sources]
    try:
        unavailable, library_rows, own_issues, libraries = [], [], [], []
        for section in included:
            result = read_library(client, section, args.tv, unavailable)
            name = clean(section.get("title"))
            if result is None:
                continue
            rows, issues = result
            library_rows.extend(rows)
            own_issues.extend(issues)
            libraries.append({"name": name, "kind": section.get("type"), "rows": len(rows)})
        if not libraries:
            reasons = "; ".join(u["reason"] for u in unavailable if u.get("part") == "listing")
            raise ReportError(f"No library could be read, so nothing was saved: {reasons}")
        results = [future.result() for future in futures]
    finally:
        pool.shutdown(wait=False)
    data = {name: payload for name, payload, _ in results}
    errors = {name: err for name, _, err in results if err}

    sheets = []
    for tab in tabs:
        if tab == "Server":
            sheets.append(server_sheet(root, data.get("health"), data.get("library"), errors, args, now))
        elif tab in LIST_TABS:
            failed = [(clean(s.get("title")), u["reason"]) for s in included if s.get("type") == LIST_TABS[tab]
                      for u in unavailable if u.get("part") == "listing" and u.get("library") == clean(s.get("title"))]
            sheets.append(list_sheet(tab, library_rows, args.tv, failed))
        elif tab == "Issues":
            sheets.append(issues_sheet(own_issues, [lib["name"] for lib in libraries], data.get("library"),
                                       errors.get("library")))
        elif tab == "Episode gaps":
            sheets.append(gaps_sheet(data.get("gaps"), errors.get("gaps"), has_tv))
        elif tab == "Playback":
            sheets.append(playback_sheet(data.get("playback"), errors.get("playback")))
        elif tab == "Subtitles":
            sheets.append(subtitles_sheet(data.get("subtitles"), errors.get("subtitles")))

    if in_data_folder:
        ensure_private_dir(os.path.dirname(path))
    content = workbook_bytes(sheets)
    replaced = write_export(path, content, in_data_folder or args.replace)
    return {
        "cinemetric_version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
        "server": {"name": clean(root.get("friendlyName")), "version": clean(root.get("version"))},
        "media_deletion_allowed": media_deletion_allowed(lambda: client.get("/:/prefs")),
        "output": path,
        "in_data_folder": in_data_folder,
        "replaced": replaced,
        "size_bytes": len(content),
        "tv_rows": args.tv,
        "tabs": [{"name": s.name, "rows": s.data_rows, "problem": s.problem} for s in sheets],
        "skipped_tabs": [SKIPPABLE[s] for s in args.skip],
        "libraries": libraries,
        "skipped_libraries": skipped,
        "unavailable": unavailable,
        "watched_note": WATCHED_NOTE,
    }


def list_sheet(tab, rows, tv, failed):
    """The Movies or TV Shows tab: the rows of that kind, with the columns that fit them. `failed`
    holds (library, reason) for the libraries of this kind whose listing couldn't be read."""
    if tab == "Movies":
        wanted, columns = ("Movie",), MOVIE_COLUMNS
    else:
        wanted, columns = ("Show", "Episode"), EPISODE_COLUMNS if tv == "episodes" else SHOW_COLUMNS
    sheet = Sheet(tab, columns)
    for row in rows:
        fields = dict(zip(ROW_FIELDS, row))
        if fields["Type"] in wanted:
            sheet.add([fields[c] for c in columns])
    for name, reason in failed:
        sheet.note(f"{name} couldn't be read: {reason}")
    if not sheet.data_rows and not failed:
        sheet.note("The included libraries are empty.")
    if failed and not sheet.data_rows:
        sheet.problem = "; ".join(reason for _, reason in failed)
    return sheet


def check(config):
    root = need_plex(config).get("/")
    return {"ok": True, "plex": {"server": clean(root.get("friendlyName")), "version": root.get("version")}}


def skip_value(value):
    value = str(value).strip().lower()
    if value not in SKIPPABLE:
        raise argparse.ArgumentTypeError(
            f"can't skip '{value}'; choose from {', '.join(SKIPPABLE)} (the Movies and TV Shows tabs are always included)")
    return value


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Save your Plex libraries and their issues as a spreadsheet workbook (.xlsx). Read-only.")
    parser.add_argument("--check", action="store_true", help="only test the connection")
    parser.add_argument("--library", action="append", help="export only this library (repeatable)")
    parser.add_argument("--tv", choices=("shows", "episodes"), default="shows",
                        help="one row per show (default) or per episode")
    parser.add_argument("--language", action="append",
                        help="language to check subtitles against on the Subtitles tab (repeatable)")
    parser.add_argument("--skip", action="append", type=skip_value, default=[],
                        help="leave out a tab: server, issues, gaps, playback or subtitles (repeatable)")
    parser.add_argument("--output", help="folder or .xlsx file to save to (default: Cinemetric's data folder)")
    parser.add_argument("--replace", action="store_true", help="replace the file if it's already there")
    args = parser.parse_args(argv)
    args.skip = list(dict.fromkeys(args.skip))
    return args


def main():
    args = parse_args()
    try:
        config = load_config()
        result = check(config) if args.check else build(config, args)
    except ReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    json.dump(result, sys.stdout, indent=1, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
