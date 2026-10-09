## ADDED Requirements

### Requirement: Sources used
The script `skills/watch-mix/scripts/watch_mix.py` SHALL request only `/`, `/library/sections`,
`/library/sections/{id}/all`, `/library/sections/{id}/genre`, `/accounts`,
`/status/sessions/history/all` and `/:/prefs` from the user's Plex server, all with `GET`, reading
listings in pages of 500. `/accounts` SHALL be requested only with `--user` when Plex is the source of
plays. `/:/prefs` SHALL be read only for the media deletion setting (see "Media deletion setting" in
the conventions spec). With Tautulli it SHALL run only `get_tautulli_info`, `get_history` and
`get_users`, and `get_users` only with `--user`. The shelf SHALL always come from Plex; only the plays
can come from Tautulli. It SHALL NOT contact plex.tv or any other address.

#### Scenario: Building a report with Tautulli
- **WHEN** the report is built with Tautulli as the source of plays and no `--user`
- **THEN** every Tautulli request is `get_history`, and every Plex request is `GET` to one of the
  allowed paths other than `/accounts`

#### Scenario: Tautulli only, no Plex
- **WHEN** Tautulli is set up but Plex isn't
- **THEN** the script stops with `error: NOT_CONFIGURED: ...`, because the shelf only comes from Plex

### Requirement: Choosing a source of plays
`--source auto` (the default) SHALL use Tautulli's history if Tautulli is configured and fall back to
Plex's history otherwise, recording why in `fallback_reason` ("Tautulli is not set up", that its
settings couldn't be read and why, or that it is configured but failed and why). `--source tautulli`
SHALL fail with `TAUTULLI_NOT_CONFIGURED` if it isn't set up and SHALL fail instead of falling back
if Tautulli errors. `--source plex` SHALL use Plex's history only. `source` in the report SHALL be
`tautulli` or `plex`. If Plex's history is the source and the history request is refused (401 or
403) while `/` still works, the script SHALL fail with `OWNER_ONLY`.

#### Scenario: Tautulli is down
- **WHEN** Tautulli is configured but can't be reached and `--source` is `auto`
- **THEN** the report uses Plex's history and `fallback_reason` says Tautulli failed and why

#### Scenario: Connected to a shared server without Tautulli
- **WHEN** Plex is the source, `/` succeeds and `/status/sessions/history/all` returns 403
- **THEN** the script stops with `error: OWNER_ONLY: ...`

### Requirement: The shelf
The shelf SHALL be every movie and show in the included movie and TV libraries, read from
`/library/sections/{id}/all` with `type=1` (movies), `type=2` (shows) and `type=4` (episodes). Other
libraries SHALL be named in `skipped_libraries` with their type. A movie's or episode's size SHALL be
the total of every part of every media version Plex can still find (versions with `deletedAt` left
out, as in `unwatched`); a show's size the total of its episodes' sizes. If a library's
listings or genre requests can't be read, that library SHALL be left out of every share, named in
`unavailable` with `part` and `reason`, and the report SHALL be built from the other libraries.

#### Scenario: A music library
- **WHEN** the server has a music library
- **THEN** it is in `skipped_libraries` and none of its titles or plays are counted

#### Scenario: One library can't be read
- **WHEN** the movie listing for "Movies" answers 500 and "Kids Movies" reads normally
- **THEN** "Movies" is named in `unavailable`, the movie shares are built from "Kids Movies", and the
  script exits 0

### Requirement: Genres
A title's genres SHALL come from Plex's genre filter: for each included library, the genre list from
`/library/sections/{id}/genre`, then, for each genre, `/library/sections/{id}/all` with `type=1`
(movie libraries) or `type=2` (TV libraries) and that genre, reading every page. A title SHALL belong
to every genre whose filtered listing includes it. Genres with the same name in different libraries
of the same kind SHALL be one group, matched ignoring upper and lower case. A title in no genre SHALL
be in a `(no genre)` group. Genres on library listing entries SHALL NOT be used.

#### Scenario: A movie with three genres
- **WHEN** the genre filter lists one movie under Comedy, Drama and Romance, and the library listing
  shows only Comedy and Drama for it
- **THEN** the movie counts toward all three genre groups

#### Scenario: No genre
- **WHEN** a show appears in no genre's filtered listing
- **THEN** it counts in the `(no genre)` group for TV

### Requirement: Decades
A title's decade SHALL come from its `year` (for a show, the show's `year`), or, when that's missing,
the year of `originallyAvailableAt`. The decade SHALL be named like `1980s`. A title with neither
SHALL be in an `unknown` decade.

#### Scenario: A 1987 movie
- **WHEN** a movie's `year` is 1987
- **THEN** it counts toward `1980s`

#### Scenario: No year
- **WHEN** a movie has no `year` and no `originallyAvailableAt`
- **THEN** it counts toward `unknown`

### Requirement: Quality
Quality SHALL be a resolution bucket, using the same rule as `library-report`: `4K`, `2K`, `1080p`,
`720p`, `SD` or `unknown`. For movies, the unit SHALL be the movie, at its best media version Plex can
still find. For TV, the unit SHALL be the episode, at its best media version Plex can still find. A
title with no version Plex can find SHALL be `unknown`. A play SHALL be grouped by the quality
of the matched title's file on the server now. The report SHALL include `quality_note` saying that
plays are grouped by the file on the server now, which may differ from the one played.

#### Scenario: A movie with two versions
- **WHEN** a movie has a 1080p version and a 4K version
- **THEN** it counts once, toward `4K`

#### Scenario: Mixed-quality show
- **WHEN** a show has 10 episodes in 1080p and 2 in 720p
- **THEN** the TV quality groups count 10 episodes toward `1080p` and 2 toward `720p`

### Requirement: Which plays count
Only plays that started within the period SHALL count: from the same date and time `--months`
calendar months before now (clamped to the month's end, as in `unwatched`) up to now. Only movie and
episode plays SHALL count; music and live TV SHALL be left out. With Tautulli, every grouped history
row SHALL count as one play, finished or not. With Plex, every history entry SHALL count as one play
(Plex records only finished or nearly finished plays). Without `--user`, plays by every account
SHALL count. History SHALL be read newest first, in pages, stopping once past the period, up to
100,000 plays; `history_capped` SHALL be true when that limit is reached.

#### Scenario: The period's edge
- **WHEN** `--months` is 12, it's 9 October 2026, and plays started on 8 October 2025 and 10 October
  2025
- **THEN** only the second counts

#### Scenario: An unfinished play with Tautulli
- **WHEN** Tautulli is the source and a horror movie was played to 30% with `watched_status` 0
- **THEN** it counts as one play of a horror movie, with the time actually played

### Requirement: Watch time
With Tautulli, a play's watch time SHALL be the time actually played with pauses left out
(`play_duration`, or `duration` on older Tautulli without it), and `watch_time_method` SHALL be
`"played"`. With Plex, a play's watch time SHALL be the matched title's length (`duration` of the
movie or episode on the shelf), and `watch_time_method` SHALL be `"finished_plays_times_length"`. A
play whose title has no length SHALL count as a play with no watch time. Hours SHALL be rounded to one
decimal place.

#### Scenario: Plex as the source
- **WHEN** Plex is the source and a 2-hour movie was finished 3 times in the period
- **THEN** it adds 3 plays and 6 hours, and `watch_time_method` is `"finished_plays_times_length"`

#### Scenario: A paused play
- **WHEN** Tautulli reports a play of 2 hours 30 minutes from start to stop, 30 minutes of it paused
- **THEN** it adds 2 hours

### Requirement: Matching plays to the shelf
A title's rating key changes when its file is replaced or it's added again, so plays SHALL be matched
in steps, each tried only when the one before finds nothing:
- A movie play SHALL match the shelf movie with its rating key; else, with Tautulli, the shelf movie
  with the same `guid`; else the one shelf movie with the same title (ignoring case, spaces and
  punctuation) and year (Tautulli's `year`, or the year of Plex's `originallyAvailableAt`); else the
  one shelf movie with that title.
- An episode play SHALL match its show for genre and decade: the shelf show with its show's rating
  key (Tautulli's `grandparent_rating_key`, or the last part of Plex's `grandparentKey`); else the
  show of the shelf episode with the play's rating key; else the one shelf show with the same title.
  It SHALL match its episode for quality: the shelf episode with its rating key, if that episode
  belongs to the matched show; else the matched show's episode with the same season and episode
  number.

When several shelf titles share a title (and year), that step SHALL match nothing. A play that matches
no movie or show on the included shelf SHALL be left out of every share and counted in
`unmatched_plays` (`plays` and `hours`, per kind). An episode play whose show matches but whose
episode doesn't SHALL count for genre and decade and toward `unknown` quality. Titles read from the
history SHALL be used only for matching and SHALL NOT appear in the report.

#### Scenario: A removed movie
- **WHEN** a movie was played 4 times in the period and has since been removed from the server
- **THEN** the 4 plays are in `unmatched_plays.movies` and in no share

#### Scenario: A movie replaced since it was played
- **WHEN** Tautulli has a play of a movie under rating key 100 with guid `plex://movie/abc`, and the
  movie is now on the shelf under rating key 900 with the same guid
- **THEN** the play counts toward that movie's genres, decade and quality

#### Scenario: Matching by title and year with Plex history
- **WHEN** Plex is the source, a play's rating key isn't on the shelf, and its title is "Night of the
  Test" with `originallyAvailableAt` in 1987, and one shelf movie is "Night Of The Test" (1987)
- **THEN** the play matches that movie

#### Scenario: Two movies with the same title
- **WHEN** a play's rating key and guid match nothing and two shelf movies are called "Test Story",
  one from 1995 and one from 2019, and the play has no year
- **THEN** the play matches nothing and is counted in `unmatched_plays`

#### Scenario: Plex history for an episode
- **WHEN** Plex is the source and an episode entry has `grandparentKey` `/library/metadata/500`
- **THEN** the play counts toward the genres and decade of the show with rating key `500`

#### Scenario: An episode replaced since it was played
- **WHEN** an episode play of S02E03 has a rating key that's no longer on the shelf, and its show
  has an S02E03 in 720p
- **THEN** it counts for the show's genres and decade and toward `720p`

#### Scenario: An episode removed since it was played
- **WHEN** an episode play's show is on the shelf but neither its rating key nor its season and
  episode number are
- **THEN** it counts for the show's genres and decade and toward `unknown` quality

### Requirement: Shares
For each kind (`movies`, `tv`) and each grouping (`genres`, `decades`, `quality`), the report SHALL
give one row per group with `name`, `titles`, `titles_percent`, `storage_bytes`, `storage_gb`,
`storage_percent`, `plays`, `plays_percent`, `hours`, `hours_percent` and `gap_points`. The wholes
SHALL be the kind's shelf (titles, storage) and its matched plays (plays, hours); for TV quality the
titles are episodes. Percentages SHALL be rounded to one decimal place, and `null` when the whole is
zero. `gap_points` SHALL be `hours_percent` minus `titles_percent`, rounded to one decimal place, or
`null` when either is `null`. A group SHALL have a row when it has titles on the shelf or matched
plays. Genre rows SHALL be sorted by `titles` most first, then name; decade rows oldest first with
`unknown` last; quality rows best first (`4K`, `2K`, `1080p`, `720p`, `SD`, any other value, then
`unknown`). The report
SHALL include `genre_note` saying that a title can be in several genres, so genre shares can add up
to more than 100%.

#### Scenario: The horror example
- **WHEN** 90 of 500 movies are horror and horror movies make up 30 of 1,000 hours watched
- **THEN** the horror row has `titles_percent` 18.0, `hours_percent` 3.0 and `gap_points` -15.0

#### Scenario: Nothing watched
- **WHEN** no TV plays matched in the period
- **THEN** every TV row has `plays` 0, `plays_percent` and `hours_percent` `null`, and `gap_points`
  `null`

### Requirement: Biggest differences
For each kind, `watched_more` SHALL list up to `--top` rows with the highest positive `gap_points`
and `watched_less` up to `--top` rows with the lowest negative `gap_points`, taken from all three
groupings together. Each entry SHALL carry the row's fields plus `grouping` (`genre`, `decade` or
`quality`). Rows with fewer than 5 titles, the `(no genre)` row, `unknown` decades and `unknown`
quality SHALL be left out of these lists (they stay in the full groupings). Ties SHALL be broken by
`titles` most first, then name.

#### Scenario: A tiny genre
- **WHEN** a Western genre has 2 movies and 20% of hours watched
- **THEN** it isn't in `watched_more`, and it is still in the movie genre rows

#### Scenario: Top limit
- **WHEN** `--top` is 3 and 8 movie groups have positive gaps
- **THEN** `watched_more` for movies holds the 3 largest

### Requirement: Few plays
For each kind, `few_plays` SHALL be true when fewer than 30 plays matched the shelf in the period,
and false otherwise. The shares SHALL still be given.

#### Scenario: A quiet TV year
- **WHEN** 12 TV plays matched in the period
- **THEN** `tv.few_plays` is true and the TV rows are still in the report

### Requirement: One person
With `--user NAME`, only that person's plays SHALL count, and the shelf SHALL be the same as without
it. The person SHALL be matched as in `watch-activity` ("Choosing one person"): with Tautulli among
`get_users`' friendly names and usernames, with Plex among `/accounts` names, ignoring case, an exact
match winning, otherwise a single "contains" match; with the same `USER_NOT_FOUND` and
`USER_AMBIGUOUS` errors, which SHALL NOT cause `--source auto` to fall back. With Tautulli, the
person's `user_id` SHALL be passed to every `get_history` request; with Plex, history entries SHALL be
kept only when their `accountID` matches. `scope` SHALL be `user` and `user` the person's display
name; without `--user`, `scope` SHALL be `server` and `user` `null`.

#### Scenario: One person with Plex
- **WHEN** Plex is the source, run with `--user alex-test`, and the history holds plays by
  `alex-test` and another account
- **THEN** only `alex-test`'s plays are counted and `user` is `alex-test`

#### Scenario: Nobody matches
- **WHEN** run with `--user nobody`, Tautulli is the source with `--source auto`, and no one matches
- **THEN** the script stops with `error: USER_NOT_FOUND: ...` and does not fall back to Plex

### Requirement: A whole-server report names no one
When `scope` is `server`, the report SHALL NOT contain any person's name, user name, user id or
account id, any device or player name, any title, or the time of any single play. The report SHALL
contain only groups, counts, shares and totals.

#### Scenario: Names in the history
- **WHEN** the history holds plays by `alex-test` and `sam-test` on a device called "Alex's iPhone"
  of a movie called "Night of the Test"
- **THEN** none of `alex-test`, `sam-test`, "Alex's iPhone" or "Night of the Test" appears in the
  JSON

### Requirement: Options
The script SHALL accept `--months N` (default 12, limited to 1–120), `--user NAME`, `--library NAME`
(repeatable, case-insensitive; error if nothing matches, or if only libraries other than movie and TV
libraries match), `--top N` (default 5, limited to 1–20), `--source auto|tautulli|plex` and `--check`.
`--library` SHALL narrow both the shelf and which plays can match it.

#### Scenario: Only one library
- **WHEN** run with `--library "Kids Movies"` and a play is of a movie in "Movies"
- **THEN** that play is in `unmatched_plays` and only "Kids Movies" is on the shelf

#### Scenario: Asking for a music library
- **WHEN** run with `--library Music` and "Music" is a music library
- **THEN** the script stops with an error saying only movie and TV libraries are compared

### Requirement: Report contents
The JSON report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version),
`media_deletion_allowed`, `source`, `fallback_reason`, `scope`, `user`, `months`, `period_start`,
`history_capped`, `watch_time_method`, `genre_note`, `quality_note`, `libraries` (the included
libraries' names and kinds), `skipped_libraries`, `unavailable`, `unmatched_plays`, and `movies` and
`tv`, each with `titles`, `storage_bytes`, `storage_gb`, `plays`, `hours`, `few_plays`, `genres`,
`decades`, `quality`, `watched_more` and `watched_less`, and for `tv` also `episodes`. A kind with no
included library that could be read SHALL be `null`, and its plays SHALL be counted in
`unmatched_plays`. Every genre name from the server SHALL be cleaned as described in the security spec's
"Server text is treated as data".

#### Scenario: Movies only
- **WHEN** the only included library is a movie library
- **THEN** `tv` is `null` and `movies` is reported

#### Scenario: A genre name with control characters
- **WHEN** a genre's name contains control characters or text made to look like instructions
- **THEN** the control characters are removed and the text appears only as a value in the JSON
