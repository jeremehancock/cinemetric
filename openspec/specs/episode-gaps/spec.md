# episode-gaps Specification

## Purpose

A read-only list of gaps in the TV episodes on a Plex server: episode numbers missing between the ones
there, seasons that start late, seasons missing between others, and episodes whose files Plex can't
find. Uses only what's on the server, so episodes after the last one there can't be seen. Specials,
multi-episode files, numbering that carries on across seasons and date-numbered seasons aren't
reported as gaps. Script: `skills/episode-gaps/scripts/episode_gaps.py`. How Claude presents it is in
the skill's `SKILL.md`.

## Requirements
### Requirement: Sources used
The script `skills/episode-gaps/scripts/episode_gaps.py` SHALL request only `/`, `/library/sections`
and `/library/sections/{id}/all` from the user's Plex server, reading library items in pages of 500.
It SHALL NOT contact Tautulli, plex.tv, Plex's online metadata service or any other address. It
SHALL NOT use any source of how many episodes a season or show is meant to have.

#### Scenario: Building a report
- **WHEN** the script builds a report
- **THEN** every request goes to the configured Plex server, to one of the three allowed paths, with
  `GET`

#### Scenario: Tautulli is set up
- **WHEN** Tautulli is configured
- **THEN** the script still makes no Tautulli request

### Requirement: Libraries and episodes checked
Only TV libraries SHALL be checked; other libraries SHALL be named in `skipped_libraries` with their
type. Episodes SHALL be read with the episode listing (`type=4`) and grouped into shows by
`grandparentRatingKey`; each show's title and year SHALL come from the show listing (`type=2`).
`--library NAME` (repeatable, case-insensitive) SHALL limit the libraries checked, and SHALL stop the
script with an error if nothing matches, or if only libraries other than TV libraries match. `--show
TEXT` SHALL keep only shows whose title contains the text, ignoring case.

#### Scenario: Movie library
- **WHEN** the server has a movie library
- **THEN** it is not checked and appears in `skipped_libraries` with type `movie`

#### Scenario: Asking for a movie library
- **WHEN** run with `--library Movies` and "Movies" is a movie library
- **THEN** the script stops with an error saying only TV libraries are checked

#### Scenario: Two shows with the same title
- **WHEN** a library has two shows called "Doctor Who", from 1963 and 2005
- **THEN** their episodes are checked separately and each is identified by its year

#### Scenario: No show matches
- **WHEN** run with `--show "zzz"` and no show title contains it
- **THEN** each library reports 0 shows and the script exits 0

### Requirement: Which episodes are there
An episode number SHALL count as there for a season when at least one episode with that season and
number has a media version without a `deletedAt` value. Several episodes with the same season and
number SHALL count once. An episode whose every media version has a `deletedAt` value SHALL count as
unavailable, not there. When a file name (the last part of a part's file path) holds a range of
episode numbers after a season number in the usual forms (`S01E01-E02`, `S01E01-02`, `S01E01E02`,
`S01E01-E02-E03`), and the range starts at the episode's own number, every number in that range
SHALL count as there for that episode's season. A number followed by `p` or `i` (as in `1080p`)
SHALL NOT be read as part of a range. File paths SHALL NOT appear in the report.

Episodes with no season number or no episode number SHALL be counted as `unnumbered` and otherwise
ignored. Season 0 (specials) SHALL NOT be checked for gaps and SHALL NOT count toward missing seasons.

#### Scenario: A file that holds two episodes
- **WHEN** season 1 lists E01 and E03, and the E01 file is named `Show - S01E01-E02.mkv`
- **THEN** E02 counts as there and season 1 has no missing episodes

#### Scenario: A resolution after the episode number
- **WHEN** season 1 lists E01 and E03, and the E01 file is named `Show - S01E01-1080p.mkv`
- **THEN** E02 is missing

#### Scenario: Two copies of an episode
- **WHEN** S01E04 has a 1080p and a 4K copy, both available
- **THEN** E04 counts once as there

#### Scenario: Plex can't find the file
- **WHEN** S01E05's only media version has a `deletedAt` value and E04 and E06 are there
- **THEN** E05 is reported as unavailable, not as missing

#### Scenario: Specials
- **WHEN** season 0 has specials numbered 1, 4 and 9
- **THEN** no gaps are reported for season 0

### Requirement: Finding gaps
For each season numbered 1 or higher, every number from 1 up to the highest number there or
unavailable that is neither there nor unavailable SHALL be missing, with one exception: when a
season's lowest number (there or unavailable) is exactly one more than the highest number in the
nearest lower-numbered season the show has, the season continues the show's numbering, numbers below
its lowest SHALL NOT be missing, and the season SHALL be marked `continues_numbering`.

Season numbers between the lowest and highest season the show has (both from 1 to 999) with no
episode there or unavailable SHALL be missing seasons. When the show's lowest season is above 1,
`first_season` SHALL record it, and the seasons before it SHALL NOT be missing seasons: keeping only
the later seasons of a long-running show is common and usually deliberate.

A season numbered above 999, or with any episode numbered above 999, SHALL NOT be checked for gaps
and SHALL be counted in `seasons_not_checked`.

#### Scenario: A gap in the middle
- **WHEN** season 2 has E01, E02 and E04
- **THEN** season 2's missing episodes are E03

#### Scenario: A season that starts late
- **WHEN** season 1 has E05 to E10 and the show has no season before it
- **THEN** season 1's missing episodes are E01 to E04

#### Scenario: Numbering carries on across seasons
- **WHEN** season 1 has E01 to E12 and season 2 has E13 to E24
- **THEN** season 2 has no missing episodes and is marked `continues_numbering`

#### Scenario: A missing season
- **WHEN** a show has seasons 1, 2 and 4
- **THEN** its missing seasons are 3

#### Scenario: Only the later seasons
- **WHEN** a show has only seasons 35 to 40, with no gaps inside them
- **THEN** it has no missing seasons, its `first_season` is 35, and it doesn't count as a show with
  gaps

#### Scenario: Missing episodes after the last one
- **WHEN** season 1 has E01 to E08 and the show really has 10 episodes
- **THEN** season 1 has no missing episodes, because the script can't know about E09 and E10

#### Scenario: A date-numbered show
- **WHEN** a show has season 2023 with episodes numbered 20230102 and 20230109
- **THEN** that season is not checked, is counted in `seasons_not_checked`, and no missing seasons are
  reported because of it

### Requirement: Report contents
The JSON report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version),
`show_filter` (the `--show` text or `null`), `limits` (a fixed sentence saying that episodes after
the last one on the server and seasons after the last season can't be seen), `libraries`,
`skipped_libraries` and `totals`.

Each entry in `libraries` SHALL have `name`, `shows` (shows checked), `episodes` (episodes checked),
`shows_with_gaps`, `missing_episodes`, `unavailable_episodes`, `missing_seasons`,
`shows_starting_later` (shows whose `first_season` is above 1), `seasons_not_checked`, `unnumbered`,
`listed` and `more_shows`. A show SHALL have gaps when it has at
least one missing episode, unavailable episode or missing season. `listed` SHALL hold the shows with
gaps, sorted by missing plus unavailable episodes (most first), then missing seasons (most first),
then title, and at most `--limit` of them; `more_shows` SHALL be how many shows with gaps were left
out. The library counts SHALL cover every show checked, before that limit.

Each listed show SHALL have `title`, `year` (or `null`), `first_season`, `missing_seasons` (a list
of season numbers),
`missing_episodes` and `unavailable_episodes` (counts), `unnumbered` and `seasons`. `seasons` SHALL
hold only seasons with something missing, unavailable or marked `continues_numbering`, each with
`season`, `episodes` (count there), `highest` (highest number there or unavailable), `missing` (a list
of `[first, last]` number ranges), `unavailable` (a list of numbers) and `continues_numbering`.

`totals` SHALL give `shows`, `episodes`, `shows_with_gaps`, `missing_episodes`,
`unavailable_episodes`, `missing_seasons` and `shows_starting_later` over all libraries checked.

#### Scenario: Several gaps in one season
- **WHEN** season 3 has E01, E02, E04, E08 and E09
- **THEN** its `missing` is `[[3, 3], [5, 7]]` and the show's `missing_episodes` counts 4 for it

#### Scenario: Nothing missing
- **WHEN** no show has a missing episode, unavailable episode or missing season
- **THEN** each library has `shows_with_gaps` 0 and an empty `listed`, `limits` is still present, and
  the script exits 0

#### Scenario: More shows with gaps than the limit
- **WHEN** 40 shows have gaps and `--limit` is 25
- **THEN** `listed` holds the 25 with the most missing and unavailable episodes, `more_shows` is 15,
  and `shows_with_gaps` is 40

### Requirement: Options
The script SHALL accept `--library NAME` (repeatable), `--show TEXT`, `--limit N` (shows listed per
library, default 25, limited to 0–500) and `--check`.

#### Scenario: Out-of-range limit
- **WHEN** run with `--limit 9999`
- **THEN** each library lists at most 500 shows

#### Scenario: Counts only
- **WHEN** run with `--limit 0`
- **THEN** every library's `listed` is empty and its counts are still filled in

