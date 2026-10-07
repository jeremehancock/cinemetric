## ADDED Requirements

### Requirement: Sources used
The script `skills/show-progress/scripts/show_progress.py` SHALL request only `/`,
`/library/sections`, `/library/sections/{id}/all`, `/status/sessions/history/all`, `/accounts` and
`/:/prefs` from the user's Plex server, all with `GET`. `/accounts` SHALL be requested only to put
names to Plex history entries, and only each account's id and name SHALL be read from it. From
`/:/prefs` the script SHALL read only `allowMediaDeletion` (see "Media deletion setting" in the
conventions spec), requesting it at most once per run.

When Tautulli is used, the script SHALL run only the Tautulli commands `get_tautulli_info`,
`get_history` and `get_users`, and `get_users` only to find the person named with `--user`. It SHALL
NOT contact plex.tv or any other address.

#### Scenario: A report with Tautulli set up
- **WHEN** the script builds a report with Tautulli as the source
- **THEN** every request goes to the configured Plex server (one of the six allowed paths, with
  `GET`) or to the configured Tautulli address (one of the three allowed commands)

#### Scenario: A report from Plex alone
- **WHEN** Tautulli isn't set up
- **THEN** every request goes to the configured Plex server

### Requirement: Choosing a source
Plays SHALL come from Tautulli or Plex following the `watch-activity` spec's "Choosing a source"
requirement, with the same `--source` values (`auto`, `tautulli`, `plex`) and `fallback_reason`. The
report SHALL give `source` as `tautulli` or `plex`. When the source is Plex, the report SHALL include
`plex_history_note` saying Plex's history only records finished episodes.

#### Scenario: Tautulli is down
- **WHEN** Tautulli is configured but can't be reached and `--source` is `auto`
- **THEN** the report comes from Plex, `fallback_reason` says Tautulli failed and why, and
  `plex_history_note` is present

### Requirement: Owner-only history
When Plex is the source and `/status/sessions/history/all` answers 401 or 403, the script SHALL fail
with `OWNER_ONLY` and a message saying Plex only shares watch history with the server owner, and
suggesting Tautulli.

#### Scenario: Not the server owner
- **WHEN** Plex is the source and the history request answers 403
- **THEN** the script stops with `error: OWNER_ONLY: ...` and prints no report

### Requirement: Episodes on the server
Only TV libraries SHALL be read; other libraries SHALL be named in `skipped_libraries` with their
type. `--library NAME` (repeatable, case-insensitive) SHALL limit the report to those libraries, and
SHALL stop the script with an error when it matches no TV library. Each library's episodes SHALL be
read from `/library/sections/{id}/all` with `type=4` in pages, and its shows with `type=2`.

An episode SHALL count as on the server when at least one of its media versions has no `deletedAt`
value. Episodes in season 0 (specials) and episodes with no season or episode number SHALL be left out
of every position, count and status. The same season and episode number appearing more than once in
a show (for example two copies) SHALL count as one episode, added at the earliest `addedAt`.

#### Scenario: An episode Plex can't find
- **WHEN** a show's S02E03 has only one file and it has a `deletedAt` value
- **THEN** S02E03 isn't counted as left to watch for anyone

#### Scenario: Specials
- **WHEN** someone finished S00E01 and nothing else of a show
- **THEN** that show doesn't appear for them

#### Scenario: A music library
- **WHEN** the server has a music library
- **THEN** it isn't read and appears in `skipped_libraries` with type `artist`

### Requirement: Reading history
The script SHALL read the source's history, newest first, in pages, up to 100,000 rows, and set
`history_capped` to true when that limit is reached. With Tautulli only episode rows SHALL be
requested; Plex's history can't be filtered by type, so with Plex rows of every type SHALL count
towards the limit and only episode entries SHALL be used. `history_since` SHALL be the date of the
oldest row in the source's history (with Tautulli, the oldest episode row that isn't Live TV), or
`null` when there are none. When the rows read were narrowed to one person or show and the limit
wasn't reached, the script SHALL ask the source for its oldest row separately (Tautulli
`get_history` with `order_dir` `asc`; Plex's history sorted by `viewedAt:asc`), so the date says how
far back the history goes, not when that person or show was first played. When the limit is
reached, it SHALL be the date of the oldest row read. Live TV SHALL be left out. With Tautulli,
`get_history` SHALL be called with `media_type` `episode` and `grouping` 1.

A history row SHALL be matched to an episode by its show's rating key (Tautulli's
`grandparent_rating_key`; Plex's `grandparentRatingKey`, or the number at the end of `grandparentKey`)
and its season and episode numbers, not by the episode's own rating key. A row with no show key, or
whose show isn't on the server, SHALL be ignored. A row whose show is on the server but whose season
and episode don't match any episode there SHALL still count towards the person's last play of the
show, and SHALL be counted in that show's `unmatched_plays`.

A row SHALL count as finished with Tautulli when `watched_status` is 1 or more, and always with Plex.
From Tautulli rows only the fields needed for the report SHALL be read; IP addresses, device and
player names, and every other field SHALL NOT appear in the output.

#### Scenario: A file was upgraded
- **WHEN** Sam finished S01E04 before its file was replaced, and the episode now has a different
  rating key
- **THEN** Sam's finished S01E04 still counts

#### Scenario: Started but not finished
- **WHEN** Tautulli is the source and Sam's only play of S01E05 reached 40% with `watched_status` 0.5
- **THEN** S01E05 isn't one of Sam's finished episodes, but the play counts as Sam's last play of the
  show

#### Scenario: Very large history
- **WHEN** the source has more than 100,000 episode plays
- **THEN** only the newest 100,000 are read and `history_capped` is true

#### Scenario: History since with one show
- **WHEN** the report is run with `--show` for a show first played a month ago, and the history goes
  back two years
- **THEN** `history_since` is the date two years ago

### Requirement: A person's place in a show
A person SHALL appear for a show when they finished at least one regular episode of it. For each
person and show the report SHALL give:
- `furthest`: the highest season and episode number among the person's finished episodes, compared by
  season first, then episode.
- `episodes_finished`: the number of distinct episodes on the server the person finished.
- `episodes_left`: episodes on the server whose season and episode come after `furthest`.
- `next_episode`: the first of those (season, episode and title), or `null` when there are none.
- `new_since_last_play`: how many of the episodes left were added after `last_played_at`.
- `last_played_at`: the person's most recent play of the show, finished or not.
- `status`, chosen in this order: `caught_up` when `episodes_left` is 0; `new_episodes` when every
  episode left was added after `last_played_at`; `stopped` when `last_played_at` is more than
  `--stopped-months` calendar months ago; otherwise `in_progress`.

Episodes before `furthest` that the person never finished SHALL NOT count as left.

#### Scenario: A rewatch of season 1
- **WHEN** Sam finished every episode up to S02E05, then rewatched S01E01 last week, and the server
  has S02E06 to S02E10
- **THEN** Sam's `furthest` is S02E05, `episodes_left` is 5, `next_episode` is S02E06 and `status` is
  `in_progress`

#### Scenario: Started partway in
- **WHEN** Alex finished S03E01 to S03E04 of a show with three 10-episode seasons, and nothing else
- **THEN** Alex's `furthest` is S03E04 and `episodes_left` is 6

#### Scenario: Caught up
- **WHEN** Jo finished the last episode on the server
- **THEN** Jo's `status` is `caught_up`, `episodes_left` is 0 and `next_episode` is `null`

#### Scenario: New episodes arrived
- **WHEN** Jo finished everything on the server in January, and three episodes were added in May
- **THEN** Jo's `status` is `new_episodes` and `new_since_last_play` is 3, even when January is more
  than `--stopped-months` months ago

#### Scenario: Gave up partway
- **WHEN** Alex finished S01E01 and S01E02 of a 10-episode season, all on the server for a year, and
  last played the show 5 months ago, with the default 3 months
- **THEN** Alex's `status` is `stopped` and `episodes_left` is 8

### Requirement: Recently added episodes
`recently_added` SHALL list shows with at least one episode added in the last `--new-days` days (30
by default), newest first. Each entry SHALL give the show, `new_episodes` (the count added in that
window), `added_since` (the earliest of those dates) and `people`: each person who finished at least one
regular episode of the show, with `finished_new` (how many of the new episodes they have finished)
and `was_following` (true when they finished an episode of the show before the window began).
`nobody_started` SHALL be true when nobody has finished any of the new episodes. `recently_added` SHALL hold at most `--top` entries, and `recently_added_count` SHALL be the
total before that limit.

#### Scenario: A new season nobody has started
- **WHEN** season 4 of a show was added 3 weeks ago, Sam and Alex finished earlier seasons, and
  neither has finished a season 4 episode
- **THEN** the show is in `recently_added` with `nobody_started` true and both people with
  `finished_new` 0 and `was_following` true

#### Scenario: A show new to the server
- **WHEN** a show's first 4 episodes were added 3 weeks ago and Jo has since finished 3 of them
- **THEN** the show is in `recently_added` with `nobody_started` false, and Jo has `finished_new` 3
  and `was_following` false

### Requirement: Narrowing to one person or show
`--user NAME` SHALL find the person following the `watch-activity` spec's "Choosing one person"
requirement (exact match first, otherwise exactly one name containing NAME, ignoring case), with the
same `USER_NOT_FOUND` and `USER_AMBIGUOUS` errors, and every part of the report SHALL cover only that
person. With Tautulli, the person's `user_id` SHALL be passed to `get_history`.

`--show NAME` SHALL keep only shows whose title contains NAME, ignoring case, spaces and punctuation;
an exact match SHALL win over "contains" matches. When no show matches, the script SHALL fail with
`SHOW_NOT_FOUND`. When several match and none exactly, it SHALL fail with `SHOW_AMBIGUOUS` and list
them (at most 20, each with title, year and library). With one show chosen, Tautulli's `get_history`
SHALL be passed its `grandparent_rating_key` and Plex's history SHALL be requested with
`metadataItemID` set to its rating key. With `--show`, the show SHALL be reported even when nobody has
finished an episode, with `people` empty.

#### Scenario: One person
- **WHEN** run with `--user sam` and the history has plays by Samantha and Alex
- **THEN** every show and count in the report covers only Samantha

#### Scenario: Two shows match
- **WHEN** run with `--show office` and the server has "The Office (US)" and "The Office (UK)"
- **THEN** the script stops with `error: SHOW_AMBIGUOUS: ...` naming both

#### Scenario: A show nobody watches
- **WHEN** run with `--show "slow horses"` and nobody has finished an episode
- **THEN** the report has that show with `people` empty

### Requirement: Report contents
The report SHALL give `source`, `fallback_reason`, `history_since`, `history_capped`,
`stopped_after_months`, `new_days`, `user` (the chosen person's name, or `null`), `show` (the chosen
show's title, or `null`), `skipped_libraries`, `media_deletion_allowed`, `status_counts` (how many
person-show pairs have each status), `show_count`, `shows`, `recently_added_count` and
`recently_added`.

Each `shows` entry SHALL give `title`, `year`, `library`, `episodes_on_server`, `last_added_at`,
`last_played_at` (by anyone), `unmatched_plays` and `people` as described in "A person's place in a
show", sorted by `last_played_at`, newest first. `shows` SHALL be sorted by `last_played_at`, newest
first, and hold at most `--top` entries (25 by default); `show_count` and `status_counts` SHALL count
everything before that limit.

For each person only the name and the fields above SHALL be printed: no email, account id, user id,
IP address or device. Every text value from the server SHALL be cleaned as described in "Server text
is treated as data" in the security spec.

#### Scenario: More shows than the limit
- **WHEN** 40 shows have someone following them and `--top` is 25
- **THEN** `shows` holds the 25 most recently played and `show_count` is 40

#### Scenario: Nothing watched
- **WHEN** nobody has finished any episode
- **THEN** `shows` is empty, `show_count` is 0 and the script exits 0

### Requirement: Options
The script SHALL accept `--show NAME`, `--user NAME`, `--library NAME` (repeatable),
`--stopped-months N` (default 3), `--new-days N` (default 30), `--top N` (default 25),
`--source auto|tautulli|plex` (default `auto`) and `--check`. `--stopped-months`, `--new-days` and
`--top` SHALL be positive whole numbers.

#### Scenario: A bad number
- **WHEN** the script runs with `--stopped-months 0`
- **THEN** it stops with an error saying `--stopped-months` must be a positive whole number
