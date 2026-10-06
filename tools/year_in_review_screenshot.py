#!/usr/bin/env python3
"""Retake the website's year-in-review screenshot (website/screens/year-in-review.jpg).

Builds a whole-server recap from made-up plays with the real script's own counting and page code (no
Plex server is contacted), takes a screenshot with headless Chrome or Chromium, saves it as a JPG and
updates the image's height in website/index.html. Run it from anywhere after changing how the recap
looks:

    python3 tools/year_in_review_screenshot.py

Needs Google Chrome or Chromium, and Pillow (`pip install pillow`). This is a development tool: it
isn't part of the plugin or the website, so unlike the skill scripts it may use a package outside the
standard library.

The sample plays below are invented: people, titles and numbers are all made up, and a fixed random
seed keeps the screenshot the same until the recap page itself changes.
"""

import argparse
import importlib.util
import os
import random
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashboard_screenshot import crop_and_save as _crop, find_browser, screenshot  # noqa: E402
import dashboard_screenshot  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "plugins", "cinemetric", "skills", "year-in-review", "scripts", "year_in_review.py")
SCREENSHOT = os.path.join(ROOT, "website", "screens", "year-in-review.jpg")
INDEX = os.path.join(ROOT, "website", "index.html")
YEAR = 2025

# ---------------------------------------------------------------- made-up sample plays

PEOPLE = 6
# (kind, title, minutes per play, how many plays, how many different people, months it was popular)
TITLES = [
    ("episode", "Harbor Lights", 52, 140, 4, (1, 2, 3, 10, 11)),
    ("episode", "Quiet Hours", 44, 96, 3, (5, 6, 7)),
    ("episode", "North of Nowhere", 58, 70, 3, (8, 9)),
    ("episode", "The Night Desk", 41, 62, 2, (11, 12)),
    ("episode", "Copper Valley", 47, 48, 2, (2, 3, 4)),
    ("episode", "Small Hours Bakery", 23, 55, 1, (6, 7)),
    ("episode", "Glasshouse", 49, 30, 1, (9, 10)),
    ("movie", "The Long Voyage (2019)", 148, 9, 4, (12,)),
    ("movie", "Paper Lanterns (2022)", 112, 7, 3, (2,)),
    ("movie", "Midnight Orchard (2016)", 121, 6, 3, (10,)),
    ("movie", "The Glass Coast (2021)", 104, 5, 2, (7,)),
    ("movie", "Second Summer (2018)", 98, 4, 2, (8,)),
    ("movie", "Winter Postcards (2014)", 93, 4, 2, (12,)),
    ("movie", "A Quiet Engine (2023)", 131, 3, 1, (3,)),
    ("movie", "Salt and Static (2020)", 109, 2, 1, (5,)),
    ("track", "Low Tide", 4, 260, 3, tuple(range(1, 13))),
    ("track", "Satellite Hearts", 4, 180, 2, (4, 5, 6, 7, 8)),
    ("track", "Wildflower Radio", 3, 150, 1, (1, 2, 3)),
]


def sample_plays(module):
    rng = random.Random(2025)
    plays = []
    for kind, title, minutes, count, viewers, months in TITLES:
        who = rng.sample(range(1, PEOPLE + 1), viewers)
        for i in range(count):
            month = months[i % len(months)]
            day = rng.randint(1, 28)
            started = time.mktime((YEAR, month, day, rng.randint(17, 22), rng.randint(0, 59), 0, 0, 0, -1))
            seconds = int(minutes * 60 * rng.uniform(0.85, 1.0))
            plays.append(module.play(who[i % viewers], kind, title, started, seconds))
    return plays


# ---------------------------------------------------------------- page and screenshot

def load_script():
    spec = importlib.util.spec_from_file_location("cinemetric_year_in_review", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_page(path):
    yr = load_script()
    args = argparse.Namespace(top=6, min_viewers=2)
    end = time.mktime((YEAR + 1, 1, 1, 0, 0, 0, 0, 0, -1))
    report = {
        "year": YEAR, "partial_year": False, "scope": "server", "user": None, "source": "tautulli",
        "history_capped": False, "min_viewers": 2, "hours_unavailable": None,
        "generated_at": "2026-01-02 10:15 CST",
        **yr.summarize(sample_plays(yr), args, "server", True, YEAR, end, False),
    }
    title, body = yr.render(report)
    page = yr.full_page(title, body).replace('<html lang="en">', '<html lang="en" data-theme="dark">')
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def update_index(height):
    with open(INDEX, encoding="utf-8") as f:
        html = f.read()
    pattern = r'(<img src="screens/year-in-review\.jpg" width="\d+" height=")\d+(")'
    html, count = re.subn(pattern, rf"\g<1>{height}\g<2>", html)
    if count != 1:
        sys.exit("error: couldn't find the year-in-review screenshot <img> in website/index.html.")
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    browser = find_browser()
    dashboard_screenshot.SCREENSHOT = SCREENSHOT  # crop_and_save writes here
    with tempfile.TemporaryDirectory() as tmp:
        page, png = os.path.join(tmp, "recap.html"), os.path.join(tmp, "recap.png")
        render_page(page)
        screenshot(browser, page, png)
        height = _crop(png)
    update_index(height)
    print(f"Saved {os.path.relpath(SCREENSHOT, ROOT)} ({dashboard_screenshot.WIDTH} x {height}) and updated "
          f"its height in {os.path.relpath(INDEX, ROOT)}.")


if __name__ == "__main__":
    main()
