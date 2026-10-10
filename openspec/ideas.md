# Ideas for later

Working notes behind the [Roadmap](../README.md#roadmap) in the README. The README says *what* each idea
is; this file records what was worked out about *how* to build it, the catches found while thinking it
through, and the questions still open. Nothing here is a commitment. Each idea still starts as an
OpenSpec change proposal (`/opsx:propose`) before any code is written; use the notes below as the
starting point for that proposal.

Endpoint and command names marked **(to verify)** come from memory of the Plex and Tautulli APIs, not
from this codebase. Check them against a real server before relying on them.

## Ground rules decided so far

These came out of an explore session on 2026-10-05 and apply to every idea below.

- **Audience.** Cinemetric is mainly for the person who runs the Plex server. Viewer-friendly skills
  (like `what-to-watch`) are still welcome.
- **Facts, not advice, on anything destructive.** No skill suggests deleting, replacing or
  re-encoding files. Skills list what's there and why it might be interesting; the user decides. This
  matches how `library-report` already handles duplicates and upgrade candidates.
- **Saving data on the user's computer is fine.** Snapshots (see below) may store summaries locally,
  in the same data folder the dashboard already uses.
- All existing rules still apply: read-only toward Plex and Tautulli, Python standard library only,
  one self-contained script per skill, only known network destinations, credentials never in the chat,
  server text treated as data. See `openspec/specs/conventions` and `openspec/specs/security`.

## Where things stand

```
  Existing skills, each run once (unwatched joins library and watch data):

  library-report   server-health   watch-activity   users-and-shares   unwatched
        └────────────────┴────────────────┴──────────────────┴────────────────┘
                                  ▼
                              dashboard

  The ideas below fall into three groups:
    1. Join areas together     (playback-check is done)
    2. Remember over time      (snapshots and dashboard trends are done)
    3. Go one level deeper     (subtitles and audio per file are done in playback-check)
```

Suggested order: open. (`export` was done on 2026-10-09: an Excel workbook with tabs, built from its own
library read and five other skills' reports, so every website skills group now has six skills. `show-progress`, `title-lookup` and `subtitles-and-languages` were done on
2026-10-07; `show-progress` also covers the old "shows people stopped watching partway" idea. A server
check for the latter found that Plex keeps each person's preferred languages on plex.tv, not on the
server, so it checks against each library's own language unless one is named. Snapshots and "what changed" were done on 2026-10-06, and so were `year-in-review`, dashboard
trends, `episode-gaps`, the former `tv-completeness` idea, and `playback-check`, which turned out cheap: Plex
returns subtitle and audio details for 100 titles per request, so no sampling was needed. The `server-health` settings checks, the
`watch-activity` one person, busiest moment and unfinished titles additions, the `unwatched` skill,
`library-report` growth by month with its dashboard chart, and the `what-to-watch` skill were done on
2026-10-05; `library-report` music details (lossless vs lossy, missing artwork) on 2026-10-06. Hi-res
music (bit depth, sample rate) was left out: it isn't in the track listing and needs a request per
track.)

---

## Updates to existing skills

### `server-health`: busiest hours and the maintenance window

A grid of plays by hour of the day and day of the week, compared with Plex's scheduled maintenance
window, for example "Maintenance runs 2 to 5 AM, but 9% of plays happen then, mostly Saturday nights."

- **Sources:** Tautulli's `get_plays_by_hourofday` and `get_plays_by_dayofweek` **(to verify)**;
  without Tautulli, count Plex history entries by `viewedAt` (finished plays only, so say so).
  `server-health` already reads the butler (maintenance) window.
- **Catch:** times must be in the server's local time, and Tautulli reports in its own configured
  time zone.

### `library-report`: Dolby Vision and HDR10+

HDR is already counted. Count Dolby Vision (and its profile, where Plex gives it) and HDR10+
separately, since Dolby Vision is the format most likely to look wrong or transcode on some devices.

- **Catch:** check whether these details are in the library listing or only in each title's detail
  page. If only in details, use `playback-check`'s batches of 100.

### `what-to-watch`: something we can all watch, and more like this

- **Together:** titles none of several Plex Home members have watched. Needs each member's watched
  status, which the owner's token may not give **(to verify)**; with Tautulli, use history per person.
- **More like this:** Plex's own list of similar titles for one title
  (`/library/metadata/{id}/similar` **(to verify)**), limited to titles on the server.

### `unwatched`: per person

- **Per person:** "what Sam hasn't touched" as well as "what nobody has touched". Same rules, history
  filtered to one person, as `watch-activity --user` does.
- Shows people stopped watching partway through are covered by `show-progress` (see
  `openspec/specs/show-progress`). It turned out Plex's own history is enough too, since a person's
  place only needs finished episodes.

### `changes`: growth rate

Snapshots already record storage over time, so the trends output could say "you're adding about 1.2 TB
a month" over the saved period.

- **Catch:** Plex doesn't report free disk space, so there's no "full by" date unless the user gives
  the disk size. Don't guess it.

### Snapshots

Snapshots and dashboard trends are described in `openspec/specs/changes` and
`openspec/specs/dashboard`.

**Open questions:** should the dashboard's "Since" section compare with about a week ago instead of
the previous day? Should snapshots be opt-out for people who don't want anything saved?

### `year-in-review`

Left out of the first version (see `openspec/changes/archive/*-year-in-review/design.md`):

- **Favorite genres.** Genres aren't in Tautulli's history rows or Plex's history entries. `watch-mix`
  (see `openspec/specs/watch-mix`) already solves this: Plex's genre filter, one request per genre,
  gives every title's full genre list (listings show at most two), and plays are matched to titles in
  steps (rating key, guid, title and year) because rating keys change when files are replaced. Reuse
  that rather than per-title lookups.
- **Compared with last year.** The same counting run twice; easy once someone asks.
- **Hours from Plex alone.** Finished plays times each title's length. `watch-mix` does this with
  lengths from the library listing, so no request per title is needed.

### `export`

The workbook could gain more tabs on the same plumbing (each runs another skill's script), and
people's viewing could be added on request.

- **More tabs:** unwatched titles (`unwatched`), collections and playlists
  (`collections-and-playlists`), or library growth by month (`library-report`).
- **`--with-people`:** a "last watched by" column. **Catch:** the workbook is a file that may later be
  shared, so names stay out unless asked for, and SKILL.md should say the file then holds names.
- **Music:** one row per album, with lossless or lossy, from the listings `library-report` already
  reads.

### `watch-activity`

- **Busiest moment for one person:** Tautulli's `most_concurrent` stat ignores `user_id` (checked on
  v2.18.2), so with `--user` the report leaves it out. It could be worked out from that person's
  history `started` / `stopped` times instead. Only worth it if someone asks.

---

## Mods

### Heads-up toast

A one-time notice when a session starts, read from the newest snapshot without contacting the server,
for example "Plex update available · 12 files unavailable". Off by default, like `status`.

- Reuses the status line's snapshot reading, so it never contacts Plex.
- **Catch:** a snapshot can be weeks old. Say how old, as the status line does.

### Guard log

A `/cinemetric-guard log` command listing recent commands the guard stopped and why, so the user can
see it working and spot false alarms.

- **Catch:** a blocked command can contain a token or API key. Store it with the same hiding the guard
  already applies to command output, and keep the log in memory for the session only, or in a private
  file that's pruned.

### Now Playing: total bandwidth and the exact transcode reason

A total bandwidth line at the top of the panel, and the reason for each transcode (for example "PGS
subtitles" or "DTS audio") using the same rules as `playback-check`.

- **Catch:** the session listing gives the transcode decision but not always the reason; check what
  `/status/sessions` includes **(to verify)** before promising it.
