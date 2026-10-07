#!/usr/bin/env python3
"""Cinemetric dashboard: one HTML page combining the library report, server status, the last 30 days
of watching, unwatched titles, episode gaps, playback problems and who the server is shared with.

It runs the other Cinemetric report scripts (so it has exactly their read-only behaviour and
safety rules), then writes a self-contained HTML page: no scripts and no external requests (a
Content Security Policy blocks them). Uses only the Python standard library.

It never publishes anything: when the user wants the dashboard online, Claude publishes the page as
a private claude.ai page. This script only remembers that choice and the page's link.

  dashboard.py [--output PATH] [--hide-names | --show-names]   build the dashboard
  dashboard.py destination local|online|both                    save where the dashboard goes
  dashboard.py online-page --url LINK | --forget                save or forget the claude.ai page link
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

VERSION = "0.24.0"
SCRIPT_TIMEOUT_SECONDS = 1800

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.normpath(os.path.join(HERE, "..", ".."))
SOURCES = {
    "library": ("library-report", "library_report.py", ["--snapshot-items"]),
    # The dashboard doesn't show the stuck task check, so it skips the wait.
    "health": ("server-health", "server_health.py", ["--stuck-wait", "0", "--snapshot-items"]),
    "watch": ("watch-activity", "watch_activity.py", ["--days", "30", "--top", "8", "--recent", "10"]),
    "sharing": ("users-and-shares", "users_and_shares.py", ["--snapshot-items"]),
    # Each library lists its 10 largest, so the 10 largest overall are always among them.
    "unwatched": ("unwatched", "unwatched.py", ["--limit", "10"]),
    # Same reasoning: each library lists its 10 shows with the most gaps.
    "episode_gaps": ("episode-gaps", "episode_gaps.py", ["--limit", "10"]),
    # Counts and the transcode history only; the page lists no files.
    "playback": ("playback-check", "playback_check.py", ["--limit", "0"]),
}
# Reports whose snapshot blocks are saved, and whose since_snapshot feeds the "Since" section.
SNAPSHOT_AREAS = ("library", "health", "sharing")
CHANGES_SCRIPT = os.path.join(SKILLS_DIR, "changes", "scripts", "changes.py")
CHANGE_EXAMPLES = 5
UNWATCHED_TITLES_LIMIT = 10
GAP_SHOWS_LIMIT = 10
PLAYBACK_GROUPS_LIMIT = 5
GAPS_PER_SHOW = 5
SHARING_PEOPLE_LIMIT = 20
TRENDS_TIMEOUT_SECONDS = 120
# The count drawn for each library in Trends: the first of these the library has.
TREND_COUNTS = (("movies", "movie"), ("episodes", "episode"), ("albums", "album"), ("photos", "photo"))
ERROR_CODE = re.compile(r"^[A-Z_]+: ")


class DashboardError(Exception):
    """An error with a message that is safe to show the user."""


def data_dir():
    if os.environ.get("CINEMETRIC_DATA_DIR"):
        return os.environ["CINEMETRIC_DATA_DIR"]
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "cinemetric")


def default_output():
    return os.path.join(data_dir(), "dashboard.html")


def ensure_private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    if os.name == "posix":
        os.chmod(path, 0o700)


# ---------------------------------------------------------------- collecting

def run_source(name):
    folder, script, extra = SOURCES[name]
    path = os.path.join(SKILLS_DIR, folder, "scripts", script)
    if not os.path.exists(path):
        return name, None, f"the {folder} script is missing"
    try:
        proc = subprocess.run(
            [sys.executable, path, *extra], capture_output=True, text=True,
            timeout=SCRIPT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return name, None, f"{folder} took longer than {SCRIPT_TIMEOUT_SECONDS // 60} minutes"
    if proc.returncode != 0:
        errors = [line[7:] for line in proc.stderr.splitlines() if line.startswith("error: ")]
        return name, None, errors[-1] if errors else f"{folder} failed"
    try:
        return name, json.loads(proc.stdout), None
    except ValueError:
        return name, None, f"{folder} produced unreadable output"


def collect():
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        results = list(pool.map(run_source, SOURCES))
    data = {name: payload for name, payload, _ in results}
    errors = {name: err for name, _, err in results if err}
    if len(errors) == len(SOURCES):
        first = next(iter(errors.values()))
        raise DashboardError(first if "NOT_CONFIGURED" in first else f"Nothing could be collected: {first}")
    return data, errors


def save_snapshot(data):
    """Hand the reports to the changes script to save today's snapshot. Returns the date, or None.

    Then drop the snapshot blocks: they're for saving only and never go on the page."""
    reports = {area: data[area] for area in SNAPSHOT_AREAS if data.get(area)}
    saved = None
    if reports and os.path.exists(CHANGES_SCRIPT):
        try:
            proc = subprocess.run([sys.executable, CHANGES_SCRIPT, "save"], input=json.dumps(reports),
                                  capture_output=True, text=True, timeout=120)
            if proc.returncode == 0:
                saved = json.loads(proc.stdout).get("snapshot_saved")
        except (OSError, ValueError, AttributeError, subprocess.TimeoutExpired):
            saved = None
    for report in reports.values():
        if isinstance(report, dict):
            report.pop("snapshot", None)
    return saved if isinstance(saved, str) else None


def snapshot_server_id(data):
    """The server id the reports' snapshot blocks agree on, or None. Read before they are dropped."""
    ids = {str((data[area].get("snapshot") or {}).get("server_id") or "") for area in SNAPSHOT_AREAS
           if isinstance(data.get(area), dict) and isinstance(data[area].get("snapshot"), dict)}
    return ids.pop() if len(ids) == 1 and "" not in ids else None


def load_trends(server_id):
    """Counts and sizes from every saved snapshot, from the changes script. None if unavailable."""
    if not server_id or not os.path.exists(CHANGES_SCRIPT):
        return None
    try:
        proc = subprocess.run([sys.executable, CHANGES_SCRIPT, "trends", "--server-id", server_id],
                              capture_output=True, text=True, timeout=TRENDS_TIMEOUT_SECONDS)
        if proc.returncode != 0:
            return None
        trends = json.loads(proc.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return trends if isinstance(trends, dict) else None


# ---------------------------------------------------------------- formatting helpers

def e(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def num(value):
    try:
        return f"{int(round(float(value))):,}"
    except (TypeError, ValueError):
        return "–"


def size(gb):
    try:
        gb = float(gb)
    except (TypeError, ValueError):
        return "–"
    return f"{gb / 1000:.1f} TB" if gb >= 1000 else f"{gb:.0f} GB"


def hours(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "–"
    if value >= 240:
        return f"{value / 24:.1f} days"
    if value <= 0:
        return "0 min"
    if value < 1:
        return f"{max(1, round(value * 60))} min"
    return f"{value:.0f} h"


def plural(n, word):
    return f"{num(n)} {word}{'' if n == 1 else 's'}"


def people_count(n):
    return "1 person" if n == 1 else f"{num(n)} people"


def short_date(iso):
    try:
        t = time.strptime(iso[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return e(iso)
    return f"{time.strftime('%b', t)} {t.tm_mday}"


def month_year(iso):
    try:
        t = time.strptime(iso[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return e(iso)
    return time.strftime("%b %Y", t)


def friendly_now():
    t = time.localtime()
    hour = t.tm_hour % 12 or 12
    return f"{time.strftime('%a %b', t)} {t.tm_mday}, {t.tm_year} at {hour}:{t.tm_min:02d} {'AM' if t.tm_hour < 12 else 'PM'}"


STATUS_ICON = {"good": "✓", "warning": "!", "critical": "✕", "unknown": "?"}


def pill(level, label):
    return (f'<span class="pill pill-{level}"><span class="pill-icon" aria-hidden="true">'
            f'{STATUS_ICON[level]}</span>{e(label)}</span>')


# ---------------------------------------------------------------- sections

def attention_items(health, library):
    items = []
    for w in (health or {}).get("worth_a_look", []) or []:
        kind = w.get("kind")
        if kind == "update_available":
            items.append(("warning", "Plex update available", f"Version {w.get('version')} is ready to install."))
        elif kind == "remote_access_not_working":
            items.append(("critical", "Remote access isn't working",
                          "People outside your home network can't connect directly."))
        elif kind == "scheduled_scans_not_running":
            items.append(("warning", "Scheduled scans aren't running",
                          "Not scanned recently: " + ", ".join(w.get("libraries") or []) + "."))
        elif kind == "automatic_scans_off":
            items.append(("warning", "Automatic library scans are off",
                          "New files only appear after a manual scan."))
        elif kind == "important_maintenance_disabled":
            items.append(("warning", "Maintenance tasks are off", ", ".join(w.get("tasks") or []) + "."))

    unavailable = unmatched = 0
    for lib in (library or {}).get("libraries", []) or []:
        unavailable += (lib.get("media") or {}).get("unavailable_files", 0) or 0
        unmatched += (lib.get("housekeeping") or {}).get("unmatched_count", 0) or 0
    if unavailable:
        items.append(("warning", plural(unavailable, "file") + " Plex can't find",
                      "Usually a moved or deleted file, or a drive that isn't mounted."))
    if unmatched:
        items.append(("warning", plural(unmatched, "unmatched item"),
                      "These have no proper title, poster or description yet."))
    return items


def overall_status(health, items):
    if not health:
        return "unknown", "Health unknown"
    if any(level == "critical" for level, _, _ in items):
        return "critical", "Needs attention"
    if items:
        return "warning", "Mostly fine"
    return "good", "Healthy"


def tile(label, value, note=""):
    note_html = f'<span class="tile-note">{note}</span>' if note else ""
    return (f'<div class="tile"><span class="tile-label">{e(label)}</span>'
            f'<span class="tile-value">{value}</span>{note_html}</div>')


def kpi_row(library, health, watch):
    tiles = []
    if library:
        t = library.get("totals") or {}
        tiles.append(tile("Library", size(t.get("size_gb")), f"{num(t.get('files'))} files"))
    if watch:
        t = watch.get("totals") or {}
        tiles.append(tile(f"Plays, {watch.get('period_days')} days", num(t.get("plays")),
                          plural(t.get("active_users") or 0, "viewer")))
        if t.get("watch_hours") is not None:
            tiles.append(tile("Watch time", hours(t.get("watch_hours")), "same period"))
    return f'<section class="tiles" aria-label="Summary">{"".join(tiles)}</section>' if tiles else ""


def card(title, body, extra_class="", aside=""):
    aside_html = f'<span class="card-aside">{aside}</span>' if aside else ""
    return (f'<section class="card {extra_class}"><header class="card-head"><h2>{e(title)}</h2>'
            f'{aside_html}</header>{body}</section>')


def unavailable_note(what, reason):
    return f'<p class="muted">Couldn\'t load {e(what)}: {e(reason)}</p>'


def server_card(health, items, error):
    if not health:
        return card("Server", unavailable_note("server health", error))
    s = health.get("server") or {}
    rows = [("Version", e(s.get("version")))]
    update = s.get("update")
    if update:
        rows.append(("Updates", pill("warning", f"{update.get('available_version')} available")
                     if update.get("update_available") else pill("good", "Up to date")))
    remote = s.get("remote_access")
    if remote:
        rows.append(("Remote access", pill("good", "Working") if remote.get("state") == "mapped"
                     else pill("critical", f"Not working ({remote.get('state')})")))
    kv = "".join(f"<li><span>{label}</span><span>{value}</span></li>" for label, value in rows)

    if items:
        attn = "".join(
            f'<li class="attn attn-{level}"><span class="attn-icon" aria-hidden="true">{STATUS_ICON[level]}</span>'
            f'<div><strong>{e(title)}</strong><span class="muted">{e(detail)}</span></div></li>'
            for level, title, detail in items)
        attn_html = f'<h3>Needs a look</h3><ul class="attn-list">{attn}</ul>'
    else:
        attn_html = '<p class="all-clear">' + pill("good", "Nothing needs attention") + "</p>"
    return card("Server", f'<ul class="kv">{kv}</ul>{attn_html}')


def nice_step(peak, ticks=4):
    """A round tick step (1, 2, 5, 10, 20, 50...) so every axis label is a whole, round number."""
    raw = max(peak, 1) / ticks
    magnitude = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 1
    for step in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        value = step * magnitude
        if value >= raw and value == int(value):
            return int(value)
    return 10 * magnitude


def daily_chart(daily):
    if not daily:
        return ""
    bars = []
    for d in daily:
        plays = d.get("plays", 0)
        tip = f"{short_date(d.get('date'))}: {plural(plays, 'play')}"
        if d.get("hours") is not None and plays:
            tip += f", {hours(d['hours'])}"
        bars.append({"value": plays, "label": short_date(d.get("date")), "tip": tip})
    aria = f"Plays per day over the last {len(daily)} days"
    # Static SVG text scales with the drawing, so draw a wide and a narrow version and let CSS
    # pick one; labels then stay a readable size on both desktop and phone.
    return (bar_chart(bars, 720, 200, 6, "chart chart-wide", aria)
            + bar_chart(bars, 360, 180, 3, "chart chart-narrow", aria))


def month_label(key, fmt):
    """'2026-03' formatted with fmt, e.g. '%b' -> 'Mar'."""
    try:
        t = time.strptime(f"{key}-01", "%Y-%m-%d")
    except (TypeError, ValueError):
        return e(key)
    return time.strftime(fmt, t)


def added_size(gb):
    """Like size(), but keeps a decimal for small amounts so a quiet month doesn't read as 0 GB."""
    try:
        return f"{float(gb):.1f} GB" if float(gb) < 10 else size(gb)
    except (TypeError, ValueError):
        return "–"


def growth_chart(months):
    bars = []
    for i, m in enumerate(months):
        key = str(m.get("month") or "")
        added = m.get("added", 0)
        when = month_label(key, "%b %Y")
        if i == len(months) - 1:
            when += " so far"
        bars.append({"value": m.get("gb", 0), "label": month_label(key, "%b"), "year": key[:4],
                     "year_label": month_label(key, "%b '%y"),
                     "tip": f"{when}: {added_size(m.get('gb'))}, {plural(added, 'item')}"})
    aria = f"Storage added per month over the last {len(months)} months"
    return (bar_chart(bars, 720, 200, len(bars), "chart chart-wide", aria, tick=size, left=52)
            + bar_chart(bars, 360, 180, 4, "chart chart-narrow", aria, tick=size, left=52))


def bar_chart(bars, w, h, label_count, css_class, aria, tick=num, left=36):
    """An inline SVG bar chart. Each bar has a value, an axis label (already safe HTML) and a tooltip.

    The tallest bar is highlighted, and tick values are shown with tick(). Bars may also carry a
    "year" and a "year_label": the first label drawn in each new year then uses year_label, so the
    year shows up even when the label for January is skipped on a narrow chart.
    """
    bottom, top = 24, 10
    plot_w, plot_h = w - left - 8, h - bottom - top
    peak = max(b["value"] for b in bars)
    step = nice_step(peak)
    ymax = step * 4
    n = len(bars)
    slot = plot_w / n
    bar_w = max(slot - 2, 1)
    parts = [f'<svg class="{css_class}" viewBox="0 0 {w} {h}" role="img" aria-label="{e(aria)}">']
    for i in range(5):
        value = step * i
        y = top + plot_h - plot_h * i / 4
        cls = "baseline" if i == 0 else "grid"
        parts.append(f'<line class="{cls}" x1="{left}" x2="{w - 8}" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{tick(value)}</text>')
    label_every = max(1, round(n / label_count))
    shown_year = None
    for i, b in enumerate(bars):
        x = left + i * slot + 1
        bh = plot_h * b["value"] / ymax
        y = top + plot_h - bh
        if bh > 0:
            r = min(4, bar_w / 2, bh)
            path = (f"M{x:.1f},{top + plot_h:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
                    f"H{x + bar_w - r:.1f} Q{x + bar_w:.1f},{y:.1f} {x + bar_w:.1f},{y + r:.1f} "
                    f"V{top + plot_h:.1f} Z")
            peak_cls = " bar-peak" if b["value"] == peak else ""
            parts.append(f'<path class="bar{peak_cls}" d="{path}"><title>{e(b["tip"])}</title></path>')
        # A full-height, invisible hit area so thin or empty bars still show their tooltip.
        parts.append(f'<rect class="hit" x="{x - 1:.1f}" y="{top}" width="{slot:.1f}" height="{plot_h}">'
                     f'<title>{e(b["tip"])}</title></rect>')
        if i % label_every == 0 and (n - 1 - i) >= label_every / 2 or i == n - 1:
            label = b["label"]
            if b.get("year") and b["year"] != shown_year:
                label, shown_year = b["year_label"], b["year"]
            parts.append(f'<text class="tick" x="{x + bar_w / 2:.1f}" y="{h - 6}" text-anchor="middle">'
                         f'{label}</text>')
    parts.append("</svg>")
    return "".join(parts)


def day_number(iso):
    """Days since 1970 for a YYYY-MM-DD date, so points can be placed by date. None if not a date."""
    try:
        return int(time.mktime(time.strptime(str(iso)[:10], "%Y-%m-%d")) // 86400 + 0.5)
    except (TypeError, ValueError, OverflowError):
        return None


def trend_scale(values):
    """Round axis bounds and step around the values, which needn't start at zero."""
    lo, hi = min(values), max(values)
    step = nice_step(hi - lo, ticks=3) if hi > lo else nice_step(max(abs(hi) / 10, 1), ticks=1)
    ymin = (lo // step) * step
    steps = max(1, -(-(hi - ymin) // step))
    return ymin, ymin + step * steps, step, int(steps)


def line_chart(points, w, h, css_class, aria, tick=num, left=44, labels=3):
    """An inline SVG line chart. points: dicts with "day" (day number), "date", "value" (or None)
    and "tip", oldest first, with at least two values.

    Points are placed by date, so a longer gap between snapshots is a longer gap on the chart.
    A None value has no point and breaks the line. Each point has a tooltip."""
    bottom, top, right = 24, 10, 12
    plot_w, plot_h = w - left - right, h - bottom - top
    first, last = points[0]["day"], points[-1]["day"]
    ymin, ymax, step, steps = trend_scale([p["value"] for p in points if p["value"] is not None])
    x = lambda p: left + plot_w * (p["day"] - first) / max(last - first, 1)
    y = lambda v: top + plot_h - plot_h * (v - ymin) / (ymax - ymin)
    parts = [f'<svg class="{css_class}" viewBox="0 0 {w} {h}" role="img" aria-label="{e(aria)}">']
    for i in range(steps + 1):
        value = ymin + step * i
        cls = "baseline" if i == 0 else "grid"
        parts.append(f'<line class="{cls}" x1="{left}" x2="{w - right}" y1="{y(value):.1f}" y2="{y(value):.1f}"/>')
        parts.append(f'<text class="tick" x="{left - 6}" y="{y(value) + 4:.1f}" text-anchor="end">{tick(value)}</text>')
    path, drawing = [], False
    for p in points:
        if p["value"] is None:
            drawing = False
            continue
        path.append(f'{"L" if drawing else "M"}{x(p):.1f},{y(p["value"]):.1f}')
        drawing = True
    parts.append(f'<path class="trend-line" d="{" ".join(path)}"/>')
    for i, p in enumerate(points):
        if p["value"] is None:
            continue
        cx, cy = f"{x(p):.1f}", f'{y(p["value"]):.1f}'
        last_cls = " trend-last" if i == len(points) - 1 else ""
        parts.append(f'<circle class="trend-dot{last_cls}" cx="{cx}" cy="{cy}" r="2.5"/>')
        # A larger, invisible hit area so the tooltip is easy to reach.
        parts.append(f'<circle class="hit" cx="{cx}" cy="{cy}" r="8"><title>{e(p["tip"])}</title></circle>')
    # Date labels: the first and last, then evenly spaced ones that don't crowd those.
    wanted = [0, len(points) - 1]
    for k in range(1, labels - 1):
        target = first + (last - first) * k / (labels - 1)
        wanted.append(min(range(len(points)), key=lambda i: abs(points[i]["day"] - target)))
    placed = []
    for i in wanted:
        if all(abs(x(points[i]) - x(points[j])) >= plot_w / (labels * 1.6) for j in placed):
            placed.append(i)
    for i in placed:
        anchor = "start" if i == 0 else "end" if i == len(points) - 1 else "middle"
        parts.append(f'<text class="tick" x="{x(points[i]):.1f}" y="{h - 6}" text-anchor="{anchor}">'
                     f'{short_date(points[i]["date"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def ranked(title, rows, label_key, hide=False):
    rows = [r for r in rows or [] if r.get(label_key)]
    if not rows or hide:
        return ""
    top_plays = max(r.get("plays", 0) for r in rows) or 1
    items = []
    for r in rows:
        width = 100 * r.get("plays", 0) / top_plays
        # Watch time arrives rounded to a tenth of an hour, so 0 means "a few minutes": show plays only.
        extra = f" · {hours(r['hours'])}" if r.get("hours") else ""
        items.append(
            f'<li><div class="rank-line"><span class="rank-name">{e(r.get(label_key))}</span>'
            f'<span class="mono">{num(r.get("plays"))}{extra}</span></div>'
            f'<div class="rank-track"><div class="rank-bar" style="width:{width:.1f}%"></div></div></li>')
    return f'<div class="ranked"><h3>{e(title)}</h3><ol>{"".join(items)}</ol></div>'


def watch_section(watch, hide_names, error):
    if not watch:
        return card("Watch activity", unavailable_note("watch activity", error), "wide")
    source = ("From Tautulli" if watch.get("source") == "tautulli"
              else "From Plex's own history (play counts only)")
    t = watch.get("trend") or {}
    earlier, recent = t.get("earlier_half_plays", 0), t.get("recent_half_plays", 0)
    if earlier and recent > earlier * 1.15:
        trend = "Busier in the second half of the period."
    elif earlier and recent < earlier * 0.85:
        trend = "Quieter in the second half of the period."
    else:
        trend = "Steady across the period."
    by_type = watch.get("plays_by_type") or {}
    types = " · ".join(f"{e(k.title() if k != 'tv' else 'TV')} {num(v)}" for k, v in
                       sorted(by_type.items(), key=lambda kv: -kv[1]) if v)

    chart = (f'<div class="chart-block"><div class="chart-head"><h3>Plays per day</h3>'
             f'<span class="muted">{e(trend)}</span></div>{daily_chart(watch.get("daily"))}'
             f'<p class="muted small">{types}</p></div>')

    lists = "".join([
        ranked("Top shows", watch.get("top_shows"), "title"),
        ranked("Top movies", watch.get("top_movies"), "title"),
        ranked("Top music", watch.get("top_music"), "title"),
        ranked("Top viewers", watch.get("top_users"), "user", hide=hide_names),
        ranked("Devices", watch.get("top_platforms"), "platform"),
    ])

    recent_rows = []
    for p in watch.get("recent_plays") or []:
        who = "" if hide_names else f'<span class="who">{e(p.get("user"))}</span>'
        recent_rows.append(f'<li><span class="mono muted">{e((p.get("when") or "")[5:])}</span>'
                           f'<span class="recent-title">{who}{e(p.get("title"))}</span></li>')
    recent_html = (f'<div class="ranked"><h3>Recently watched</h3><ul class="recent">{"".join(recent_rows)}'
                   f'</ul></div>') if recent_rows else ""

    return card("Watch activity", f'{chart}<div class="lists">{lists}</div>{recent_html}', "wide",
                aside=e(source))


QUALITY_ORDER = [("4K", "q-4k"), ("1080p", "q-1080"), ("720p", "q-720"), ("SD", "q-sd")]


def quality_bar(resolution):
    total = sum(resolution.values())
    if not total:
        return ""
    segments, known = [], 0
    for label, cls in QUALITY_ORDER:
        count = resolution.get(label, 0)
        known += count
        if count:
            pct = 100 * count / total
            segments.append(f'<span class="seg {cls}" style="width:{pct:.2f}%" '
                            f'title="{label}: {num(count)} files ({pct:.0f}%)"></span>')
    other = total - known
    if other:
        pct = 100 * other / total
        segments.append(f'<span class="seg q-other" style="width:{pct:.2f}%" '
                        f'title="Other: {num(other)} files ({pct:.0f}%)"></span>')
    return f'<div class="qbar">{"".join(segments)}</div>'


def count_text(counts):
    order = ["movies", "shows", "episodes", "artists", "albums", "tracks", "photos"]
    return ", ".join(f"{num(counts[k])} {k}" for k in order if counts.get(k) is not None)


def library_section(library, error):
    if not library:
        return card("Library", unavailable_note("the library report", error), "wide")
    rows = []
    for lib in library.get("libraries") or []:
        media = lib.get("media") or {}
        res = media.get("resolution") or {}
        total = sum(res.values())
        four_k = f"{100 * res.get('4K', 0) / total:.0f}%" if total else "–"
        rows.append(
            f'<tr><th scope="row">{e(lib.get("name"))}</th><td>{e(count_text(lib.get("counts") or {}))}</td>'
            f'<td class="num">{size(media.get("size_gb"))}</td><td class="num">{four_k}</td>'
            f'<td class="qcell">{quality_bar(res)}</td></tr>')
    legend = "".join(f'<span><i class="swatch {cls}"></i>{label}</span>' for label, cls in QUALITY_ORDER)
    legend += '<span><i class="swatch q-other"></i>Other</span>'
    table = (f'<div class="legend" aria-label="Video quality colors">{legend}</div>'
             f'<div class="table-wrap"><table><thead><tr><th scope="col">Library</th><th scope="col">Contents</th>'
             f'<th scope="col" class="num">Size</th><th scope="col" class="num">4K</th>'
             f'<th scope="col">Video quality</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')

    added = []
    for lib in library.get("libraries") or []:
        for item in lib.get("recently_added") or []:
            added.append((item.get("added") or "", item.get("title"), lib.get("name")))
    added.sort(key=lambda a: a[0], reverse=True)
    added_html = "".join(f'<li><span class="mono muted">{e(a[0][5:])}</span>'
                         f'<span class="recent-title">{e(a[1])}<span class="muted"> · {e(a[2])}</span>'
                         f'</span></li>' for a in added[:10])
    added_block = (f'<div class="ranked"><h3>Recently added</h3><ul class="recent">{added_html}</ul></div>'
                   if added_html else "")
    return card("Library", f'{table}{growth_block(library.get("growth"))}<div class="lists two">{added_block}</div>',
                "wide")


def growth_block(growth):
    months = (growth or {}).get("months") or []
    if not months:
        return ""
    period = f"the last {plural(len(months), 'month')}" if len(months) > 1 else "this month"
    if not any(m.get("added") for m in months):
        return f'<p class="muted">Nothing was added in {period}.</p>'
    total = f"{added_size(growth.get('gb'))}, {plural(growth.get('added', 0), 'item')} in {period}"
    return (f'<div class="chart-block"><div class="chart-head"><h3>Storage added per month</h3>'
            f'<span class="muted">{e(total)}</span></div>{growth_chart(months)}</div>')


def unwatched_section(unwatched, error):
    if not unwatched:
        reason = ERROR_CODE.sub("", error or "")
        return card("Unwatched", unavailable_note("the unwatched report", reason), "wide")
    months = unwatched.get("months")
    period = f"{num(months)} {'month' if months == 1 else 'months'}"
    totals = unwatched.get("totals") or {}
    libraries = [lib for lib in unwatched.get("libraries") or [] if lib.get("items")]
    if not totals.get("unwatched"):
        return card("Unwatched", f'<p class="muted">Everything added more than {e(period)} ago has been '
                                 f'finished by someone in the last {e(period)}.</p>', "wide")

    verb = "hasn't" if totals.get("unwatched") == 1 else "haven't"
    headline = (f'<p class="unwatched-headline"><strong>{e(plural(totals.get("unwatched"), "title"))}</strong> '
                f'added more than {e(period)} ago {e(verb)} been finished by anyone in the last {e(period)}. '
                f'Together they use <strong>{size(totals.get("unwatched_gb"))}</strong>, '
                f'{e(totals.get("unwatched_pct"))}% of {size(totals.get("library_gb"))}.</p>')

    rows = "".join(
        f'<tr><th scope="row">{e(lib.get("name"))}</th><td class="num">{num(lib.get("unwatched"))}</td>'
        f'<td class="num">{num(lib.get("never_finished"))}</td><td class="num">{size(lib.get("unwatched_gb"))}</td>'
        f'<td class="num">{e(lib.get("unwatched_pct"))}%</td></tr>'
        for lib in libraries)
    table = (f'<div class="table-wrap"><table><thead><tr><th scope="col">Library</th>'
             f'<th scope="col" class="num">Titles</th><th scope="col" class="num">Never finished</th>'
             f'<th scope="col" class="num">Size</th><th scope="col" class="num">Share</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div>')

    largest = sorted(((t, lib.get("name")) for lib in libraries for t in lib.get("titles") or []),
                     key=lambda pair: -float(pair[0].get("gb") or 0))[:UNWATCHED_TITLES_LIMIT]
    items = []
    for t, lib_name in largest:
        last = f'last finished {month_year(t["last_finished"])}' if t.get("last_finished") else "never finished"
        items.append(f'<li><span class="mono muted">{size(t.get("gb"))}</span>'
                     f'<span class="recent-title">{e(t.get("title"))}<span class="muted"> · {e(lib_name)}'
                     f' · added {month_year(t.get("added"))} · {e(last)}</span></span></li>')
    largest_html = (f'<div class="ranked"><h3>Largest</h3><ul class="recent">{"".join(items)}</ul></div>'
                    if items else "")

    source = "Tautulli" if unwatched.get("source") == "tautulli" else "Plex's watch history"
    since = unwatched.get("history_since")
    note = f"Plays from everyone, from {source}" + (f", going back to {month_year(since)}" if since else "")
    note += ". Only finished plays count."
    if unwatched.get("history_capped"):
        note += " The history was very large, so only its newest part was read."
    body = f'{headline}{table}{largest_html}<p class="muted small">{e(note)}</p>'
    return card("Unwatched", body, "wide")


def number_ranges(numbers):
    """[3, 4, 5, 9] -> [[3, 5], [9, 9]]. Anything that isn't a whole number is left out."""
    groups = []
    for n in sorted(n for n in numbers if isinstance(n, int)):
        if groups and n == groups[-1][1] + 1:
            groups[-1][1] = n
        else:
            groups.append([n, n])
    return groups


def season_ranges(numbers):
    """[3, 4, 5, 9] -> ["seasons 3 to 5", "season 9"]."""
    return [f"season {a}" if a == b else f"seasons {a} to {b}" for a, b in number_ranges(numbers)]


def two(n):
    """Season or episode number with at least two digits; anything that isn't a number as text."""
    try:
        return f"{int(n):02d}"
    except (TypeError, ValueError):
        return str(n)


def show_gaps(show):
    """What one show is missing, as short phrases: "S02E03", "S02E05 to E07", "season 3"."""
    phrases = season_ranges(show.get("missing_seasons") or [])
    for season in show.get("seasons") or []:
        s = two(season.get("season"))
        for first, last in season.get("missing") or []:
            phrases.append(f"S{s}E{two(first)}" if first == last else f"S{s}E{two(first)} to E{two(last)}")
        for first, last in number_ranges(season.get("unavailable") or []):
            episodes = f"S{s}E{two(first)}" if first == last else f"S{s}E{two(first)} to E{two(last)}"
            phrases.append(f"{episodes} (file not found)")
    return phrases


def episode_gaps_section(gaps, error):
    if not gaps:
        reason = ERROR_CODE.sub("", error or "")
        return card("Episode gaps", unavailable_note("the episode gaps report", reason), "wide")
    limits = f'<p class="muted small">{e(gaps.get("limits"))}</p>' if gaps.get("limits") else ""
    libraries = gaps.get("libraries") or []
    if not libraries:
        return card("Episode gaps", '<p class="muted">This server has no TV library.</p>', "wide")
    totals = gaps.get("totals") or {}
    if not totals.get("shows_with_gaps"):
        return card("Episode gaps", f'<p class="muted">No gaps were found between the episodes on the '
                                    f'server.</p>{limits}', "wide")

    parts = [plural(totals.get("missing_episodes", 0), "missing episode")]
    if totals.get("unavailable_episodes"):
        parts.append(f'{plural(totals["unavailable_episodes"], "episode")} whose file Plex can\'t find')
    if totals.get("missing_seasons"):
        parts.append(plural(totals["missing_seasons"], "missing season"))
    have = "has" if totals.get("shows_with_gaps") == 1 else "have"
    headline = (f'<p class="unwatched-headline"><strong>{e(num(totals.get("shows_with_gaps")))}</strong> of '
                f'{e(plural(totals.get("shows"), "show"))} {have} gaps: {e(", ".join(parts))}.</p>')

    rows = "".join(
        f'<tr><th scope="row">{e(lib.get("name"))}</th><td class="num">{num(lib.get("shows"))}</td>'
        f'<td class="num">{num(lib.get("shows_with_gaps"))}</td><td class="num">{num(lib.get("missing_episodes"))}</td>'
        f'<td class="num">{num(lib.get("unavailable_episodes"))}</td><td class="num">{num(lib.get("missing_seasons"))}</td></tr>'
        for lib in libraries)
    table = (f'<div class="table-wrap"><table><thead><tr><th scope="col">Library</th>'
             f'<th scope="col" class="num">Shows</th><th scope="col" class="num">With gaps</th>'
             f'<th scope="col" class="num">Missing episodes</th><th scope="col" class="num">File not found</th>'
             f'<th scope="col" class="num">Missing seasons</th></tr></thead><tbody>{rows}</tbody></table></div>')

    shows = sorted(((s, lib.get("name")) for lib in libraries for s in lib.get("listed") or []),
                   key=lambda pair: (-((pair[0].get("missing_episodes") or 0) + (pair[0].get("unavailable_episodes") or 0)),
                                     -len(pair[0].get("missing_seasons") or []), str(pair[0].get("title")).lower()))
    items = []
    for show, lib_name in shows[:GAP_SHOWS_LIMIT]:
        name = show.get("title") or ""
        if show.get("year"):
            name += f" ({show['year']})"
        phrases = show_gaps(show)
        listed = ", ".join(phrases[:GAPS_PER_SHOW])
        if len(phrases) > GAPS_PER_SHOW:
            listed += f", and {len(phrases) - GAPS_PER_SHOW} more"
        items.append(f'<li><span class="recent-title">{e(name)}<span class="muted"> · {e(lib_name)}</span>'
                     f'<span class="gap-list">{e(listed)}</span></span></li>')
    more = sum(lib.get("shows_with_gaps") or 0 for lib in libraries) - min(len(shows), GAP_SHOWS_LIMIT)
    more_html = f'<p class="muted small">{e(plural(more, "more show"))} with gaps.</p>' if more > 0 else ""
    shows_html = f'<div class="ranked"><h3>Most gaps</h3><ul class="recent gaps">{"".join(items)}</ul>{more_html}</div>'
    return card("Episode gaps", f"{headline}{table}{shows_html}{limits}", "wide")


# (report key, table heading, words for the headline)
PLAYBACK_CAUSES = (("image_subtitles", "Image subtitles", "with image-based subtitles"),
                   ("truehd_audio", "TrueHD audio", "with TrueHD audio"),
                   ("dts_audio", "DTS audio", "with DTS audio"),
                   ("over_bitrate_limit", "Above bitrate limit", "above the bitrate limit"))
REASON_WORDS = {"subtitles": "subtitles", "video": "video", "audio": "audio"}


def main_reason(reasons):
    """The most common known reason, as a word, or None."""
    known = [(reasons.get(r) or 0, r) for r in REASON_WORDS]
    count, reason = max(known, key=lambda pair: pair[0]) if known else (0, None)
    return REASON_WORDS[reason] if count else None


def anonymous_devices(devices):
    """Devices merged by app and platform, for when names are hidden (device names often hold one)."""
    merged = {}
    for d in devices:
        label = " · ".join(x for x in (d.get("app"), d.get("platform")) if x) or "Unknown device"
        m = merged.setdefault(label, {"name": label, "plays": 0, "transcodes": 0, "reasons": {}})
        m["plays"] += d.get("plays") or 0
        m["transcodes"] += d.get("transcodes") or 0
        for r, n in (d.get("reasons") or {}).items():
            m["reasons"][r] = m["reasons"].get(r, 0) + (n or 0)
    return sorted(merged.values(), key=lambda m: (-m["transcodes"], m["name"].lower()))


def transcode_list(title, rows):
    items = []
    for r in rows[:PLAYBACK_GROUPS_LIMIT]:
        plays, transcodes = r.get("plays") or 0, r.get("transcodes") or 0
        share = round(100 * transcodes / plays) if plays else 0
        reason = main_reason(r.get("reasons") or {})
        detail = f"{num(transcodes)} of {plural(plays, 'play')} ({share}%)" + (f", mostly {reason}" if reason else "")
        items.append(f'<li><span class="recent-title">{e(r.get("name"))}'
                     f'<span class="transcode-detail">{e(detail)}</span></span></li>')
    return (f'<div class="ranked"><h3>{e(title)}</h3><ul class="recent transcodes">{"".join(items)}</ul></div>'
            if items else "")


def playback_section(playback, hide_names, error):
    if not playback:
        reason = ERROR_CODE.sub("", error or "")
        return card("Playback", unavailable_note("the playback report", reason), "wide")
    if not playback.get("libraries"):
        return card("Playback", '<p class="muted">This server has no movie or TV library.</p>', "wide")
    libraries = [lib for lib in playback["libraries"] if lib.get("files")] or playback["libraries"]
    limits = f'<p class="muted small">{e(playback.get("limits"))}</p>' if playback.get("limits") else ""
    totals = playback.get("totals") or {}
    causes = [f"{num(totals.get(key))} {words}" for key, _, words in PLAYBACK_CAUSES if totals.get(key)]
    if totals.get("files_flagged"):
        headline = (f'<p class="unwatched-headline"><strong>{e(num(totals.get("files_flagged")))}</strong> of '
                    f'{e(plural(totals.get("files"), "file"))} are likely to be converted on some devices: '
                    f'{e(", ".join(causes))}.</p>')
    else:
        headline = (f'<p class="unwatched-headline">None of the {e(plural(totals.get("files"), "file"))} '
                    f'checked has a common cause of transcoding.</p>')

    rows = "".join(
        f'<tr><th scope="row">{e(lib.get("name"))}</th><td class="num">{num(lib.get("files"))}</td>'
        + "".join(f'<td class="num">{num(lib.get(key))}</td>' for key, _, _ in PLAYBACK_CAUSES) + "</tr>"
        for lib in libraries)
    heads = "".join(f'<th scope="col" class="num">{e(label)}</th>' for _, label, _ in PLAYBACK_CAUSES)
    table = (f'<div class="table-wrap"><table><thead><tr><th scope="col">Library</th>'
             f'<th scope="col" class="num">Files</th>{heads}</tr></thead><tbody>{rows}</tbody></table></div>')

    limit = playback.get("bitrate_limit")
    if limit:
        where = "the server's remote streaming limit" if limit.get("source") == "server" else "the limit asked for"
        bitrate = f"Bitrate is checked against {where}: {num(limit.get('kbps'))} kbps."
    elif playback.get("bitrate_limit_problem"):
        bitrate = "The server's remote streaming limit couldn't be read, so bitrate wasn't checked."
    else:
        bitrate = "No remote streaming limit is set, so bitrate wasn't checked."
    bitrate_html = f'<p class="muted small">{e(bitrate)}</p>'

    history = playback.get("playback_history")
    if history:
        lead = (f'<p>In the last {e(num(history.get("days")))} days, {e(num(history.get("transcodes")))} of '
                f'{e(plural(history.get("plays"), "play"))} were transcoded.</p>')
        devices = history.get("devices") or []
        if hide_names:
            device_rows = anonymous_devices(devices)
        else:
            device_rows = [dict(d, name=" · ".join(x for x in (d.get("device"), d.get("app")) if x)) for d in devices]
        lists = transcode_list("Devices that transcode most", device_rows)
        if not hide_names:
            lists += transcode_list("People who transcode most",
                                    [dict(p, name=p.get("person")) for p in history.get("people") or []])
        history_html = lead + (f'<div class="lists">{lists}</div>' if lists else "")
    else:
        note = playback.get("playback_history_error") or playback.get("playback_history_note") or ""
        history_html = f'<p class="muted">{e(note)}</p>' if note else ""
    return card("Playback", f"{headline}{table}{bitrate_html}{history_html}{limits}", "wide")


KIND_LABEL = {"home": "Plex Home", "managed": "Managed", "friend": "Friend"}


def share_note(item, hide_names):
    """One neutral sentence for a users-and-shares worth_a_look item, or None for unknown kinds."""
    if item.get("kind") == "unused_library":
        # Library titles aren't about any person, so they're shown even when names are hidden.
        titles = [t for t in item.get("libraries") or [] if t]
        if not titles:
            return None
        n = len(titles)
        text = (f"{num(n)} shared {'library' if n == 1 else 'libraries'} with no plays "
                f"by the people {'it is' if n == 1 else 'they are'} shared with in {num(item.get('days'))}+ days")
        return f'<li>{e(text)}<span class="muted">: {e(", ".join(titles))}</span></li>'
    people = [p for p in item.get("people") or [] if p]
    n = len(people)
    if not n:
        return None
    days = item.get("days")
    kind = item.get("kind")
    if kind == "old_pending_invite":
        text = f"{plural(n, 'invite')} still waiting after {num(days)}+ days"
    elif kind == "inactive":
        text = f"{people_count(n)} with no plays in {num(days)}+ days"
    elif kind == "all_libraries":
        text = (f"{people_count(n)} {'has' if n == 1 else 'have'} all libraries, "
                "so new libraries are shared with them too")
    elif kind == "downloads_allowed":
        text = f"{plural(n, 'friend')} can download"
    else:
        return None
    names = "" if hide_names else f'<span class="muted">: {e(", ".join(people))}</span>'
    return f"<li>{e(text)}{names}</li>"


def sharing_section(sharing, hide_names, error):
    if not sharing:
        reason = ERROR_CODE.sub("", error or "")
        return card("Sharing", unavailable_note("who the server is shared with", reason), "wide")
    people = sharing.get("people") or []
    if not people:
        return card("Sharing", '<p class="muted">Your server isn\'t shared with anyone.</p>', "wide")

    by_kind = (sharing.get("totals") or {}).get("by_kind") or {}
    pending = sum(1 for p in people if p.get("status") == "pending")
    counts = [("People", len(people)), ("Plex Home", by_kind.get("home", 0)),
              ("Managed", by_kind.get("managed", 0)), ("Friends", by_kind.get("friend", 0)),
              ("Pending", pending)]
    counts_html = "".join(f'<li><span class="share-n">{num(n)}</span><span class="muted">{e(label)}</span></li>'
                          for label, n in counts)

    lib_rows = "".join(
        f'<tr><th scope="row">{e(lib.get("title"))}</th><td class="num">{num(lib.get("shared_with_count"))}</td></tr>'
        for lib in sharing.get("libraries") or [])
    lib_table = (f'<div class="table-wrap"><table><thead><tr><th scope="col">Library</th>'
                 f'<th scope="col" class="num">People who can see it</th></tr></thead>'
                 f'<tbody>{lib_rows}</tbody></table></div>') if lib_rows else ""

    notes = [n for n in (share_note(w, hide_names) for w in sharing.get("worth_a_look") or []) if n]
    notes_html = (f'<div class="ranked"><h3>Worth a look</h3><ul class="share-notes">{"".join(notes)}</ul></div>'
                  if notes else '<div class="ranked"><h3>Worth a look</h3><p class="muted">Nothing stands out.</p></div>')

    people_html = ""
    if not hide_names:
        rows = []
        for p in people[:SHARING_PEOPLE_LIMIT]:
            libs = p.get("libraries")
            libs_text = "all" if libs == "all" else ("–" if libs is None else num(len(libs)))
            if p.get("status") == "pending":
                played = "pending"
            elif p.get("last_played"):
                played = short_date(p["last_played"])
            else:
                played = "no plays found"
            kind = KIND_LABEL.get(p.get("kind"), p.get("kind"))
            rows.append(f'<tr><th scope="row">{e(p.get("name"))}<span class="share-kind">{e(kind)}</span></th>'
                        f'<td class="num">{e(libs_text)}</td><td class="num">{e(played)}</td></tr>')
        more = len(people) - SHARING_PEOPLE_LIMIT
        more_html = f'<p class="muted small">and {num(more)} more {"person" if more == 1 else "people"}</p>' if more > 0 else ""
        people_html = (f'<div class="table-wrap"><table><thead><tr><th scope="col">Person</th>'
                       f'<th scope="col" class="num">Libraries</th><th scope="col" class="num">Last played</th></tr></thead>'
                       f'<tbody>{"".join(rows)}</tbody></table></div>{more_html}')

    body = (f'<ul class="share-counts">{counts_html}</ul>'
            f'<div class="lists two"><div class="ranked">{lib_table}</div>{notes_html}</div>{people_html}')
    return card("Sharing", body, "wide")


def signed(n, word=None):
    text = f"+{num(n)}" if n > 0 else num(n)
    return f"{text} {word}" if word else text


def note(text, names=None):
    """One line for the changes section, with up to CHANGE_EXAMPLES names after it."""
    names = [n for n in names or [] if n]
    if not names:
        return f"<li>{e(text)}</li>"
    shown = ", ".join(names[:CHANGE_EXAMPLES]) + (", …" if len(names) > CHANGE_EXAMPLES else "")
    return f'<li>{e(text)}<span class="muted">: {e(shown)}</span></li>'


def library_change_notes(since):
    lines = []
    for lib in since.get("libraries") or []:
        name, status = lib.get("name") or "A library", lib.get("status")
        if status == "new":
            lines.append(note(f"New library: {name}"))
            continue
        if status == "removed":
            lines.append(note(f"Library no longer there: {name}"))
            continue
        if lib.get("renamed_from"):
            lines.append(note(f"{lib['renamed_from']} is now called {name}"))
        for key, label in (("added", "added"), ("removed", "removed"),
                           ("became_unavailable", "Plex can't find now"),
                           ("available_again", "available again")):
            n = lib.get(f"{key}_count") or 0
            if n:
                lines.append(note(f"{name}: {num(n)} {label}", lib.get(key)))
        for key, label in (("episodes_added", "new episodes"), ("episodes_removed", "episodes removed")):
            n = lib.get(f"{key}_count") or 0
            if n:
                shows = [f"{r.get('show')} ({num(r.get('count'))})" for r in lib.get(key) or []
                         if isinstance(r, dict)]
                lines.append(note(f"{name}: {num(n)} {label}", shows))
    return lines


def server_change_notes(since):
    lines = []
    for c in since.get("changes") or []:
        kind, before, after = c.get("kind"), c.get("from"), c.get("to")
        if kind == "version":
            lines.append(note(f"Plex went from {before} to {after}"))
        elif kind == "update_version":
            lines.append(note("No update waiting now" if after is False else f"Update {after} is available"))
        elif kind == "remote_access":
            lines.append(note(f"Remote access went from {before} to {after}"))
    return lines


def sharing_change_notes(since, hide_names):
    def names(rows):
        return None if hide_names else [r.get("name") if isinstance(r, dict) else r for r in rows]

    lines = []
    for key, label in (("added", "now {verb} access"), ("removed", "no longer listed")):
        rows = since.get(key) or []
        if rows:
            text = label.format(verb="has" if len(rows) == 1 else "have")
            lines.append(note(f"{people_count(len(rows))} {text}", names(rows)))
    accepted = since.get("accepted") or []
    if accepted:
        lines.append(note(f"{plural(len(accepted), 'invite')} accepted", names(accepted)))
    changed = since.get("libraries_changed") or []
    if changed:
        details = None if hide_names else [
            f"{c.get('name')} ({', '.join(['+' + g for g in c.get('gained') or []] + ['-' + l for l in c.get('lost') or []])})"
            if "gained" in c else f"{c.get('name')} ({'all libraries' if c.get('to') == 'all' else 'chosen libraries'})"
            for c in changed]
        lines.append(note(f"{people_count(len(changed))} with different libraries", details))
    downloads = since.get("downloads_changed") or []
    if downloads:
        lines.append(note(f"Download access changed for {people_count(len(downloads))}", names(downloads)))
    invites = since.get("email_invites_change") or 0
    if invites:
        lines.append(note(f"{signed(invites)} invites sent by email"))
    return lines


def changes_section(data, hide_names, snapshot_saved):
    reports = {area: data.get(area) for area in SNAPSHOT_AREAS if data.get(area)}
    if not reports:
        return ""
    found = {area: r.get("since_snapshot") for area, r in reports.items()
             if isinstance(r.get("since_snapshot"), dict)}
    if not found:
        text = ("First snapshot saved today. What changed will show here from the next day's update."
                if snapshot_saved else "No earlier snapshot to compare with yet.")
        return card("What changed", f'<p class="muted">{e(text)}</p>', "wide")

    oldest = max(found.values(), key=lambda s: s.get("days_ago") or 0)
    title = f"Since {short_date(oldest.get('snapshot_date'))}"
    days = oldest.get("days_ago") or 0
    aside = e("yesterday" if days == 1 else f"{num(days)} days ago")

    blocks, counts_html = [], ""
    library = found.get("library")
    if library:
        t = library.get("totals") or {}
        counts = [("Titles added", t.get("added")), ("Titles removed", t.get("removed")),
                  ("New episodes", t.get("episodes_added")), ("Can't be found now", t.get("became_unavailable")),
                  ("Available again", t.get("available_again"))]
        shown = [(label, n) for label, n in counts if n]
        size_change = t.get("size_gb_change") or 0
        counts_html = "".join(f'<li><span class="share-n">{num(n)}</span><span class="muted">{e(label)}</span></li>'
                              for label, n in shown)
        if abs(size_change) >= 1:
            counts_html += (f'<li><span class="share-n">{e(("+" if size_change > 0 else "-") + size(abs(size_change)))}'
                            f'</span><span class="muted">Storage</span></li>')
        blocks.append(("Library", library_change_notes(library)))
    if found.get("health"):
        blocks.append(("Server", server_change_notes(found["health"])))
    if found.get("sharing"):
        blocks.append(("Sharing", sharing_change_notes(found["sharing"], hide_names)))

    if not counts_html and not any(lines for _, lines in blocks):
        return card(title, '<p class="muted">Nothing changed.</p>', "wide", aside)
    lists = "".join(
        f'<div class="ranked"><h3>{e(heading)}</h3>'
        + (f'<ul class="share-notes">{"".join(lines)}</ul>' if lines else '<p class="muted">No changes.</p>')
        + "</div>" for heading, lines in blocks)
    counts_block = f'<ul class="share-counts">{counts_html}</ul>' if counts_html else ""
    return card(title, f'{counts_block}<div class="lists">{lists}</div>', "wide", aside)


def trend_values(values, count):
    """A list of numbers or None, exactly count long, from untrusted output."""
    values = values if isinstance(values, list) else []
    values = [v if isinstance(v, (int, float)) and not isinstance(v, bool) else None for v in values]
    return (values + [None] * count)[:count]


def trend_change(values, fmt, word=""):
    """'first → latest (+change)' for a heading, from the first and last values that exist."""
    present = [v for v in values if v is not None]
    first, latest = present[0], present[-1]
    diff = latest - first
    change = "no change" if abs(diff) < 1e-9 else ("+" if diff > 0 else "-") + fmt(abs(diff))
    return f"{fmt(first)} → {fmt(latest)}{' ' + word if word else ''} ({change})"


def trend_block(title, points, change, aria, tick=num, small=False):
    if small:
        chart = line_chart(points, 360, 120, "chart", aria, tick=tick, labels=2)
    else:
        chart = (line_chart(points, 720, 180, "chart chart-wide", aria, tick=tick, left=52, labels=5)
                 + line_chart(points, 360, 160, "chart chart-narrow", aria, tick=tick, left=52, labels=3))
    return (f'<div class="chart-block"><div class="chart-head"><h3>{e(title)}</h3>'
            f'<span class="muted">{e(change)}</span></div>{chart}</div>')


def trends_section(trends):
    """Charts of library size, titles per library and people with access across the snapshots."""
    if not isinstance(trends, dict):
        return ""
    dates = [d for d in trends.get("dates") or [] if isinstance(d, str) and day_number(d) is not None]
    if len(dates) != len(trends.get("dates") or []):
        return ""  # dates the page can't place; leave the section out rather than draw it wrong
    n = len(dates)
    days = [day_number(d) for d in dates]
    library = trends.get("library") if isinstance(trends.get("library"), dict) else {}
    sharing = trends.get("sharing") if isinstance(trends.get("sharing"), dict) else {}

    def points(values, tip):
        return [{"day": days[i], "date": dates[i], "value": v, "tip": tip(i, v)} for i, v in enumerate(values)]

    def enough(values):
        return sum(v is not None for v in values) >= 2

    blocks = []
    total = trend_values(library.get("total_size_gb"), n)
    if enough(total):
        blocks.append(trend_block(
            "Storage over time", points(total, lambda i, v: f"{short_date(dates[i])}: {size(v)}"),
            trend_change(total, size), "Total library size on each snapshot day", tick=size))

    small = []
    for lib in library.get("libraries") or []:
        if not isinstance(lib, dict) or not isinstance(lib.get("counts"), dict):
            continue
        found = next(((key, word) for key, word in TREND_COUNTS if key in lib["counts"]), None)
        if not found:
            continue
        key, word = found
        values = trend_values(lib["counts"][key], n)
        if not enough(values) or not any(values):
            continue  # too few days, or an empty library: a flat line at zero says nothing
        name = lib.get("name") or "Library"
        small.append(trend_block(
            name, points(values, lambda i, v, w=word: f"{short_date(dates[i])}: {plural(v, w)}"),
            trend_change(values, num, key), f"{name}: {key} on each snapshot day", small=True))
    if small:
        blocks.append(f'<div class="trend-grid">{"".join(small)}</div>')

    people = trend_values(sharing.get("people"), n)
    pending = trend_values(sharing.get("pending"), n)
    if enough(people):
        def people_tip(i, v):
            tip = f"{short_date(dates[i])}: {people_count(v)}"
            return tip + f", {plural(pending[i], 'pending invite')}" if pending[i] else tip
        blocks.append(trend_block("People with access", points(people, people_tip),
                                  trend_change(people, num), "People with access on each snapshot day"))

    if not blocks:
        body = '<p class="muted">Trends will show here once there are snapshots from two different days.</p>'
        return card("Trends", body, "wide")
    aside = e(f"{plural(n, 'snapshot day')}, {short_date(dates[0])} to {short_date(dates[-1])}")
    return card("Trends", "".join(blocks), "wide", aside)


# ---------------------------------------------------------------- page

CSS = """
/* Layout: projection-booth status board. Header strip, summary tiles, a server panel,
   then full-width watch and library panels. Stacks to one column on phones. */
:root {
  --bg: #eef0f2; --panel: #ffffff; --ink: #14171a; --ink-2: #4a525a; --muted: #7b838b;
  --line: #dde1e5; --grid: #e6e9ec; --axis: #c2c8ce; --accent: #2a78d6; --accent-soft: #cde2fb;
  --good: #0a7d0a; --good-bg: #e3f3e3; --warn: #8a5a00; --warn-bg: #fff1d1; --crit: #b52828; --crit-bg: #fbe3e3;
  --q-4k: #184f95; --q-1080: #2a78d6; --q-720: #6da7ec; --q-sd: #b7d3f6; --q-other: #c2c8ce;
  /* Installed fonts only (nothing is downloaded). Narrow faces: Office/Windows, Android, macOS,
     Windows 10+, then common Linux ones. */
  --font-display: "Big Shoulders Display", "Arial Narrow", "Roboto Condensed", "Avenir Next Condensed",
    Bahnschrift, "Nimbus Sans Narrow", "Liberation Sans Narrow", "DejaVu Sans Condensed", sans-serif;
  --font-body: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0f1113; --panel: #181b1e; --ink: #eef1f3; --ink-2: #b8c0c7; --muted: #8a939b;
  --line: #2a2f34; --grid: #23272b; --axis: #3a4046; --accent: #3987e5; --accent-soft: #1c3a5e;
  --good: #4cc24c; --good-bg: #13301a; --warn: #f5b335; --warn-bg: #3a2b0c; --crit: #ff7b7b; --crit-bg: #3d1717;
  --q-4k: #86b6ef; --q-1080: #3987e5; --q-720: #256abf; --q-sd: #184f95; --q-other: #3a4046;
  color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #0f1113; --panel: #181b1e; --ink: #eef1f3; --ink-2: #b8c0c7; --muted: #8a939b;
  --line: #2a2f34; --grid: #23272b; --axis: #3a4046; --accent: #3987e5; --accent-soft: #1c3a5e;
  --good: #4cc24c; --good-bg: #13301a; --warn: #f5b335; --warn-bg: #3a2b0c; --crit: #ff7b7b; --crit-bg: #3d1717;
  --q-4k: #86b6ef; --q-1080: #3987e5; --q-720: #256abf; --q-sd: #184f95; --q-other: #3a4046;
  color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 var(--font-body); }
.masthead h1, .tile-value, .card-head h2 { font-stretch: condensed; }
.page { max-width: 72rem; margin: 0 auto; padding-inline: 16px; padding-block: 20px 40px;
  display: grid; gap: 16px; }
h1, h2, h3 { margin: 0; text-wrap: balance; }
.muted { color: var(--muted); }
.small { font-size: 13px; margin: 6px 0 0; }
.mono { font-family: var(--font-mono); font-size: 13px; font-variant-numeric: tabular-nums; }
.masthead { display: flex; flex-wrap: wrap; align-items: end; justify-content: space-between; gap: 8px 16px;
  padding-block: 4px 12px; border-bottom: 2px solid var(--ink); }
.masthead h1 { font-family: var(--font-display); font-weight: 800; font-size: 40px; line-height: 1;
  letter-spacing: .01em; text-transform: uppercase; }
.masthead .eyebrow { display: block; font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
  color: var(--muted); margin-bottom: 4px; }
.masthead-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; color: var(--ink-2); font-size: 13px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(10.5rem, 1fr)); gap: 12px; }
.tile { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px;
  display: grid; gap: 2px; }
.tile-label { font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.tile-value { font-family: var(--font-display); font-weight: 700; font-size: 38px; line-height: 1.05; }
.tile-note { font-size: 13px; color: var(--ink-2); }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 16px;
  min-width: 0; display: grid; gap: 12px; align-content: start; }
.card-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 4px 12px; }
.card-head h2 { font-family: var(--font-display); font-weight: 700; font-size: 22px; letter-spacing: .02em;
  text-transform: uppercase; }
.card-aside { font-size: 13px; color: var(--muted); }
.card h3 { font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); font-weight: 600;
  margin-bottom: 6px; }
ul, ol { list-style: none; margin: 0; padding: 0; }
.kv { display: grid; gap: 0; }
.kv li { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding-block: 7px;
  border-bottom: 1px solid var(--grid); }
.kv li:last-child { border-bottom: 0; }
.kv li > span:first-child { color: var(--ink-2); }
.pill { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; padding: 2px 10px 2px 4px;
  border-radius: 999px; white-space: nowrap; }
.pill-icon { display: inline-grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; font-size: 11px;
  font-weight: 700; color: var(--panel); }
.pill-good { background: var(--good-bg); color: var(--good); } .pill-good .pill-icon { background: var(--good); }
.pill-warning { background: var(--warn-bg); color: var(--warn); } .pill-warning .pill-icon { background: var(--warn); }
.pill-critical { background: var(--crit-bg); color: var(--crit); } .pill-critical .pill-icon { background: var(--crit); }
.pill-unknown { background: var(--grid); color: var(--ink-2); } .pill-unknown .pill-icon { background: var(--muted); }
.attn-list { display: grid; gap: 8px; }
.attn { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: start; padding: 10px 12px;
  border-radius: 8px; border-left: 4px solid var(--warn); background: var(--warn-bg); }
.attn-critical { border-left-color: var(--crit); background: var(--crit-bg); }
.attn div { display: grid; min-width: 0; }
.attn .muted { color: var(--ink-2); font-size: 13px; }
.attn-icon { font-weight: 700; width: 18px; text-align: center; color: var(--warn); }
.attn-critical .attn-icon { color: var(--crit); }
.all-clear { margin: 0; }
.who { color: var(--ink); font-weight: 500; }
.who::after { content: " · "; color: var(--muted); }
.wide { grid-column: 1 / -1; }
.chart-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 4px 12px; }
.chart-head h3 { margin: 0; }
.chart { width: 100%; height: auto; display: block; margin-top: 8px; }
.chart-narrow { display: none; }
@media (max-width: 36rem) { .chart-wide { display: none; } .chart-narrow { display: block; } }
.chart .grid { stroke: var(--grid); stroke-width: 1; }
.chart .baseline { stroke: var(--axis); stroke-width: 1; }
.chart .tick { fill: var(--muted); font: 11px var(--font-mono); }
.chart .bar { fill: var(--accent); }
.chart .bar-peak { fill: var(--q-4k); }
.chart .hit { fill: transparent; }
.chart .hit:hover { fill: var(--accent-soft); fill-opacity: .35; }
.chart .trend-line { fill: none; stroke: var(--accent); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.chart .trend-dot { fill: var(--accent); }
.chart .trend-last { fill: var(--q-4k); }
.trend-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr)); gap: 16px 24px; }
.trend-grid .chart-head h3 { overflow-wrap: anywhere; }
.lists { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr)); gap: 20px 24px; }
.ranked { min-width: 0; }
.ranked ol { display: grid; gap: 8px; }
.rank-line { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; font-size: 14px; }
.rank-line .mono { white-space: nowrap; }
.rank-name { min-width: 0; overflow-wrap: anywhere; }
.rank-track { height: 6px; margin-top: 3px; }
.rank-bar { height: 100%; background: var(--accent); border-radius: 0 3px 3px 0; min-width: 2px; }
.recent { display: grid; gap: 6px; column-gap: 24px; }
@media (min-width: 48rem) { .recent { grid-template-columns: 1fr 1fr; } }
.recent li { display: grid; grid-template-columns: 6.5rem 1fr; gap: 8px; font-size: 14px; }
.recent-title { min-width: 0; overflow-wrap: anywhere; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13px; color: var(--ink-2); }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
.q-4k { background: var(--q-4k); } .q-1080 { background: var(--q-1080); } .q-720 { background: var(--q-720); }
.q-sd { background: var(--q-sd); } .q-other { background: var(--q-other); }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 9px 10px 9px 0; border-bottom: 1px solid var(--grid); vertical-align: middle; }
thead th { font-size: 12px; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
tbody th { font-weight: 600; white-space: nowrap; }
.num { text-align: right; font-variant-numeric: tabular-nums; font-family: var(--font-mono); font-size: 13px;
  white-space: nowrap; }
.qcell { min-width: 9rem; width: 30%; }
.qbar { display: flex; gap: 2px; height: 12px; }
.seg { display: block; height: 100%; min-width: 2px; }
.seg:first-child { border-radius: 3px 0 0 3px; } .seg:last-child { border-radius: 0 3px 3px 0; }
.seg:only-child { border-radius: 3px; }
.share-counts { display: flex; flex-wrap: wrap; gap: 10px 28px; margin-bottom: 14px; }
.share-counts li { display: grid; }
.share-n { font-family: var(--font-display); font-size: 30px; font-weight: 700; line-height: 1.1; }
.share-notes { display: grid; gap: 8px; font-size: 14px; }
.share-notes li { padding-left: 12px; border-left: 3px solid var(--line); }
.share-kind { display: block; font-size: 12px; font-weight: 400; color: var(--muted); }
.unwatched-headline { margin: 0; max-width: 60rem; }
.recent.gaps li { grid-template-columns: 1fr; }
.recent.transcodes, .recent.transcodes li { grid-template-columns: 1fr; }
.transcode-detail { display: block; font-size: 13px; color: var(--muted); }
.gap-list { display: block; font-family: var(--font-mono); font-size: 13px; color: var(--muted); }
.foot { font-size: 12px; color: var(--muted); display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; }
@media (max-width: 30rem) { .masthead h1 { font-size: 32px; } .tile-value { font-size: 32px; }
  .recent li { grid-template-columns: 1fr; gap: 0; } }
"""

# The page loads nothing from outside itself; the browser enforces this. Text uses installed fonts.
CSP = ('<meta http-equiv="Content-Security-Policy" '
       'content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:">')


def render(data, errors, hide_names, snapshot_saved=None, trends=None):
    library, health, watch = data.get("library"), data.get("health"), data.get("watch")
    server = ((health or {}).get("server") or {}).get("name") or ((library or {}).get("server") or {}).get("name") \
        or "Plex"
    items = attention_items(health, library)
    level, label = overall_status(health, items)
    generated = friendly_now()
    version = ((health or {}).get("server") or {}).get("version") or ((library or {}).get("server") or {}).get("version")

    body = f"""<main class="page">
<header class="masthead">
 <div><span class="eyebrow">Cinemetric · Plex server</span><h1>{e(server)}</h1></div>
 <div class="masthead-meta">{pill(level, label)}<span>Updated {e(generated)}</span></div>
</header>
{kpi_row(library, health, watch)}
{changes_section(data, hide_names, snapshot_saved)}
{trends_section(trends)}
{server_card(health, items, errors.get("health"))}
{watch_section(watch, hide_names, errors.get("watch"))}
{library_section(library, errors.get("library"))}
{unwatched_section(data.get("unwatched"), errors.get("unwatched"))}
{episode_gaps_section(data.get("episode_gaps"), errors.get("episode_gaps"))}
{playback_section(data.get("playback"), hide_names, errors.get("playback"))}
{sharing_section(data.get("sharing"), hide_names, errors.get("sharing"))}
<footer class="foot"><span>Read-only snapshot made by Cinemetric {e(VERSION)}{" · Plex " + e(version) if version else ""}.</span>
<span>Numbers come from your server; written notes are rule-based, not AI.</span></footer>
</main>"""
    title = f"<title>{e(server)} Plex Dashboard</title>"
    return title, body


def write_page(path, content):
    """Write a file atomically, readable only by the user."""
    folder = os.path.dirname(os.path.abspath(path))
    ensure_private_dir(folder)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".cinemetric-", suffix=".tmp")
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def full_page(title, body):
    return (f'<!doctype html>\n<html lang="en"><head>{CSP}\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'{title}\n<style>{CSS}</style>\n</head><body>\n{body}\n</body></html>\n')


# ---------------------------------------------------------------- saved choices

DESTINATIONS = ("local", "online", "both")
# The online page's link is handed back to Claude as the page to update, so only accept the exact
# shape of a claude.ai page link.
ONLINE_PAGE_RE = re.compile(r"https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9-]{1,100}")


def state_path():
    return os.path.join(data_dir(), "dashboard-state.json")


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_state():
    return load_json(state_path())


def save_state(state):
    write_page(state_path(), json.dumps(state, indent=1))


def saved_destination(state):
    value = state.get("destination")
    return value if value in DESTINATIONS else None


def saved_online_page(state):
    value = state.get("online_page")
    return value if isinstance(value, str) and ONLINE_PAGE_RE.fullmatch(value) else None


def server_name(data):
    return (((data.get("health") or {}).get("server") or {}).get("name")
            or ((data.get("library") or {}).get("server") or {}).get("name"))


# ---------------------------------------------------------------- build

def build(args):
    state = load_state()
    old_schedule_removed, old_schedule_error = remove_old_schedule(state)
    if args.hide_names is not None and args.hide_names != state.get("hide_names", False):
        state["hide_names"] = args.hide_names
        save_state(state)
    hide_names = bool(state.get("hide_names", False))

    data, errors = collect()
    server_id = snapshot_server_id(data)  # before save_snapshot drops the snapshot blocks
    snapshot_saved = save_snapshot(data)
    trends = load_trends(server_id)
    title, body = render(data, errors, hide_names, snapshot_saved, trends)
    output = os.path.abspath(os.path.expanduser(args.output))
    write_page(output, full_page(title, body))

    destination = saved_destination(state)
    result = {
        "step": "done",
        "output": output,
        "server": server_name(data),
        "sections_missing": errors,
        "names_hidden": hide_names,
        "destination": destination,
        "online_page": saved_online_page(state),
        "ask": [] if destination else ["destination"],
        "old_schedule_removed": old_schedule_removed,
        "snapshot_saved": snapshot_saved,
    }
    if old_schedule_error:
        result["old_schedule_error"] = old_schedule_error
    return result


def cmd_destination(args):
    state = load_state()
    state["destination"] = args.choice
    save_state(state)
    return {"destination": args.choice, "online_page": saved_online_page(state)}


def cmd_online_page(args):
    state = load_state()
    if args.forget:
        state.pop("online_page", None)
    else:
        url = args.url.strip()
        if not ONLINE_PAGE_RE.fullmatch(url):
            raise DashboardError("That isn't a claude.ai page link. It should look like "
                                 "https://claude.ai/artifact/... or https://claude.ai/code/artifact/...")
        state["online_page"] = url
    save_state(state)
    return {"destination": saved_destination(state), "online_page": saved_online_page(state)}


# ---------------------------------------------------------------- removing schedules from older versions
#
# Versions before 0.4.0 could refresh the dashboard on a timer (cron, launchd or Task Scheduler).
# That feature is gone; these functions only remove a task an older version installed, so nothing
# keeps running in the background.

CRON_TAG = "# cinemetric-dashboard"
LAUNCHD_LABEL = "com.cinemetric.dashboard"
TASK_NAME = "Cinemetric Dashboard"


def run(cmd, **kwargs):
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def cron_remove():
    if not shutil.which("crontab"):
        return  # no cron, so no cron task to remove
    proc = run(["crontab", "-l"])
    if proc.returncode != 0:
        if "no crontab" in (proc.stderr or "").lower():
            return
        raise DashboardError(f"couldn't read your scheduled tasks: {proc.stderr.strip()}")
    lines = proc.stdout.splitlines()
    others = [line for line in lines if not line.rstrip().endswith(CRON_TAG)]
    if len(others) == len(lines):
        return
    text = "\n".join(others).strip("\n")
    proc = run(["crontab", "-"], input=(text + "\n") if text else "")
    if proc.returncode != 0:
        raise DashboardError(f"couldn't update your scheduled tasks: {proc.stderr.strip()}")


def launchd_remove():
    path = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", f"{LAUNCHD_LABEL}.plist")
    run(["launchctl", "bootout", f"gui/{os.getuid()}/{LAUNCHD_LABEL}"])  # fine if it isn't loaded
    if os.path.exists(path):
        os.remove(path)


def task_remove():
    if run(["schtasks", "/Query", "/TN", TASK_NAME]).returncode != 0:
        return  # not there
    proc = run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME])
    if proc.returncode != 0:
        raise DashboardError(f"couldn't remove the task from Task Scheduler: "
                             f"{(proc.stderr or proc.stdout).strip()}")


OLD_SCHEDULERS = {"cron": cron_remove, "launchd": launchd_remove, "task-scheduler": task_remove}


def remove_old_schedule(state):
    """Remove a scheduled task left by an older version. Returns (removed, error)."""
    saved = state.get("automation")
    if not saved:
        return False, None
    kind = saved.get("scheduler") if isinstance(saved, dict) else None
    try:
        OLD_SCHEDULERS.get(kind, cron_remove)()
    except (DashboardError, OSError) as exc:
        return False, str(exc)
    shutil.rmtree(os.path.join(data_dir(), "scheduled"), ignore_errors=True)
    for leftover in ("run-dashboard.cmd", "dashboard.log"):
        try:
            os.remove(os.path.join(data_dir(), leftover))
        except OSError:
            pass  # already gone, or a stray file that no longer matters
    if isinstance(saved, dict) and saved.get("hide_names") and "hide_names" not in state:
        state["hide_names"] = True  # scheduled runs hid names; keep that choice
    state.pop("automation", None)
    save_state(state)
    return True, None


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Build the Cinemetric Plex dashboard (HTML).")
    parser.add_argument("--output", default=default_output(), help="where to write the page")
    names = parser.add_mutually_exclusive_group()
    names.add_argument("--hide-names", dest="hide_names", action="store_true", default=None,
                       help="leave out people's names (remembered)")
    names.add_argument("--show-names", dest="hide_names", action="store_false",
                       help="show people's names again (remembered)")
    sub = parser.add_subparsers(dest="command")
    dest = sub.add_parser("destination", help="save where the dashboard goes")
    dest.add_argument("choice", choices=DESTINATIONS)
    page = sub.add_parser("online-page", help="save or forget the claude.ai page link")
    which = page.add_mutually_exclusive_group(required=True)
    which.add_argument("--url", help="the claude.ai page link")
    which.add_argument("--forget", action="store_true", help="forget the saved link")
    args = parser.parse_args()

    try:
        if args.command == "destination":
            result = cmd_destination(args)
        elif args.command == "online-page":
            result = cmd_online_page(args)
        else:
            result = build(args)
    except DashboardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    json.dump(result, sys.stdout, indent=1, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
