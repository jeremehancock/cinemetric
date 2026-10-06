## 0. Confirm defaults

- [x] 0.1 Confirm with the user: three blocks (storage over time, titles per library, people with access), line charts, placed right after "Since", and leaving out removed libraries and server health trends. Update proposal, design and specs if any answer differs

## 1. `changes.py trends`

- [x] 1.1 Add the `trends` subcommand with `--server-id`; a server id that fails the existing letters-and-digits check gives the empty result and exit 0
- [x] 1.2 Read every `YYYY-MM-DD.json` dated within the last 90 days (today included) with the existing safe reader, oldest first; skip unreadable files without failing
- [x] 1.3 Build `library`: pick the newest snapshot with a library area for the list of libraries (key, name, type, order); per date fill `size_gb` and each count list, `null` where the area, library or count is missing; `total_size_gb` sums every library that day (removed ones included), `null` when the day has no library area
- [x] 1.4 Build `sharing`: per date `people`, `home`, `managed`, `friend` and `pending`, `null` when the day has no sharing area
- [x] 1.5 Print `server_id`, `days` (90), `dates`, `library`, `sharing`; check no titles or names can reach the output
- [x] 1.6 Measure: generate 90 snapshot files the size of a large library (several MB each) in a temp data folder and time `trends`; note the result in design.md and raise it if it's over a few seconds

## 2. Dashboard

- [x] 2.1 Keep the agreed server id from the reports' `snapshot` blocks before they are dropped; after `changes.py save`, run `changes.py trends --server-id <id>` with a 2-minute limit; on any failure leave trends out without touching `sections_missing`
- [x] 2.2 Add a line-chart helper next to `bar_chart`: inline SVG, wide and narrow versions, x placed by date, `null` breaks the line, a `<title>` tooltip per point with date and value, styled with the existing chart colors in light and dark
- [x] 2.3 Add the Trends section after the Changes section: subtitle (number of snapshot days, first and last date), storage block, one block per library for its main count (`movies`, `episodes`, `albums`, `photos`), people block with pending invites in tooltips; first, latest and change next to each heading; blocks with fewer than two values left out; the one-line message when all are left out
- [x] 2.4 Check the section adds nothing to "Needs a look", doesn't change the overall status, escapes library names, and is the same with names hidden
- [x] 2.5 Build the real dashboard and look at it at desktop and phone widths, in light and dark

## 3. Skills

- [x] 3.1 `changes/SKILL.md`: when the user asks how the library or sharing changed over weeks or months, run `trends` (it picks the current server); describe first, latest and change in plain words; facts only
- [x] 3.2 `dashboard/SKILL.md`: mention the Trends section in what the page shows and that it needs snapshots from two different days

## 4. Tests

- [x] 4.1 `tests/test_changes.py`: lists line up with `dates`; a day missing the sharing area; a renamed library; a removed library still counted in older totals; files older than 90 days and damaged files skipped; no names in the output; a bad server id; no network
- [x] 4.2 `tests/test_dashboard.py`: trends run after save with the right server id; a month of data shows all blocks; one day shows the one-line message; gap spacing by date; a series that is `null` except the latest is left out; trends failing still writes the page and leaves `sections_missing` alone; library name escaped; overall status unchanged
- [x] 4.3 Run the full test suite and fix anything that fails

## 5. Docs and version

- [x] 5.1 README: remove the "Trends on the dashboard" Roadmap item; mention trends in the dashboard's Skills table row
- [x] 5.2 `openspec/ideas.md`: remove the trends note and update "Where things stand"
- [x] 5.3 Check whether the website's dashboard screenshot or text should show the Trends section; retake the screenshot only if the section is in its frame
- [x] 5.4 Bump the version to 0.21.0 in every script's `VERSION`, `plugin.json` and `marketplace.json`
