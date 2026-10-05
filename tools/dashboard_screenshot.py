#!/usr/bin/env python3
"""Retake the website's dashboard screenshot (website/screens/dashboard.jpg).

Renders the real dashboard page from made-up sample data (no Plex server is contacted), takes a
screenshot with headless Chrome or Chromium, saves it as a JPG and updates the image's height in
website/index.html. Run it from anywhere after changing how the dashboard looks:

    python3 tools/dashboard_screenshot.py

Needs Google Chrome or Chromium, and Pillow (`pip install pillow`) to crop the image and save the
JPG. This is a development tool: it isn't part of the plugin or the website, so unlike the skill
scripts it may use a package outside the standard library.

The sample data below is invented: server, people, titles and numbers are all made up. Keep it that
way, and keep the dates fixed so the screenshot only changes when the dashboard itself does.
"""

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD = os.path.join(ROOT, "plugins", "cinemetric", "skills", "dashboard", "scripts", "dashboard.py")
SCREENSHOT = os.path.join(ROOT, "website", "screens", "dashboard.jpg")
INDEX = os.path.join(ROOT, "website", "index.html")
WIDTH = 900
BOTTOM_MARGIN = 47  # space kept below the footer text, matching the page's own bottom padding
BROWSERS = ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "chrome")

# ---------------------------------------------------------------- made-up sample data

daily_plays = [9, 12, 11, 16, 23, 27, 17, 10, 12, 10, 14, 21, 29, 19, 8, 13, 11, 15, 22, 26,
               17, 10, 12, 13, 14, 24, 28, 18, 11, 13]
days = [f"2026-09-{d:02d}" for d in range(5, 31)] + [f"2026-10-{d:02d}" for d in range(1, 5)]

health = {
    "server": {"name": "Media NAS", "version": "1.41.1",
               "update": {"update_available": True, "available_version": "1.41.2"},
               "remote_access": {"state": "mapped"}},
    "worth_a_look": [{"kind": "update_available", "version": "1.41.2"}],
}
watch = {
    "source": "tautulli", "period_days": 30,
    "totals": {"plays": 486, "active_users": 6, "watch_hours": 312},
    "trend": {"earlier_half_plays": 240, "recent_half_plays": 246},
    "plays_by_type": {"tv": 301, "movies": 112, "music": 73},
    "daily": [{"date": d, "plays": p} for d, p in zip(days, daily_plays)],
    "top_shows": [{"title": t, "plays": p, "hours": h} for t, p, h in [
        ("Harbor Lights", 64, 51), ("Quiet Hours", 41, 30), ("North of Nowhere", 29, 25),
        ("The Night Desk", 22, 15), ("Copper Valley", 18, 14)]],
    "top_movies": [{"title": t, "plays": p, "hours": h} for t, p, h in [
        ("The Long Voyage", 9, 18), ("Paper Lanterns", 7, 12), ("Midnight Orchard", 5, 9),
        ("The Glass Coast", 4, 7), ("Second Summer", 3, 5)]],
    "top_music": [{"title": t, "plays": p, "hours": h} for t, p, h in [
        ("Low Tide", 21, 1), ("Satellite Hearts", 14, 0.9), ("Wildflower Radio", 9, 0.6)]],
    "top_users": [{"user": u, "plays": p, "hours": h} for u, p, h in [
        ("alex", 162, 104), ("sam", 121, 82), ("jordan", 88, 57), ("riley", 61, 38),
        ("casey", 34, 19), ("morgan", 20, 10)]],
    "top_platforms": [{"platform": u, "plays": p, "hours": h} for u, p, h in [
        ("Roku", 190, 140), ("Android", 120, 70), ("Chrome", 96, 55), ("iOS", 80, 46)]],
    "recent_plays": [
        {"when": "2026-10-04 18:30", "user": "alex", "title": "The Long Voyage"},
        {"when": "2026-10-04 17:30", "user": "sam", "title": "Harbor Lights - S2E5"},
        {"when": "2026-10-04 14:30", "user": "jordan", "title": "Quiet Hours - S1E4"},
        {"when": "2026-10-04 10:30", "user": "riley", "title": "Low Tide - Undertow"},
    ],
}


def lib(name, counts, size_gb, res, unavailable=0, unmatched=0, added=()):
    return {"name": name, "counts": counts,
            "media": {"size_gb": size_gb, "resolution": res, "unavailable_files": unavailable},
            "housekeeping": {"unmatched_count": unmatched},
            "recently_added": [{"title": t, "added": d} for t, d in added]}


growth_gb = [420, 380, 610, 350, 290, 480, 1350, 520, 410, 560, 690, 180]
growth_items = [96, 88, 140, 80, 66, 110, 240, 118, 94, 126, 150, 42]
growth_months = [f"2025-{m:02d}" for m in (11, 12)] + [f"2026-{m:02d}" for m in range(1, 11)]
library = {
    "server": {"name": "Media NAS", "version": "1.41.1"},
    "totals": {"size_gb": 42100, "files": 9412},
    "growth": {"added": sum(growth_items), "gb": float(sum(growth_gb)),
               "months": [{"month": m, "added": n, "gb": float(g)}
                          for m, n, g in zip(growth_months, growth_items, growth_gb)]},
    "libraries": [
        lib("Movies", {"movies": 1284}, 18600, {"4K": 308, "1080p": 820, "720p": 120, "SD": 36}, 1, 4,
            [("The Long Voyage", "2026-10-03"), ("Paper Lanterns", "2026-10-02"), ("Midnight Orchard", "2026-10-01")]),
        lib("TV Shows", {"shows": 212, "episodes": 6930}, 21100, {"4K": 624, "1080p": 5600, "720p": 600, "SD": 106}, 0, 3,
            [("Harbor Lights S2E6", "2026-10-03"), ("Quiet Hours S1E3", "2026-10-02"), ("North of Nowhere S4E1", "2026-10-01")]),
        lib("Music", {"artists": 140, "albums": 520, "tracks": 1150}, 2300, {}, 0, 0,
            [("Low Tide (album)", "2026-10-03")]),
        lib("Home Videos", {"movies": 38}, 100, {"1080p": 30, "720p": 6, "SD": 2}, 0, 0,
            [("Beach Trip 2026", "2026-10-03")]),
    ],
}


def person(name, kind, libraries, last, status="accepted"):
    return {"name": name, "kind": kind, "status": status, "libraries": libraries, "last_played": last}


sharing = {
    "people": [
        person("jordan", "home", ["Movies", "TV Shows"], "2026-10-04"),
        person("sam", "home", "all", "2026-10-04"),
        person("Kids", "managed", ["Movies", "TV Shows"], "2026-08-20"),
        person("alex", "friend", ["Movies", "TV Shows"], "2026-10-04"),
        person("casey", "friend", ["Movies", "Music", "TV Shows"], "2026-10-03"),
        person("drew", "friend", None, None, status="pending"),
        person("morgan", "friend", ["Movies"], "2026-10-01"),
        person("riley", "friend", ["Movies", "Music", "TV Shows"], "2026-10-04"),
        person("taylor", "friend", ["Movies"], "2026-05-17"),
    ],
    "libraries": [{"title": t, "shared_with_count": n} for t, n in
                  [("Movies", 8), ("TV Shows", 6), ("Music", 3), ("Home Videos", 1)]],
    "totals": {"people": 9, "by_kind": {"home": 2, "managed": 1, "friend": 6},
               "by_status": {"accepted": 8, "pending": 1}},
    "worth_a_look": [
        {"kind": "old_pending_invite", "people": ["drew"], "days": 30},
        {"kind": "inactive", "people": ["taylor"], "days": 90},
        {"kind": "all_libraries", "people": ["sam"]},
        {"kind": "downloads_allowed", "people": ["alex", "riley"]},
    ],
}

def title(name, gb, added, last=None, episodes=None):
    t = {"title": name, "added": added, "gb": gb, "last_finished": last}
    if episodes:
        t["episodes"] = episodes
    return t


unwatched = {
    "months": 6, "cutoff": "2026-04-04", "source": "tautulli", "fallback_reason": None,
    "history_since": "2022-03-12", "history_capped": False,
    "libraries": [
        {"name": "Movies", "type": "movie", "items": 1284, "library_gb": 18600.0, "unwatched": 168,
         "unwatched_gb": 1900.0, "unwatched_pct": 10.2, "never_finished": 121, "never_finished_gb": 1350.0,
         "titles": [title("Glass Orchard (2019)", 88.0, "2023-02-11", "2024-03-02"),
                    title("The Salt Road (2016)", 74.0, "2024-06-30"),
                    title("Second Harvest (2021)", 61.0, "2023-11-04"),
                    title("Paper Moons (2014)", 58.0, "2022-09-18", "2023-01-07"),
                    title("A Winter Lake (2018)", 52.0, "2024-01-22")]},
        {"name": "TV Shows", "type": "show", "items": 212, "library_gb": 21100.0, "unwatched": 46,
         "unwatched_gb": 1900.0, "unwatched_pct": 9.0, "never_finished": 18, "never_finished_gb": 820.0,
         "titles": [title("Northern Static", 412.0, "2023-05-02", None, 52),
                    title("Lanterns", 69.0, "2022-11-19", "2023-08-14", 31),
                    title("The Night Ferry", 66.0, "2024-02-08", None, 20),
                    title("Copper Coast", 55.0, "2023-07-27", "2024-12-01", 24),
                    title("Field Notes", 49.0, "2024-03-15", None, 16)]},
        {"name": "Home Videos", "type": "movie", "items": 38, "library_gb": 100.0, "unwatched": 0,
         "unwatched_gb": 0.0, "unwatched_pct": 0.0, "never_finished": 0, "never_finished_gb": 0.0, "titles": []},
    ],
    "skipped_libraries": [{"name": "Music", "type": "artist"}],
    "totals": {"unwatched": 214, "unwatched_gb": 3800.0, "library_gb": 39800.0, "unwatched_pct": 9.5,
               "never_finished": 139, "never_finished_gb": 2170.0},
}


# ---------------------------------------------------------------- page and screenshot

def load_dashboard():
    spec = importlib.util.spec_from_file_location("cinemetric_dashboard", DASHBOARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_page(path):
    db = load_dashboard()
    db.friendly_now = lambda: "Sun Oct 4, 2026 at 7:30 PM"
    data = {"library": library, "health": health, "watch": watch, "sharing": sharing, "unwatched": unwatched}
    title, body = db.render(data, {}, hide_names=False)
    page = db.full_page(title, body).replace('<html lang="en">', '<html lang="en" data-theme="dark">')
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def find_browser():
    for name in BROWSERS:
        found = shutil.which(name)
        if found:
            return found
    sys.exit("error: couldn't find Google Chrome or Chromium on this computer.")


def screenshot(browser, page, png):
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", f"--window-size={WIDTH},8000",
                    f"--screenshot={png}", "file://" + page],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def crop_and_save(png):
    """Cut off the empty background below the page and save a progressive JPG. Returns its height."""
    try:
        from PIL import Image
    except ImportError:
        sys.exit("error: Pillow is needed to save the screenshot. Install it with: pip install pillow")
    image = Image.open(png).convert("RGB")
    width, height = image.size
    background = image.getpixel((width - 1, height - 1))
    pixels = image.load()
    last = next(y for y in range(height - 1, -1, -1)
                if any(pixels[x, y] != background for x in range(0, width, 3)))
    if last >= height - BOTTOM_MARGIN:
        sys.exit("error: the page is taller than the screenshot window; raise the window height.")
    image = image.crop((0, 0, width, last + BOTTOM_MARGIN))
    image.save(SCREENSHOT, quality=82, progressive=True, optimize=True)
    return image.size[1]


def update_index(height):
    with open(INDEX, encoding="utf-8") as f:
        html = f.read()
    pattern = r'(<img src="screens/dashboard\.jpg" width="\d+" height=")\d+(")'
    html, count = re.subn(pattern, rf"\g<1>{height}\g<2>", html)
    if count != 1:
        sys.exit("error: couldn't find the dashboard screenshot <img> in website/index.html.")
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    browser = find_browser()
    with tempfile.TemporaryDirectory() as tmp:
        page, png = os.path.join(tmp, "dashboard.html"), os.path.join(tmp, "dashboard.png")
        render_page(page)
        screenshot(browser, page, png)
        height = crop_and_save(png)
    update_index(height)
    print(f"Saved {os.path.relpath(SCREENSHOT, ROOT)} ({WIDTH} x {height}) and updated its height in "
          f"{os.path.relpath(INDEX, ROOT)}.")
    print("Check the image, and update its alt text in index.html if the page has new sections.")


if __name__ == "__main__":
    main()
