## ADDED Requirements

### Requirement: Episode numbers for listed shows
Each show listed under a finding in a TV library SHALL say which of its episodes have that finding,
taken from the season (`parentIndex`) and episode (`index`) numbers in the episode listing the script
already reads. No extra request SHALL be made for them.

- `seasons`: one entry per season with at least one flagged, numbered episode, in season order (season
  0, Plex's specials, first). Each entry SHALL have `season`, `episodes` (the flagged episode numbers as
  `[first, last]` ranges in order, a single episode being `[n, n]`) and `some_versions` (the flagged
  episode numbers in that season where the episode has more than one checked file and not all of them
  have the finding, in order).
- `ranges_more`: how many flagged, numbered episodes were left out of `seasons` because of the cap
  below.
- `unnumbered`: flagged episodes with no season or no episode number, in the order of the episode
  listing, each with `title` (cleaned), `aired` (the `originallyAvailableAt` date as `YYYY-MM-DD`, or
  `null` when it's missing or not in that form) and `some_versions` (`true` or `false`, as above).
- `unnumbered_more`: how many flagged episodes with no number were left out of `unnumbered` because
  of the cap below.

At most 30 ranges SHALL be given per show per finding, counted across its seasons in order; once 30
are given, the rest of that show's numbered episodes for that finding SHALL be counted in
`ranges_more` instead, and their numbers SHALL NOT appear in `some_versions`. At most 10 unnumbered
episodes SHALL be given per show per finding, with the rest counted in `unnumbered_more`. An episode
listed twice with the same season and episode number SHALL appear once. File paths SHALL NOT appear.

#### Scenario: Flagged episodes in two seasons
- **WHEN** episodes 1 to 4 and 6 of season 1 and episode 2 of season 3 of a show have only Spanish
  audio and no English subtitles, and the user's language is `en`
- **THEN** the show's entry under `foreign_no_subtitles` has `seasons`
  `[{"season": 1, "episodes": [[1, 4], [6, 6]], "some_versions": []}, {"season": 3, "episodes": [[2, 2]], "some_versions": []}]`,
  `ranges_more` 0, `unnumbered` `[]` and `unnumbered_more` 0

#### Scenario: One version of an episode is fine
- **WHEN** season 2 episode 5 has two files, one with English subtitles and one without, and the
  user's language is `en`
- **THEN** the show's entry under `no_subtitles` has season 2 with `[5, 5]` in `episodes` and 5 in
  `some_versions`

#### Scenario: An episode with no number
- **WHEN** a flagged episode has no `index`, the title "Live Special" and `originallyAvailableAt`
  `2021-12-31`
- **THEN** it appears in the show's `unnumbered` as `{"title": "Live Special", "aired": "2021-12-31",
  "some_versions": false}` and not in `seasons`

#### Scenario: A show with many separate flagged episodes
- **WHEN** every second episode from 1 to 99 of season 1 is flagged (50 episodes, 50 separate ranges)
- **THEN** the show's `seasons` holds 30 ranges (episodes 1, 3, ... 59) and `ranges_more` is 20

#### Scenario: Every episode flagged
- **WHEN** all 300 episodes of a 10-season show, numbered 1 to 30 in each season, have
  `unknown_language`
- **THEN** its entry has 10 seasons, each with `episodes` `[[1, 30]]`, and `ranges_more` 0

#### Scenario: Specials
- **WHEN** season 0 episode 3 and season 1 episode 1 are flagged
- **THEN** `seasons` lists season 0 first, then season 1

## MODIFIED Requirements

### Requirement: Report contents
The JSON report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version),
`limits` (a fixed sentence saying the report goes by the language labels on each track, which can be
wrong or missing, that forced tracks aren't counted as full subtitles, and that a film mostly in the
user's language can still have short scenes in another language that this can't see), `libraries`,
`skipped_libraries`, `language_names`, `totals` and `media_deletion_allowed`.

Each entry in `libraries` SHALL have `name`, `type`, `language` (and `language_problem` when it
applies), `titles`, `files`, `unavailable`, `details_missing`, one count of files per finding
(`foreign_no_subtitles`, `no_subtitles`, `unknown_language`), `forced_only`, `audio_languages`,
`subtitle_languages`, `listed` and `more`. The counts SHALL cover every file checked.

`listed` and `more` SHALL each have one key per finding. In a movie library each list SHALL hold
movies with at least one file that has the finding, each with `title`, `year` (or `null`) and `files`:
the files with the finding, each with `resolution`, `main_audio_language`, `audio_languages` (every
audio track's language, `unknown` for none), `subtitle_languages` (full subtitle tracks),
`forced_subtitle_languages`, `unknown_audio_tracks` and `unknown_subtitle_tracks`. In a TV library each
list SHALL hold shows with at least one episode that has the finding, each with `title`, `year` (or
`null`), `episodes`, `episodes_flagged`, `audio_languages` (the main audio languages of the flagged
episodes, with counts) and the episode numbers described in "Episode numbers for listed shows"
(`seasons`, `ranges_more`, `unnumbered`, `unnumbered_more`). File paths SHALL NOT appear in the report.

Movies SHALL be sorted by title, and shows by `episodes_flagged` (most first) and then by title. Each
list SHALL hold at most `--limit` entries, and `more` SHALL say how many were left out of each.

`totals` SHALL give `titles`, `files`, `unavailable`, `details_missing`, one count per finding and
`forced_only` over all libraries checked; a library whose language findings are `null` SHALL count as
0 for them.

#### Scenario: A clean library
- **WHEN** no file in a library has any finding
- **THEN** each of its lists is empty, each `more` is 0, `limits` is still present and the script
  exits 0

#### Scenario: A show with some foreign episodes
- **WHEN** a show has 20 episodes and 3 of them (season 1 episodes 2, 3 and 7) have only Spanish
  audio and no English subtitles
- **THEN** its entry under `foreign_no_subtitles` has `episodes` 20, `episodes_flagged` 3,
  `audio_languages` `{"es": 3}` and `seasons`
  `[{"season": 1, "episodes": [[2, 3], [7, 7]], "some_versions": []}]`

#### Scenario: Two versions of a movie
- **WHEN** a movie has one file with English subtitles and one without, and the user's language is `en`
- **THEN** it is listed under `no_subtitles` with only the file without subtitles
