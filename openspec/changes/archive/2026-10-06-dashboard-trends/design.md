## Context

Snapshots were added in the `snapshots-what-changed` change. `changes.py` is the only script that
writes them; it saves one file per server per day at
`<data folder>/snapshots/<server id>/<YYYY-MM-DD>.json` and deletes files older than 90 days. The
three report scripts read one earlier snapshot each to build `since_snapshot`.

What a snapshot already holds, per area:
- `library`: keyed by library key, each with `name`, `type`, `counts` (for example
  `{"movies": 1970}`, `{"shows": 417, "seasons": 1414, "episodes": 19011}`,
  `{"artists": 251, "albums": 499, "tracks": 6529}`), `size_gb`, and full item lists.
- `sharing`: `people`, each with `name`, `kind` (`home`, `managed`, `friend`), `status`, `libraries`
  and `allow_downloads`. Email invites appear with a fixed placeholder name.
- `health`: `version`, `update_version`, `remote_access`.

The dashboard already runs `changes.py save` after its reports finish, passing them on stdin. Its
charts (`daily_chart`, `growth_chart`) are bar charts built by one `bar_chart` helper as inline SVG,
each in a wide and a narrow version. The page has no scripts and a `default-src 'none'` policy.

A real snapshot for a medium server (about 2,900 titles, 19,000 episodes, 11 people) is about 0.1 MB.

## Goals / Non-Goals

**Goals:**
- Show how the library and sharing changed across all saved snapshots, on the dashboard.
- Read snapshots in one place only, with the same safe reading rules as today.
- Keep the page script-free and rule-based.

**Non-Goals:**
- Changing the snapshot format or saving anything new. Trends use only what is already saved.
- Charts of watch activity (watch history already has its own daily chart).
- Server health trends (version, remote access). They change rarely and the "Since" section already
  names them.
- Filling in missing days. A day with no snapshot has no point.
- A weekly digest or any scheduled run.

## Decisions

**`changes.py` reads the snapshots for trends; the dashboard doesn't.** A new `trends` mode in
`changes.py` takes `--server-id` and prints a compact series. The dashboard calls it right after
`changes.py save`, the same way.

*Why:* `changes.py` already has the snapshot folder helper, the safe reader and the date rules, and
is the one place that knows the file layout. Copying the reader into `dashboard.py` would add a fifth
copy of a helper the conventions spec says must be kept in step.

*Alternatives considered:* (a) `save` also prints the trends. One call fewer, but it mixes writing
with reading and means the `changes` skill couldn't ask for trends without saving. (b) The dashboard
reads the folder itself. Rejected for the copy reason above.

**The server id comes from the reports.** The dashboard already has the `snapshot` blocks from the
library, health and sharing reports before it drops them; it passes their `server_id` (when they
agree) to `trends`. If no report succeeded, or they disagree, the dashboard skips trends.
`trends` applies the existing letters-and-digits check; anything else gives an empty result, not an
error.

**Output shape.** Counts only, oldest day first:

```json
{
  "server_id": "7c85...",
  "days": 90,
  "dates": ["2026-07-10", "2026-07-11", "..."],
  "library": {
    "total_size_gb": [57100.2, 57190.0, "..."],
    "libraries": [
      {"key": "1", "name": "Movies", "type": "movie",
       "size_gb": [20001.4, null, "..."],
       "counts": {"movies": [1960, null, "..."]}}
    ]
  },
  "sharing": {
    "home": [5, 5, "..."], "managed": [2, 2, "..."], "friend": [3, 4, "..."],
    "people": [10, 11, "..."], "pending": [1, 0, "..."]
  }
}
```

Every list lines up with `dates`. A day whose snapshot has no `library` area has `null` in every
library list (and in `total_size_gb`); same for `sharing`. A library missing on a day that has a
library area also gets `null`. Using `null` rather than dropping the day keeps one shared date axis,
which makes the charts and tests simple.

**Which libraries are listed.** Libraries are matched by key, as in `since_snapshot`. Only libraries
present in the newest snapshot that has a library area are listed, using that snapshot's name and
type, in that snapshot's order. A library that was removed has no place on a "how is it going now"
chart, and a renamed one keeps its history because the key didn't change.

**People counts.** `people` counts every entry in that day's sharing area, the same way the
dashboard's Sharing section counts its "People" tile today, so the latest point matches that tile.
`home`, `managed` and `friend` split it by the saved `kind`. `pending` counts entries whose status is
`pending` (email invites included). No names are printed.

**Size of the read.** Every file is still read with the existing reader (regular file, 50 MB cap,
JSON object, `format` 1, text cleaned). The full item lists are parsed and then dropped; only counts
and sizes are kept. At about 0.1 MB a file, 90 files is about 9 MB of JSON, which Python parses in
well under a second.

*Measured:* 90 files of 1.1 MB each (ten times a real 2,900-title library) took 6.6 seconds at
first, almost all of it cleaning every title's text, which trends never prints. The shared reader is
now split in two (in all four copies, kept identical): `load_snapshot` does the safety checks and
`read_snapshot` adds the cleaning. `trends` uses `load_snapshot` and cleans only the library keys,
names, types and count names it prints. The same 90 files then took 1.4 seconds; the real snapshot
folder takes 0.1 seconds.

**Default server.** Without `--server-id`, `trends` uses the server whose folder has the most recent
snapshot, which is the one the user is connected to (every run saves one). That lets the `changes`
skill ask for trends without knowing the id. The dashboard always passes the id.

**Charts.** A new small line-chart helper next to `bar_chart`, producing inline SVG in a wide and a
narrow version, with a `<title>` tooltip on each point (date and value). X positions come from real
dates, so gaps between snapshots look like gaps in time. `null` points break the line. Three blocks:
1. **Storage over time:** `total_size_gb`, with the first and latest value and the change next to the
   heading (for example "57.1 TB → 58.0 TB, +0.9 TB").
2. **Titles per library:** one compact chart per listed library for its main count (`movies`,
   `episodes`, `albums` or `photos`; libraries with no main count are left out), each with first,
   latest and change. Small multiples keep a 19,000-episode library from flattening a 400-album one.
3. **People with access:** `people`, with pending invites in each point's tooltip, first, latest and
   change.

A block is left out when its series has fewer than two non-null points. When every block is left
out, the section shows one line saying trends appear once snapshots from two different days exist.

*Alternative considered:* bar charts using the existing helper. Bars suggest "amount added per
period", which is what the existing growth chart shows; a running total over time reads better as a
line.

**Section placement and failure.** The Trends section goes right after "Since". If `trends` fails,
times out or prints bad JSON, the section is left out and the build carries on, exactly as a failed
`save` does. The dashboard doesn't add a `sections_missing` entry for it, since it's not a report.

## Risks / Trade-offs

- [A very large library makes each snapshot big (item lists), so reading 90 is slow] → The read is
  measured in a task; `trends` keeps a time limit in the dashboard (as `save` has), and if it's too
  slow the follow-up is to store a small per-day summary alongside each snapshot, not to change this
  design's output.
- [Snapshots only exist for days the user ran the dashboard or `changes`] → Charts space points by
  date and say nothing about days without snapshots; the section's subtitle gives the number of
  snapshot days and the date range.
- [People counted differently from the Sharing section] → Both use the same kinds and statuses from
  the sharing report; a test checks the latest trend point matches the Sharing section's count for
  the same data.
- [Library renamed: older points used the old name] → Only the newest name is shown; the history
  stays because it's keyed by library key.

## Open Questions

- Default chart set: storage, titles per library, people with access. Confirm before building
  (task 0.1).
