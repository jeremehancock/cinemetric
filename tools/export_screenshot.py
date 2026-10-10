#!/usr/bin/env python3
"""Retake the website's export screenshot (website/screens/export.jpg).

Builds a workbook from made-up titles with the real export script's own tab and file code (no Plex
server is contacted), opens it on its Movies tab, zoomed in, in LibreOffice Calc on a virtual screen (Xvfb), takes
a screenshot, crops it to the sheet and its row of tabs, saves it as a JPG and updates the image's
size in website/index.html. Run it from anywhere after changing how the workbook looks:

    python3 tools/export_screenshot.py

Needs LibreOffice, Xvfb (xvfb-run), ImageMagick's `import`, and Pillow (`pip install pillow`). This
is a development tool: it isn't part of the plugin or the website, so unlike the skill scripts it may
use a package outside the standard library.

The titles below are invented, and so are every number and date.
"""

import datetime
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "plugins", "cinemetric", "skills", "export", "scripts", "export.py")
SCREENSHOT = os.path.join(ROOT, "website", "screens", "export.jpg")
INDEX = os.path.join(ROOT, "website", "index.html")
SCREEN = (1280, 800)
# The website shows the picture about 450 pixels wide, so the sheet is zoomed in and only its first
# columns (library, title, year, added) are kept, wide enough for every tab name.
ZOOM = 160
CROP_WIDTH = 900
WAIT_SECONDS = 25
# What's cut from the virtual screen: LibreOffice's menus, toolbars and any notice bar above the column
# letters (found by looking for the highlighted column A letter), everything right of CROP_WIDTH, and
# the status bar under the row of tabs.
STATUS_BAR_HEIGHT = 24

# ---------------------------------------------------------------- made-up sample titles

# (title, year, minutes, resolution, video, audio, channels, GB, watched, collections)
MOVIES = [
    ("A Quiet Engine", 2023, 131, "4K", "hevc", "truehd", 8, 61.40, "No", ""),
    ("Copper Valley Nights", 2011, 104, "1080p", "h264", "dca", 6, 11.82, "Yes", ""),
    ("Glasshouse", 2018, 97, "1080p", "hevc", "eac3", 6, 6.35, "Yes", "Award Winners"),
    ("Harbor Lights", 1987, 112, "1080p", "h264", "aac", 2, 9.10, "Yes", "Harbor Lights Collection"),
    ("Harbor Lights II", 1990, 108, "1080p", "h264", "aac", 2, 8.76, "Partly", "Harbor Lights Collection"),
    ("Low Tide", 2004, 96, "720p", "h264", "ac3", 6, 4.21, "No", ""),
    ("Midnight Orchard", 2016, 121, "4K", "hevc", "eac3", 6, 38.90, "Yes", "Award Winners"),
    ("North of Nowhere", 2009, 118, "1080p", "h264", "dca", 6, 12.44, "No", ""),
    ("Paper Lanterns", 2022, 112, "4K", "hevc", "truehd", 8, 55.02, "Yes", "Award Winners"),
    ("Quiet Hours", 1995, 101, "SD", "mpeg4", "mp3", 2, 1.38, "Yes", ""),
    ("Salt and Static", 2020, 109, "1080p", "hevc", "eac3", 6, 7.65, "No", ""),
    ("Satellite Hearts", 2013, 94, "1080p", "h264", "aac", 2, 5.12, "Yes", ""),
    ("Second Summer", 2018, 98, "1080p", "hevc", "eac3", 6, 6.07, "Partly", ""),
    ("Small Hours Bakery", 2015, 89, "720p", "h264", "aac", 2, 3.33, "Yes", ""),
    ("The Glass Coast", 2021, 104, "4K", "hevc", "eac3", 6, 33.18, "No", ""),
    ("The Long Voyage", 2019, 148, "4K", "hevc", "truehd", 8, 72.66, "Yes", "Award Winners"),
    ("The Night Desk", 1999, 115, "1080p", "h264", "dca", 6, 13.02, "Yes", ""),
    ("Tin Roof Weather", 2007, 92, "1080p", "h264", "ac3", 6, 7.80, "No", ""),
    ("Under the Copper Moon", 1974, 126, "1080p", "h264", "flac", 1, 18.47, "No", "Classics"),
    ("Velvet Signal", 2012, 106, "1080p", "h264", "dca", 6, 10.59, "Yes", ""),
    ("Wildflower Radio", 2017, 99, "1080p", "hevc", "eac3", 6, 5.94, "Yes", ""),
    ("Winter Postcards", 2014, 93, "1080p", "h264", "ac3", 6, 7.21, "Yes", "Holiday"),
    ("Yesterday's Lighthouse", 1962, 102, "SD", "mpeg2video", "ac3", 2, 3.95, "No", "Classics"),
    ("Zero Hour Garden", 2024, 117, "4K", "hevc", "truehd", 8, 58.31, "No", ""),
]
SHOWS = [("Harbor Lights", 2015, 40), ("Quiet Hours", 2019, 24), ("The Night Desk", 2021, 16)]


def load_export():
    spec = importlib.util.spec_from_file_location("cinemetric_export", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(ex, **fields):
    return [fields.get(name) for name in ex.ROW_FIELDS]


def sample_rows(ex):
    added = datetime.date(2026, 3, 1)
    rows = []
    for i, (title, year, minutes, res, video, audio, channels, gb, watched, collections) in enumerate(MOVIES):
        rows.append(row(ex, Library="Movies", Type="Movie", Title=title, Year=year,
                        Added=added + datetime.timedelta(days=7 * i), **{
                            "Length (min)": minutes, "Resolution": res, "Video codec": video,
                            "Audio codec": audio, "Audio channels": channels, "Container": "mkv",
                            "Size (GB)": gb, "Versions": 1, "Unavailable": "No", "Content rating": "PG-13",
                            "Watched": watched,
                            "Last watched": added + datetime.timedelta(days=9 * i) if watched != "No" else None,
                            "Collections": collections or None}))
    for title, year, episodes in SHOWS:
        rows.append(row(ex, Library="TV Shows", Type="Show", Title=title, Year=year, Added=added, **{
            "Resolution": "1080p", "Video codec": "h264", "Audio codec": "eac3", "Audio channels": 6,
            "Container": "mkv", "Size (GB)": round(episodes * 1.4, 2), "Episodes": episodes,
            "Episodes unavailable": 0, "Watched": "Partly", "Episodes watched": episodes // 2}))
    return rows


def sample_workbook(ex):
    """The real script's tabs, filled with made-up rows, opening on the Movies tab."""
    rows = sample_rows(ex)
    sheets = []
    for name in ex.TABS:
        if name in ex.LIST_TABS:
            sheets.append(ex.list_sheet(name, rows, "shows", []))
        else:
            sheet = ex.Sheet(name, None if name == "Server" else ("Library", "Title"))
            sheet.note("Filled in from the matching skill's report.")
            sheets.append(sheet)
    data = ex.workbook_bytes(sheets)
    # Open on the Movies tab (the second) instead of the first.
    source, out = zipfile.ZipFile(io.BytesIO(data)), io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            text = source.read(name).decode("utf-8")
            if name == "xl/workbook.xml":
                text = text.replace('activeTab="0"', 'activeTab="1"')
            elif name == "xl/worksheets/sheet1.xml":
                text = text.replace(' tabSelected="1"', "")
            elif name == "xl/worksheets/sheet2.xml":
                text = text.replace('<sheetView workbookViewId="0"',
                                    f'<sheetView workbookViewId="0" tabSelected="1" zoomScale="{ZOOM}" '
                                    f'zoomScaleNormal="{ZOOM}"')
            target.writestr(name, text)
    return out.getvalue()


# ---------------------------------------------------------------- screenshot

PROFILE = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema">
<item oor:path="/org.openoffice.Office.Linguistic/SpellChecking"><prop oor:name="IsSpellAuto" oor:op="fuse"><value>false</value></prop></item>
</oor:items>
"""


def need(program):
    if not shutil.which(program):
        sys.exit(f"error: {program} is needed. Install LibreOffice, Xvfb and ImageMagick first.")


def screenshot(workbook, png, home):
    """Open the workbook in LibreOffice Calc on a virtual screen and capture the screen."""
    profile = os.path.join(home, ".config", "libreoffice", "4", "user")
    os.makedirs(profile)
    with open(os.path.join(profile, "registrymodifications.xcu"), "w", encoding="utf-8") as f:
        f.write(PROFILE)
    env = dict(os.environ, HOME=home, SAL_USE_VCLPLUGIN="gen")
    env.pop("WAYLAND_DISPLAY", None)
    inner = (f"soffice --nologo --norestore --nofirststartwizard --calc '{workbook}' >/dev/null 2>&1 & "
             f"sleep {WAIT_SECONDS}; import -window root '{png}'; kill $! 2>/dev/null; true")
    subprocess.run(["xvfb-run", "-a", "-s", f"-screen 0 {SCREEN[0]}x{SCREEN[1]}x24", "sh", "-c", inner],
                   env=env, check=True, timeout=WAIT_SECONDS + 60)


def column_edge(pixels, top, limit):
    """The right edge of the last column that fits within `limit`, so no column is cut in half. The
    borders between column letters are darker than the letters' grey background."""
    y = top + 4
    background = pixels[limit // 2, y]
    edges = [x for x in range(100, limit) if sum(pixels[x, y]) < sum(background) - 60]
    return (max(edges) + 1) if edges else limit


def crop_and_save(png):
    try:
        from PIL import Image
    except ImportError:
        sys.exit("error: Pillow is needed to save the screenshot. Install it with: pip install pillow")
    image = Image.open(png).convert("RGB")
    width, height = image.size
    pixels = image.load()
    # The column letters start where column A's letter is highlighted (the selected cell is A1).
    top = next((y for y in range(height // 2)
                if (lambda r, g, b: r > 100 and g < 60 and b < 60)(*pixels[60, y])), None)
    if top is None:
        sys.exit("error: couldn't find the sheet in the screenshot; did LibreOffice open the workbook?")
    image = image.crop((0, top, column_edge(pixels, top, min(CROP_WIDTH, width)), height - STATUS_BAR_HEIGHT))
    image.save(SCREENSHOT, quality=88, progressive=True, optimize=True)
    return image.size


def update_index(size):
    with open(INDEX, encoding="utf-8") as f:
        html = f.read()
    pattern = r'<img src="screens/export\.jpg" width="\d+" height="\d+"'
    html, count = re.subn(pattern, f'<img src="screens/export.jpg" width="{size[0]}" height="{size[1]}"', html)
    if count != 1:
        sys.exit("error: couldn't find the export screenshot <img> in website/index.html.")
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    for program in ("soffice", "xvfb-run", "import"):
        need(program)
    ex = load_export()
    with tempfile.TemporaryDirectory() as tmp:
        workbook, png = os.path.join(tmp, "plex-export.xlsx"), os.path.join(tmp, "export.png")
        with open(workbook, "wb") as f:
            f.write(sample_workbook(ex))
        screenshot(workbook, png, os.path.join(tmp, "home"))
        size = crop_and_save(png)
    update_index(size)
    print(f"Saved {os.path.relpath(SCREENSHOT, ROOT)} ({size[0]} x {size[1]}) and updated its size in "
          f"{os.path.relpath(INDEX, ROOT)}.")
    print("Check the image, and update its alt text in index.html if the workbook has new columns or tabs.")


if __name__ == "__main__":
    main()
