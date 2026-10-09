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

Suggested order: open. (`show-progress`, `title-lookup` and `subtitles-and-languages` were done on
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

## New skills

Each new skill fills one group of the website's skills section, so the three groups stay even (six
skills each): `collections-and-playlists` goes in **Your library**, `watch-mix` in **Watching** and
`export` in **Your server**. `export` could fit Your library too, but it sits beside `dashboard` and
`changes`, the other skills that save files on the user's computer.

### `collections-and-playlists`

Collections and playlists on the server: how many titles each holds, collections with only one title,
smart vs regular collections, playlists with items Plex can no longer find, and titles that aren't in
any collection.

- **Sources:** `/library/sections/{id}/collections` and `/playlists` **(to verify)**, plus each
  one's items.
- **Catch:** playlists belong to the account that made them. With the owner's token only the owner's
  playlists are visible; say so instead of implying they're all there.
- Facts only: no "you should make a collection for ..." suggestions.

### `export`

Saves a listing of a library as a CSV file on the user's computer (title, year, library, resolution,
codecs, size, added date, watched status, collections), for a spreadsheet.

- **Where it goes:** the same data folder the dashboard uses, with the same private file permissions,
  unless the user names a folder.
- **Catch:** the CSV is a file on disk that may later be shared. Leave people's names out by default;
  a `--with-people` option could add "last watched by".
- **Catch:** spreadsheet programs run text that starts with `=`, `+`, `-` or `@` as a formula. Titles
  from the server must be escaped against that (prefix with `'`).

### `watch-mix`

What gets watched compared with what's on the server: each genre's, decade's and resolution's share of
the library next to its share of plays and watch time, for example "Horror is 18% of your movies but
3% of what's watched; anime is 5% of your shows but 22% of watch time." For the whole server or one
person, over the last 12 months or a period the user names.

- **Sources:** library listings for what's on the shelf (as `library-report` reads them); Tautulli
  history, or Plex's own history without it, for plays, the same way `watch-activity` does.
- **Catch:** genres aren't in history entries, so each played title needs its genres looked up. Use
  batches like `playback-check`'s instead of one request per title. The same lookup would give
  `year-in-review` its favorite genres.
- **Catch:** a title can have several genres, so the shares won't add up to 100%. Say so.
- **Catch:** without Tautulli, Plex only records finished plays, so watch time is finished plays times
  each title's length. Say which was used.
- **Privacy:** for the whole server, name no one, like `year-in-review`. One person only when asked.
- Facts only: no "you should add more anime" or "remove horror" suggestions.

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

- **Favorite genres.** Genres aren't in Tautulli's history rows or Plex's history entries, so each
  title needs a metadata lookup; a batched one like `playback-check`'s would keep it cheap.
- **Compared with last year.** The same counting run twice; easy once someone asks.
- **Hours from Plex alone.** Finished plays times each title's length, if that can be had without one
  request per title.

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
