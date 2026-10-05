## ADDED Requirements

### Requirement: Sources used
The script `skills/what-to-watch/scripts/what_to_watch.py` SHALL request only `/`,
`/library/sections`, `/library/sections/{id}/all`, `/library/sections/{id}/genre` and
`/library/onDeck` from the user's Plex server, reading library items in pages of 500. It SHALL NOT contact Tautulli, plex.tv or any other address.

#### Scenario: Building a shortlist
- **WHEN** the script builds a shortlist
- **THEN** every request goes to the configured Plex server, to one of the five allowed paths, with
  `GET`

#### Scenario: Tautulli is set up
- **WHEN** Tautulli is configured
- **THEN** the script still makes no Tautulli request

### Requirement: Libraries checked
Only movie and TV libraries SHALL be checked; other libraries SHALL be named in `skipped_libraries`
with their type. Movies SHALL be read with the movie listing (`type=1`) and shows with the show
listing (`type=2`). `--library NAME` (repeatable, case-insensitive) SHALL limit the libraries checked,
and SHALL stop the script with an error if nothing matches, or if only libraries other than movie and
TV libraries match. `--type movie` or `--type show` SHALL limit the titles to movies or shows.

#### Scenario: Music library
- **WHEN** the server has a music library
- **THEN** it is not checked and appears in `skipped_libraries` with type `artist`

#### Scenario: Asking for a music library
- **WHEN** run with `--library Music` and "Music" is a music library
- **THEN** the script stops with an error saying only movie and TV libraries are checked

### Requirement: Watched status
Watched status SHALL come from the signed-in account's own view state on each library item. A movie
SHALL be `watched` when its `viewCount` is 1 or more, `in_progress` when it has no `viewCount` but has
a `viewOffset`, and `unwatched` otherwise. A show SHALL be `unwatched` when `viewedLeafCount` is 0 or
missing, `watched` when `viewedLeafCount` is at least `leafCount`, and `started` otherwise. With
`--unwatched`, only movies that are `unwatched` or `in_progress` and shows that are `unwatched` SHALL
match.

#### Scenario: A movie watched once
- **WHEN** a movie has `viewCount` 1 and run with `--unwatched`
- **THEN** it does not match

#### Scenario: A movie half watched
- **WHEN** a movie has no `viewCount` and a `viewOffset` of 40 minutes, and run with `--unwatched`
- **THEN** it matches with `watched` set to `in_progress`

#### Scenario: A show partly watched
- **WHEN** a show has `leafCount` 20 and `viewedLeafCount` 3, and run with `--unwatched`
- **THEN** it does not match, and without `--unwatched` it has `watched` set to `started`

### Requirement: Filters
Every filter given SHALL have to match for a title to be included:
- `--genre NAME` (repeatable): the title has at least one of the named genres, compared
  case-insensitively. Library listings carry at most two genres per title, so the script SHALL find
  matching titles with Plex's own genre filter: it reads each library's genres from
  `/library/sections/{id}/genre`, and for each named genre that library has, reads
  `/library/sections/{id}/all` with that genre's key as the `genre` parameter. A named genre a
  library doesn't have matches nothing there.
- `--min-minutes N` and `--max-minutes N`: a movie's runtime, or a show's episode length, is within
  the range (inclusive). Titles with no known length SHALL NOT match when either is given.
- `--decade D` (such as `1990s` or `1990`), or `--year-from Y` and `--year-to Y` (inclusive): the
  release year is in the range. Giving `--decade` together with `--year-from` or `--year-to` SHALL be
  an error. Titles with no year SHALL NOT match when a year filter is given.
- `--min-rating N` (0 to 10): the title's audience rating, or its critic rating when it has no
  audience rating, is at least N. Titles with neither SHALL NOT match.
- `--content-rating NAME` (repeatable): the title's content rating is one of those named, compared
  case-insensitively.
- `--unwatched`: see "Watched status".

#### Scenario: Short comedies
- **WHEN** run with `--genre comedy --max-minutes 100`
- **THEN** only titles with the genre "Comedy" and a runtime of 100 minutes or less match

#### Scenario: A genre missing from the listing
- **WHEN** a movie's listing entry shows the genres "Drama" and "Romance", Plex's genre filter for
  "Comedy" includes it, and run with `--genre comedy`
- **THEN** the movie matches

#### Scenario: A decade
- **WHEN** run with `--decade 1980s`
- **THEN** only titles released from 1980 to 1989 match

#### Scenario: Decade and year together
- **WHEN** run with `--decade 1990s --year-from 1995`
- **THEN** the script stops with an error saying to use one or the other

#### Scenario: A genre the library doesn't have
- **WHEN** run with `--genre Western` and no title has that genre
- **THEN** the script exits 0 with `matches` 0, and `genres_available` lists the genres that exist

### Requirement: The same title in two libraries
Movies or shows with the same `guid` in more than one library SHALL be one entry, with `libraries` naming
every library it is in. For movies, that entry SHALL be `watched` if any copy is watched, otherwise
`in_progress` if any copy is in progress. For shows, it SHALL use the copy with the most episodes
watched. Items without a `guid` SHALL never be merged.

#### Scenario: A movie in Movies and 4K Movies
- **WHEN** the same movie is in "Movies" (watched) and "4K Movies" (not watched)
- **THEN** it appears once, `libraries` lists both, and it is `watched`

### Requirement: Order and limit
`--sort` SHALL choose the order of matching titles: `random` (the default; shuffled, so a second run
can give different titles), `rating` (highest first, using the same rating as `--min-rating`, titles
with no rating last), `added` (newest first) or `year` (newest release first). Ties outside `random`
SHALL be broken by title. `--limit N` (default 20, limited to 1–100) SHALL cap how many titles are
returned; `matches` SHALL count every matching title before the limit.

#### Scenario: More matches than the limit
- **WHEN** 300 titles match and the limit is 20
- **THEN** `matches` is 300 and `titles` holds 20

#### Scenario: Top rated
- **WHEN** run with `--sort rating`
- **THEN** `titles` is ordered from the highest rating down

### Requirement: Continue watching
`--continue` SHALL list what the signed-in account has in progress and the next episode of shows it
has started, from `/library/onDeck`, instead of the shortlist. It SHALL respect `--library`, `--type`
and `--limit`, and SHALL be an error when combined with any other filter or `--sort`. Each entry SHALL
have `type`, `title` (movies as "Title (Year)", episodes as the show title), `library`, and for
episodes `episode` (such as "S02E05") and `episode_title`. It SHALL also have `progress_pct` (one
decimal, 0 when not started), `minutes_left` and `last_viewed` (date, or `null`), in the order Plex
returns them.

#### Scenario: Halfway through a movie
- **WHEN** a 120 minute movie has a `viewOffset` of 60 minutes
- **THEN** its entry has `progress_pct` 50.0 and `minutes_left` 60

#### Scenario: Next episode up
- **WHEN** the next episode of a started show hasn't been started
- **THEN** its entry has `progress_pct` 0 and its `episode` and `episode_title`

#### Scenario: Continue with a genre
- **WHEN** run with `--continue --genre drama`
- **THEN** the script stops with an error saying `--continue` only works with `--library`, `--type`
  and `--limit`

### Requirement: Report contents
The JSON report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version), `mode`
(`pick` or `continue`), `filters` (the filters and sort that were applied), `libraries_checked`,
`skipped_libraries`, and either `matches`, `titles`, `genres_available` and `content_ratings_available`
(in `pick` mode) or `continue_watching` (in `continue` mode).

Each title SHALL have `type` (`movie` or `show`), `title` (movies as "Title (Year)", shows as the show
title), `year`, `libraries`, `genres` (as given in the library listing, so at most two),
`critic_rating`, `audience_rating`, `content_rating`, `summary`, `added` (date) and `watched`. Movies SHALL have `minutes`. Shows SHALL have
`episode_minutes`, `seasons`, `episodes` and `episodes_watched`. Missing values SHALL be `null`.

`genres_available` SHALL list, sorted and without repeats, every genre from
`/library/sections/{id}/genre` for the libraries checked. `content_ratings_available` SHALL list,
sorted, every content rating found on the titles in the libraries checked. Both SHALL be worked out
after `--type` and `--library` and before the other filters.

#### Scenario: Nothing matches
- **WHEN** no title matches the filters
- **THEN** `matches` is 0, `titles` is empty, and the script exits 0

#### Scenario: A long summary
- **WHEN** a title's summary is 600 characters long
- **THEN** `summary` is cleaned and cut to 120 characters, like every other server text

### Requirement: Options
The script SHALL accept `--type movie|show`, `--library NAME`, `--genre NAME`, `--min-minutes N`,
`--max-minutes N`, `--decade D`, `--year-from Y`, `--year-to Y`, `--min-rating N`,
`--content-rating NAME`, `--unwatched`, `--continue`, `--sort random|rating|added|year`, `--limit N`
and `--check`. A value that can't be understood (such as `--decade nineties` or `--min-rating 12`)
SHALL stop the script with an error naming the option.

#### Scenario: Out-of-range limit
- **WHEN** run with `--limit 9999`
- **THEN** at most 100 titles are returned

#### Scenario: Bad decade
- **WHEN** run with `--decade nineties`
- **THEN** the script stops with an error saying `--decade` takes a value like `1990s`

### Requirement: Connection check
`--check` SHALL test the Plex connection only and print the server name and version.

#### Scenario: Checking the connection
- **WHEN** run with `--check`
- **THEN** it requests `/` once and prints the server name and version
