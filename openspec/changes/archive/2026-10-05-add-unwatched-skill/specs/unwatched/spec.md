## ADDED Requirements

### Requirement: Sources used
The script `skills/unwatched/scripts/unwatched.py` SHALL request only `/`, `/library/sections`,
`/library/sections/{id}/all` and `/status/sessions/history/all` from the user's Plex server, reading
library items in pages of 500. With Tautulli it SHALL run only `get_tautulli_info` and `get_history`.
The library itself SHALL always come from Plex; only the plays can come from Tautulli.

#### Scenario: Building a report with Tautulli
- **WHEN** the report is built with Tautulli as the source of plays
- **THEN** every Tautulli request is `get_history`, and every Plex request is to one of the four
  allowed paths

#### Scenario: Tautulli only, no Plex
- **WHEN** Tautulli is set up but Plex isn't
- **THEN** the script stops with `error: NOT_CONFIGURED: ...`, because the library list only comes
  from Plex

### Requirement: Choosing a source of plays
`--source auto` (the default) SHALL use Tautulli's history if Tautulli is configured and fall back to
Plex's watch history otherwise, recording why in `fallback_reason` ("Tautulli is not set up", that its
settings couldn't be read and why, or that it is configured but failed and why). `--source tautulli`
SHALL fail with `TAUTULLI_NOT_CONFIGURED` if it isn't set up and SHALL fail instead of falling back if
Tautulli errors. `--source plex` SHALL use Plex's history only. `source` in the report SHALL be
`tautulli` or `plex`.

#### Scenario: Tautulli is down
- **WHEN** Tautulli is configured but can't be reached and `--source` is `auto`
- **THEN** the report uses Plex's watch history and `fallback_reason` says Tautulli failed and why

#### Scenario: Tautulli asked for but not set up
- **WHEN** run with `--source tautulli` and Tautulli isn't configured
- **THEN** the script stops with `error: TAUTULLI_NOT_CONFIGURED: ...`

### Requirement: Owner-only history
If Plex's watch history is the source and the history request is refused (401 or 403) while `/`
still works, the script SHALL fail with `OWNER_ONLY`, explaining that only the server owner can see
everyone's plays.

#### Scenario: Connected to a shared server without Tautulli
- **WHEN** Plex is the source, `/` succeeds and `/status/sessions/history/all` returns 403
- **THEN** the script stops with `error: OWNER_ONLY: ...`

### Requirement: Which plays count
Only finished plays SHALL count. With Plex as the source, every entry in the server's watch history
SHALL count as finished, since Plex only records plays that were finished or nearly finished. With
Tautulli, only movie and episode history rows whose `watched_status` is 1 SHALL count; rows that are
partly watched or barely started SHALL NOT. Plays by every account SHALL count, not only the owner's.
Plex's own `viewCount`, `lastViewedAt` and `viewOffset` on library items SHALL NOT be used, because
they only describe the token's own account.

A movie SHALL be played when a finished play has its rating key. A show SHALL be played when a
finished play of any of its episodes has the show's rating key as its grandparent.

#### Scenario: Started but not finished
- **WHEN** Tautulli is the source and the only play of a movie in the last year reached 40% with
  `watched_status` 0.5
- **THEN** the movie counts as having no finished play

#### Scenario: A friend finished it
- **WHEN** the owner never played a movie but a friend finished it last month
- **THEN** the movie is not listed

#### Scenario: One episode finished
- **WHEN** someone finished one episode of a show last month and no other episode was played
- **THEN** the show is not listed

### Requirement: Reading history
The script SHALL read the source's whole movie and episode history, newest first, in pages, up to
100,000 plays, and set `history_capped` to true when that limit is reached. `history_since` SHALL be
the date of the oldest play read, or `null` when the history is empty. Live TV SHALL be left out.

#### Scenario: Very large history
- **WHEN** the source has more than 100,000 plays
- **THEN** only the newest 100,000 are read, `history_capped` is true and `history_since` is the date
  of the oldest one read

#### Scenario: Empty history
- **WHEN** the source has no plays at all
- **THEN** `history_since` is `null` and every title old enough to qualify is listed with
  `last_finished` `null`

### Requirement: Which titles are listed
The cutoff SHALL be the same date and time `--months` calendar months before now (moved back to the
last day of the month when that month is shorter). A title SHALL be listed when it was added before
the cutoff and has no finished play after the cutoff. A movie's added date SHALL be its `addedAt`. A
show's added date SHALL be the newest `addedAt` among its episodes, so a show that got new episodes
recently is not listed. Items with no `addedAt` SHALL NOT be listed. Only movie and TV libraries SHALL
be checked; other libraries SHALL be named in `skipped_libraries` with their type.

#### Scenario: Added two years ago, never finished
- **WHEN** a movie was added 2 years ago and has no finished play
- **THEN** it is listed with `last_finished` `null`

#### Scenario: Finished long ago
- **WHEN** a movie was added 3 years ago and last finished 1 year ago, with the default 6 months
- **THEN** it is listed with `last_finished` set to that date

#### Scenario: Added recently
- **WHEN** a movie was added 2 months ago and has never been played, with the default 6 months
- **THEN** it is not listed

#### Scenario: A show with a new episode
- **WHEN** a show was first added 2 years ago, has never been played, and got a new episode last week
- **THEN** it is not listed

#### Scenario: Music library
- **WHEN** the server has a music library
- **THEN** it is not checked and appears in `skipped_libraries` with type `artist`

### Requirement: Size
A title's size SHALL be the total size of every part of every media version that doesn't have a
`deletedAt` value (a file Plex can't find takes no space). A show's size SHALL be the total over all
its episodes. A title whose files are all missing SHALL NOT be listed. Sizes SHALL be in GB.

#### Scenario: Two versions of a movie
- **WHEN** an unwatched movie has a 4K copy of 60 GB and a 1080p copy of 12 GB
- **THEN** its `gb` is 72

#### Scenario: Every file missing
- **WHEN** a movie qualifies but every one of its media versions has a `deletedAt` value
- **THEN** it is not listed

### Requirement: Report contents
The JSON report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version),
`months`, `cutoff` (date), `source`, `fallback_reason`, `history_since`, `history_capped`,
`libraries`, `skipped_libraries` and `totals`.

Each entry in `libraries` SHALL have `name`, `type` (`movie` or `show`), `items` (movies or shows in
the library), `library_gb`, `unwatched` (titles listed), `unwatched_gb`, `unwatched_pct` (share of
`library_gb`, one decimal), `never_finished` and `never_finished_gb` (those with no finished play at
all in the history read) and `titles`. Each title SHALL have `title` (movies as "Title (Year)", shows
as the show title), `added` (date), `gb`, `last_finished` (date, or `null` when no finished play was
found) and, for shows, `episodes`. `titles` SHALL be sorted by `gb`, largest first, then by title, and
hold at most `--limit` entries; the counts SHALL cover every qualifying title before that limit.

`totals` SHALL give `unwatched`, `unwatched_gb`, `library_gb`, `unwatched_pct`, `never_finished` and
`never_finished_gb` over all libraries checked.

The report SHALL NOT contain any person's name: it says whether a title was finished, not by whom.

#### Scenario: Movies library
- **WHEN** "Movies" has 400 movies using 4,000 GB and 50 of them, using 600 GB, qualify, 30 of which
  were never finished
- **THEN** its entry has `items` 400, `unwatched` 50, `unwatched_gb` 600, `unwatched_pct` 15.0,
  `never_finished` 30 and up to `--limit` titles, largest first

#### Scenario: Nothing qualifies
- **WHEN** every title has been finished in the last 6 months or was added recently
- **THEN** each library has `unwatched` 0 and an empty `titles` list, and the script exits 0

### Requirement: Options
The script SHALL accept `--months N` (default 6, limited to 1–120), `--library NAME` (repeatable,
case-insensitive; error if nothing matches, or if only libraries other than movie and TV libraries
match), `--limit N` (titles listed per library, default 25, limited to 0–500), `--source
auto|tautulli|plex` and `--check`.

#### Scenario: A shorter cutoff
- **WHEN** run with `--months 3` and a movie was added 4 months ago and never played
- **THEN** it is listed

#### Scenario: Out-of-range limit
- **WHEN** run with `--limit 9999`
- **THEN** each library lists at most 500 titles

#### Scenario: Asking for a music library
- **WHEN** run with `--library Music` and "Music" is a music library
- **THEN** the script stops with an error saying only movie and TV libraries are checked

### Requirement: Connection check
`--check` SHALL test Plex and, when configured, Tautulli separately, and print the server name and
version. A Tautulli failure SHALL be reported in the result (with `ok: false`) rather than as an
error.

#### Scenario: Tautulli key changed
- **WHEN** `--check` runs and Tautulli rejects the key
- **THEN** the output has `ok: false` and the Tautulli error, and the Plex result is still shown
