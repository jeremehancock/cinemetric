## Context

Today each report script fetches from Plex (and plex.tv or Tautulli), prints JSON, and forgets
everything. The dashboard runs five of these scripts side by side and writes a page. Nothing is kept
between runs except the dashboard's own state file and page, which live in the data folder
(`$XDG_DATA_HOME/cinemetric`, private `700` folder, `600` files).

Facts that shape the design:
- The reports keep only short example lists (for example the first 15 unavailable files), so a
  snapshot can't just be a saved report. It needs its own full lists of ids and names.
- `library_report.py` already reads every movie, show, episode, album and track in memory, so full
  lists cost no extra requests. Plex's `ratingKey` is a stable id for an item while it stays in the
  library; a removed and re-added item gets a new one.
- Every script requests `/`, whose `machineIdentifier` identifies the server. That's how snapshots
  from different servers are kept apart.
- The "Self-contained scripts" rule means shared code is copied into each script that needs it.

## Goals / Non-Goals

**Goals:**
- Answer "what changed on my Plex?" since the last time, or over the last N days.
- Show the same changes in the plain reports and on the dashboard without fetching anything twice.
- Write each comparison once, and keep the copied code small.
- Keep snapshot files private, small, self-pruning and safe to read even if damaged or edited.

**Non-Goals:**
- Weekly digest or any scheduled run (later change).
- Trend charts over many snapshots (the data will be there; charts are a later change).
- Snapshots of watch activity or unwatched titles. Watch history already has dates, and play history
  about people shouldn't be copied onto disk.
- Remembering more than one server's comparisons together.

## Decisions

**Each report owns its area: build it, compare it.** `library_report.py`, `server_health.py` and
`users_and_shares.py` each know how to turn their live data into their part of a snapshot ("area"),
and how to compare that area with the same area from an older snapshot. They read snapshots but
never write them. With `--snapshot-items` they also print their area as `snapshot`.

The changes script then does no comparing at all: it runs the three reports, prints their
`since_snapshot` sections, and saves their `snapshot` blocks. The dashboard does the same.

*Alternatives considered:* (a) the changes script does every comparison and the reports copy it.
That puts the library comparison (the biggest piece) in two places. (b) Only the changes script
compares, and reports show nothing. The user asked for changes in the reports too.

**Only the changes script writes.** Saving, merging the same day's file, and pruning old files
happen in `changes.py` only, in the default run and in `save` mode. `save` reads
`{"library": <report>, "health": <report>, "sharing": <report>}` (any subset) from stdin, so the
dashboard can save what it already fetched. `save` contacts nothing.

**What each script copies.** A small helper to find the data folder and the snapshot folder, list a
server's snapshot files, and read one safely (size limit, JSON check, `format` check, server id
check). Four copies: three reports plus `changes.py`. The conventions spec names it so a fix to one
copy must reach every copy, and a test runs the same checks against every copy.

**Layout and format.** `<data folder>/snapshots/<server id>/<YYYY-MM-DD>.json`, local date. Server id
is the server's `machineIdentifier`, used only if it is letters and digits. One file holds:

```
{ "format": 1, "cinemetric_version": "0.18.0", "date": "2026-10-06",
  "saved_at": "2026-10-06T21:14:00-06:00", "server_name": "...",
  "library": {...}, "health": {...}, "sharing": {...} }     # any area may be missing
```

- `library`: per library (keyed by Plex's library key): `name`, `type`, `counts`, `size_gb`,
  `items` (`{ratingKey: label}` for movies, shows and albums), `episodes` (`{show ratingKey: count}`
  for TV libraries) and `unavailable` (`{ratingKey: label}` of items with a file Plex marks
  unavailable).
- `health`: `version`, `update_version` (null when no update), `remote_access` (Plex's mapping state).
- `sharing`: `people`, each `{name, kind, status, libraries, allow_downloads}`. Not last played,
  restrictions content, emails or ids.

Episodes are stored as counts per show rather than one entry per episode. That keeps a 50,000-episode
library down to a few thousand entries while still saying "Show X: 3 episodes added". Tracks aren't
listed; albums are.

**Choosing the snapshot to compare with.** The newest file for this server, in a known format, that
has the report's area and whose date is before today. With `--since N`: the newest whose date is at
least N days before today; if none is that old, the oldest earlier-day file, and `since_snapshot`
says how old it really is. Comparing with an earlier *day* (not the run an hour ago) keeps results
useful when the dashboard and a report both run on the same day.

**Same-day saves merge.** A second save on the same day replaces the areas it has and keeps the
areas it doesn't, so a dashboard build where sharing failed doesn't wipe out the morning's sharing
area. Files are written to a temporary file in the same folder and renamed into place.

**Pruning.** After a save, files dated more than 90 days before today are deleted, in every server's
folder. Only names matching `YYYY-MM-DD.json` are touched; anything else in the folder is left alone.

**Example lists stay bounded.** `since_snapshot` gives full counts and up to 25 named examples per
list, so a big import (or a drive going offline) doesn't produce a huge report.

**Library comparison rules.**
- Libraries match by key. A key only in the new data is a new library; only in the old, removed; a
  different name is a rename. New and removed libraries report their counts, not every title.
- Titles match by `ratingKey`. A re-match in Plex keeps the key; a delete and re-add gives a new one,
  so it shows as one removed and one added.
- Unavailable: in `unavailable` now but not before is "became unavailable"; the reverse, while the
  item still exists, is "available again".
- When the old snapshot came from a run that only covered some libraries, that can't happen: the
  reports refuse `--snapshot-items` together with `--library`. A `--library` run still compares the
  libraries it covers.

**Sharing comparison rules.** People match by name and kind. Several pending "invited by email"
entries can't be told apart, so they're compared as a count.

## Risks / Trade-offs

- [Four copies of the snapshot reading helper drift apart] → Kept small; named in the conventions
  spec; one test runs the same checks against each copy.
- [Snapshot files edited or damaged by someone] → Read with a size limit (50 MB), parsed as JSON only,
  wrong format or server id skipped, every text value cleaned and cut to 120 characters again before
  it is printed or put on the dashboard.
- [Disk use] → Roughly 100 KB to a few MB per day for large libraries, at most 90 files per server.
- [The first run shows nothing] → `since_snapshot` is null with no earlier snapshot; SKILL.md tells
  Claude to say the first snapshot was saved and changes appear from the next day.
- [Plex rescans or re-adds files and items look removed and added] → Accepted. The report states
  facts; SKILL.md mentions that a removed-and-added pair with the same name usually means Plex
  re-added it.
- [Clock or time zone changes] → Dates are local dates; at worst one comparison picks a neighbouring
  day.

## Migration Plan

Nothing to migrate: no snapshots exist yet. Older Cinemetric versions ignore the snapshot folder.
Rolling back leaves the folder in place; `changes.py forget` (or deleting the folder) removes it.

## Open Questions

- Confirm defaults with the user: always on, 90 days, one per day.
- Should the dashboard's "Since" section compare with the previous day (default rule) or with about a
  week ago? Default rule for now; easy to change later.
