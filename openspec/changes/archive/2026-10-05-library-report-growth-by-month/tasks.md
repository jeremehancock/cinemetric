## 1. Count growth in the script

- [x] 1.1 Add a helper that builds the list of the last N `YYYY-MM` month keys in local time, oldest first, ending with the current month
- [x] 1.2 Add `growth(items, months)`: group items by the local month of `addedAt` (skip items with none), count them and sum the size of every part of every `Media` entry; return `added`, `gb` and `months` with zero rows for empty months
- [x] 1.3 Add `growth` to movie (over movies), show (over episodes) and music (over tracks) libraries; none for photo or other libraries
- [x] 1.4 In `build_report`, add the top-level `growth` by summing every library's months, keeping byte totals until the final rounding
- [x] 1.5 Add `--growth-months N` (default 12, clamped to 0-120)

## 2. Tests

- [x] 2.1 Add offline tests in `tests/test_library_report.py` for each spec scenario: two months with a gap, added before the period, show library counts episodes, music counts tracks, combined top level, `--growth-months 0`, clamping to 120
- [x] 2.2 Make the tests independent of today's date (fixed clock or `addedAt` values computed from the current month)
- [x] 2.3 Check the existing whole-report tests: photo libraries have no `growth`, only allowed Plex paths are requested
- [x] 2.4 `python3 -m unittest discover -s tests` passes

## 3. Dashboard chart

- [x] 3.1 Generalize `svg_chart` into a bar chart that takes bars (value, axis label, tooltip) and an axis formatter; switch the plays-per-day chart to it with identical output
- [x] 3.2 Add the "Storage added per month" chart to the Library section from the top-level `growth.months` (peak highlighted, wide and narrow versions, "so far" on the current month's tooltip, short month labels with the year on the first label shown in each year)
- [x] 3.3 Show the total size and items added next to the chart heading; one line instead of the chart when every month is zero; nothing when the report has no `growth`
- [x] 3.4 Tests in `tests/test_dashboard.py`: plays chart unchanged, growth chart bars and peak, all-zero message, report without growth, values escaped, overall status unchanged
- [x] 3.5 Dashboard `SKILL.md`: mention the storage-added chart when describing the page
- [x] 3.6 Dashboard `SKILL.md`: read the live online page before updating it (the Artifact tool requires this in each new conversation), check it's an earlier dashboard build, then publish; ask first if it holds anything else (found while testing: the online copy had stopped updating)

## 4. Tell Claude about it

- [x] 4.1 Library report `SKILL.md`: add "how fast is my library growing", "how much did I add this month/year" to the `description` triggers and document `--growth-months` in the run section
- [x] 4.2 Library report `SKILL.md`: describe the `growth` fields; say sizes are today's sizes, the last month is still in progress, music counts tracks, and a single big spike is often a re-scan or a move to a new drive

## 5. Docs

- [x] 5.1 README: trim the `library-report` Roadmap item to the music details only
- [x] 5.2 `openspec/ideas.md`: remove the growth by month note and update "Where things stand"
- [x] 5.3 Website: add growth by month to the library-report and dashboard feature lists in `website/index.html`

## 6. Verify

- [x] 6.1 Run against the real server (if available): output is valid JSON, existing fields unchanged, growth sizes per library add up to no more than `size_gb`, and a recent month matches what Plex's "Recently Added" shows
- [x] 6.2 Run `dashboard.py` against the new report: the growth chart appears and looks right in light and dark mode and at phone width, and the rest of the page is unchanged
- [x] 6.3 `openspec validate library-report-growth-by-month` passes

## 7. Release

- [x] 7.1 Bump the version to 0.14.0 in all seven scripts, `plugin.json` and `marketplace.json`
