#!/usr/bin/env python3
"""Cinemetric dashboard: one HTML page combining the library report, server health, watch activity
and who the server is shared with.

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

VERSION = "0.15.0"
SCRIPT_TIMEOUT_SECONDS = 1800

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.normpath(os.path.join(HERE, "..", ".."))
SOURCES = {
    "library": ("library-report", "library_report.py", []),
    # The dashboard doesn't show the stuck task check, so it skips the wait.
    "health": ("server-health", "server_health.py", ["--stuck-wait", "0"]),
    "watch": ("watch-activity", "watch_activity.py", ["--days", "30", "--top", "8", "--recent", "10"]),
    "sharing": ("users-and-shares", "users_and_shares.py", []),
    # Each library lists its 10 largest, so the 10 largest overall are always among them.
    "unwatched": ("unwatched", "unwatched.py", ["--limit", "10"]),
}
UNWATCHED_TITLES_LIMIT = 10
SHARING_PEOPLE_LIMIT = 20
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


KIND_LABEL = {"home": "Plex Home", "managed": "Managed", "friend": "Friend"}


def share_note(item, hide_names):
    """One neutral sentence for a users-and-shares worth_a_look item, or None for unknown kinds."""
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
.foot { font-size: 12px; color: var(--muted); display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; }
@media (max-width: 30rem) { .masthead h1 { font-size: 32px; } .tile-value { font-size: 32px; }
  .recent li { grid-template-columns: 1fr; gap: 0; } }
"""

# The page loads nothing from outside itself; the browser enforces this. Text uses installed fonts.
CSP = ('<meta http-equiv="Content-Security-Policy" '
       'content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:">')


def render(data, errors, hide_names):
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
{server_card(health, items, errors.get("health"))}
{watch_section(watch, hide_names, errors.get("watch"))}
{library_section(library, errors.get("library"))}
{unwatched_section(data.get("unwatched"), errors.get("unwatched"))}
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
    title, body = render(data, errors, hide_names)
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
