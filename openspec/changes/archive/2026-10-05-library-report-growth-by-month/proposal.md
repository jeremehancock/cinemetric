## Why

The library report shows what's on the server today and the last few things added, but not how fast
the library is growing. "How much did I add this year?" and "when did the drive start filling up?"
are common questions for anyone running a Plex server, and today the only way to answer them is to
scroll through Plex by date.

`library-report` already downloads every movie, episode and track along with the date each was
added (`addedAt`) and its file sizes. So it can answer these questions with no extra requests to
Plex. This is the low-effort half of the `library-report` Roadmap item; the music details half stays
on the Roadmap.

## What Changes

- Each movie, TV and music library in the report gets a `growth` section: one row per month for the
  last 12 months (oldest first), each with how many items were added that month and how much storage
  they use now. Months with nothing added are included as zeros, so the list has no gaps.
- The report gets a top-level `growth` section that adds up every reported library, month by month.
- A new `--growth-months N` option (default 12, limited to 0-120) sets how many months are covered.
  0 leaves the months out but keeps the section.
- The dashboard's Library section gets a "Storage added per month" bar chart built from the
  combined `growth` section, drawn the same way as the existing plays-per-day chart, with the total
  added over the period next to the heading.
- `SKILL.md` learns the new fields and triggers on questions about how fast the library is growing
  or how much was added in a month or year.
- README: the `library-report` Roadmap item keeps only the music details part. `openspec/ideas.md`:
  the growth note is removed. Website: the library-report and dashboard feature lists mention growth by month.
- Version bump to 0.14.0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dashboard`: a new requirement adds the storage-added-per-month chart to the Library section.
- `library-report`: "Options" adds `--growth-months`; "Report contents" adds the per-library and
  top-level `growth` sections; a new requirement defines how growth is counted.

## Impact

- `plugins/cinemetric/skills/library-report/scripts/library_report.py`: new growth-counting code and
  option; no new Plex requests.
- `plugins/cinemetric/skills/library-report/SKILL.md`: description, field list and presentation.
- `tests/test_library_report.py`: new offline tests for the spec scenarios.
- `README.md` Roadmap, `openspec/ideas.md` and `website/index.html` library-report feature list.
- `VERSION` in all seven scripts, `plugin.json` and `marketplace.json`.
- `plugins/cinemetric/skills/dashboard/scripts/dashboard.py`: the bar chart code is generalized so
  the plays-per-day and storage-per-month charts share it; the Library section adds the new chart.
- `plugins/cinemetric/skills/dashboard/SKILL.md`: mentions the growth chart when describing the page,
  and reads the live online page before updating it, since the Artifact tool refuses to update a page
  the conversation hasn't seen (found while testing: the online copy had not been updated since 0.4.0).
- `tests/test_dashboard.py`: tests for the chart, the all-zero message and a report without growth.
