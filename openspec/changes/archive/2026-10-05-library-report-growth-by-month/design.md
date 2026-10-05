## Context

`library_report.py` already fetches every movie, episode and track with `addedAt` (a Unix
timestamp of when Plex added the item) and each version's file sizes. `recent()` already turns
`addedAt` into a local date. Growth by month is a matter of grouping what's already in memory.

## Goals / Non-Goals

**Goals:**
- Answer "how much did I add each month, and how much space did it take?" per library and overall.
- Output that is easy to chart (a fixed list of months with no gaps).
- A "Storage added per month" chart on the dashboard.
- No new Plex requests, no new dependencies.

**Non-Goals:**
- Items *removed* over time. Plex doesn't keep deleted items, so this needs snapshots (separate
  Roadmap item).
- Music details (lossless vs lossy, missing album art): still on the Roadmap.
- Per-library growth charts on the dashboard. One combined chart is enough for an overview; the
  per-library numbers are in the library report.

## Decisions

- **What is counted per library type.** Movies for movie libraries, episodes for TV, tracks for
  music: the same items the `media` breakdown counts files for, so a library's growth sizes add up
  to (at most) its `size_gb`. Alternative: albums for music, which reads more naturally, but albums
  have no file sizes and adding up their tracks would mean a second grouping step. Tracks keep every
  library on one rule; SKILL.md says "tracks" when presenting music.
- **Size is today's size.** `gb` is what the files added that month take up now. If a file was
  later replaced with a bigger version, it counts at its new size in its original month. The library
  listing has no history of file changes, so this is the only option without snapshots; SKILL.md
  says it plainly.
- **Fixed window of months, zeros included.** Default 12 months, ending with the current month,
  option `--growth-months` (0-120). Listing every month back to the first item would make the output
  huge on old servers and uneven to chart. Including zero months means a reader or chart never has
  to fill gaps.
- **Calendar months in local time**, the same as `recently_added`, so dates in the report agree.
  Month keys are built by stepping back from the current year and month, not by subtracting days.
- **One small helper**, `growth(items, months)`, returning `{"added", "gb", "months": [...]}` with
  an internal byte total; `build_report` adds the libraries' rows month by month for the top-level
  section. Bytes are summed and rounded to GB only at the end, so rounding doesn't drift.
- **Dashboard chart shows storage, not item counts.** Item counts mix movies, episodes and tracks
  (one album can add 15 tracks), so a bar of "items" means little. Storage is comparable across
  library types and answers "how fast is my drive filling up?". The item count goes in each bar's
  tooltip and in the total next to the heading.
- **One chart function for both charts.** `svg_chart` today takes the watch report's daily rows and
  reads `plays` from them. It becomes a general bar chart that takes a list of bars (value, axis
  label, tooltip) plus a value formatter for the axis, so plays-per-day and storage-per-month share
  the drawing, the wide/narrow versions, the peak highlight and the hover areas. The plays chart must
  come out exactly the same as before; a test compares it. The alternative, a second copy of the
  chart code, would drift.
- **Axis in GB or TB.** Ticks use the dashboard's existing `size()` formatter. The round tick steps
  from `nice_step` work in whole GB; when the peak is under 1 GB the axis still uses a step of 1 GB,
  which is fine since such small months barely show anyway.
- **Month labels** are the short month name ("Mar"), with the year added ("Jan '26") on the first
  label drawn in each year. The narrow phone chart labels only every third month and can skip
  January, so "first label in a new year" is used rather than "January", which keeps the year change
  visible on both charts.
- **Dashboard keeps running `library_report.py` with no extra options**, so the chart covers the
  default 12 months.

## Risks / Trade-offs

- [Re-added items look new] A library re-scan or moving files to a new drive can give many items a
  new `addedAt`, showing a big spike in one month. → SKILL.md mentions this as a likely reason when
  one month stands far above the rest.
- [Current month is partial] → The last row is the month in progress; SKILL.md says so.
- [Changing the shared chart code breaks the plays chart] → A test checks the plays-per-day SVG is
  unchanged for a fixed input.
- [One huge month flattens the rest of the chart] A re-scan can make one month tower over the
  others. → Accepted: the tooltip still gives exact numbers, and it's an honest picture of what Plex
  reports.
- [Output size] 12 rows per library is small; at the 120-month limit it's still a few kilobytes.
