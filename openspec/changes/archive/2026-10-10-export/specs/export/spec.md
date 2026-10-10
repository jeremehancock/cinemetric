## ADDED Requirements

### Requirement: Sources used
The script `skills/export/scripts/export.py` SHALL itself request only `/`, `/library/sections`,
`/library/sections/{id}/all`, `/library/sections/{id}/collections`,
`/library/collections/{id}/children` and `/:/prefs` from the user's Plex server, all with `GET`,
reading listings in pages of 500. `/:/prefs` SHALL be read only for the media deletion setting (see
"Media deletion setting" in the conventions spec). It SHALL NOT contact Tautulli, plex.tv or any other
address itself. The other tabs SHALL come only from running other Cinemetric scripts, as described in
"Tabs built from other reports".

#### Scenario: Exporting with Tautulli set up
- **WHEN** the export runs and Tautulli is configured
- **THEN** no request goes to Tautulli from the export script or from any script it runs, and every
  Plex request the export script makes is `GET` to one of the allowed paths

#### Scenario: Not connected yet
- **WHEN** no Plex address and token are configured
- **THEN** the script stops with `error: NOT_CONFIGURED: ...`, runs no other script and writes no
  file

### Requirement: The tabs
The workbook SHALL have these tabs, in this order and with these names: `Server`, `Movies`,
`TV Shows`, `Issues`, `Episode gaps`, `Playback`, `Subtitles`. `Movies` SHALL be there only when at
least one movie library is included, and `TV Shows` only when at least one TV library is included;
each holds every included library of its kind, told apart by its `Library` column. `--skip TAB`
(repeatable; `server`, `issues`, `gaps`, `playback` or `subtitles`, any case) SHALL leave that tab
out of the workbook, and a script needed only by skipped tabs SHALL NOT be run. `Movies` and
`TV Shows` SHALL NOT be skippable. Every tab
other than `Server` SHALL start with one row of column names. Below a tab's rows, notes (a tab with
nothing found, rows left out by a limit, the report's `limits` sentence, a tab that couldn't be
built) SHALL be written as rows whose first cell starts with `Note: `, after one empty row.

#### Scenario: Every tab
- **WHEN** the export runs with no `--skip`
- **THEN** the workbook has the seven tabs in order, starting with `Server`

#### Scenario: Only a TV library
- **WHEN** run with `--library "TV Shows"`, a TV library
- **THEN** the workbook has a `TV Shows` tab and no `Movies` tab

#### Scenario: Skipping the slow checks
- **WHEN** run with `--skip playback --skip subtitles`
- **THEN** the workbook has `Server`, `Movies`, `TV Shows`, `Issues` and `Episode gaps`, and neither
  `playback_check.py` nor `subtitles_and_languages.py` is run

#### Scenario: Nothing found
- **WHEN** `episode_gaps.py` finds no show with gaps
- **THEN** the `Episode gaps` tab has its column names and a note saying no gaps were found

### Requirement: Which libraries are exported
Every movie and TV library SHALL be included unless `--library NAME` is given (repeatable, matched
ignoring case), which narrows the export to those libraries and SHALL be passed on to every script run
that accepts it (`library_report.py`, `episode_gaps.py`, `playback_check.py`,
`subtitles_and_languages.py`). Other libraries (music, photos) SHALL be named in `skipped_libraries`
with their type and SHALL have no rows. `--library` naming no library SHALL stop the script with an
error listing the movie and TV libraries; `--library` naming only libraries other than movie and TV
libraries SHALL stop it with an error saying only movie and TV libraries can be exported. These checks
SHALL happen before any other script is run. When no TV library is included, `episode_gaps.py` SHALL
NOT be run and the `Episode gaps` tab SHALL hold a note saying no TV library was included. If a
library's listing can't be read, that library SHALL have no rows, be named in `unavailable` with
`part` and `reason`, its tab (`Movies` or `TV Shows`) SHALL hold a note saying it couldn't be read and
why, and the workbook SHALL be built from the rest. If no included library's
listing can be read, the script SHALL stop with an error and write no file.

#### Scenario: A music library
- **WHEN** the server has "Movies", "TV Shows" and a music library "Music", and no `--library` is
  given
- **THEN** the `Movies` tab has the rows from "Movies", the `TV Shows` tab those from "TV Shows",
  "Music" has no tab and is in `skipped_libraries`

#### Scenario: One library can't be read
- **WHEN** the listing for "Movies" answers 500 and "Kids Movies" reads normally
- **THEN** the `Movies` tab has the "Kids Movies" rows and a note saying "Movies" couldn't be read
  and why, "Movies" is named in `unavailable`, and the script exits 0

#### Scenario: Asking for a music library
- **WHEN** run with `--library Music` and "Music" is a music library
- **THEN** the script stops with an error saying only movie and TV libraries can be exported, runs no
  other script and writes no file

#### Scenario: Movies only
- **WHEN** run with `--library Movies` and "Movies" is a movie library
- **THEN** `episode_gaps.py` isn't run and the `Episode gaps` tab says no TV library was included

### Requirement: Movies and TV Shows rows
Each movie library SHALL give one row per movie (`type=1`) on the `Movies` tab. Each TV library SHALL
give one row per show (`type=2`) on the `TV Shows` tab by default, or one row per episode (`type=4`)
with `--tv episodes`. Rows SHALL be in the
order the libraries are listed by Plex; within a library, movies and shows sorted by their sort title
(`titleSort`, else `title`) ignoring case, then year; episodes sorted by show (the same way), then
season number, then episode number, with unnumbered episodes last in their season.

#### Scenario: Default TV rows
- **WHEN** a TV library has 3 shows with 40 episodes between them and `--tv` isn't given
- **THEN** the `TV Shows` tab has 3 rows for that library, one per show

#### Scenario: Episode rows
- **WHEN** the same library is exported with `--tv episodes`
- **THEN** the `TV Shows` tab has 40 rows for that library, one per episode, grouped by show and in
  season and episode order

### Requirement: Movies and TV Shows columns
Each tab SHALL have only the columns that fit its rows, in this order and with these names:
- `Movies`: `Library`, `Title`, `Year`, `Added`, `Length (min)`, `Resolution`, `Video codec`,
  `Audio codec`, `Audio channels`, `Container`, `Size (GB)`, `Versions`, `Unavailable`,
  `Content rating`, `Watched`, `Last watched`, `Collections`.
- `TV Shows`, one row per show: `Library`, `Title`, `Year`, `Added`, `Resolution`, `Video codec`,
  `Audio codec`, `Audio channels`, `Container`, `Size (GB)`, `Episodes`, `Episodes unavailable`,
  `Content rating`, `Watched`, `Episodes watched`, `Last watched`, `Collections`.
- `TV Shows`, one row per episode: `Library`, `Show`, `Season`, `Episode`, `Title`, `Year`, `Added`,
  `Length (min)`, `Resolution`, `Video codec`, `Audio codec`, `Audio channels`, `Container`,
  `Size (GB)`, `Versions`, `Unavailable`, `Content rating`, `Watched`, `Last watched`, `Collections`.

A cell with no value SHALL be empty. The values SHALL be:
- `Title`: the movie's, show's or episode's title. `Show`, `Season` and `Episode`: the episode's show
  title and its season and episode numbers.
- `Year`: `year`, or the year of `originallyAvailableAt` when `year` is missing.
- `Added` and `Last watched`: dates in the computer's local time, from `addedAt` and `lastViewedAt`.
- `Length (min)`: `duration` in whole minutes, rounded.
- Media details for movies and episodes, from the best media version Plex can still find (highest
  resolution, then highest bitrate): `Resolution` as a bucket using the same rule as `library-report`
  (`4K`, `2K`, `1080p`, `720p`, `SD`), `Video codec`, `Audio codec`, `Audio channels` and `Container`
  as Plex gives them.
- Media details for shows: for each of those five columns, the value most of the show's episodes
  have (from each episode's best version Plex can still find), ties going to the better resolution or,
  for the other columns, the first in alphabetical order.
- `Size (GB)`: every part of every media version Plex can still find (versions with `deletedAt` left
  out), in GB of 1,000,000,000 bytes, rounded to two decimal places; for shows, the total of their
  episodes.
- `Versions`: the number of media versions Plex can still find.
- `Unavailable`: `Yes` when Plex can find none of the movie's or episode's media versions, otherwise
  `No`. `Episodes` and `Episodes unavailable`: the number of the show's episodes in the episode
  listing and how many of those are unavailable.
- `Content rating`: `contentRating` as Plex gives it.
- Watched status, for the Plex account Cinemetric is signed in with: for movies and episodes,
  `Watched` is `Yes` when `viewCount` is at least 1, `Partly` when it isn't but `viewOffset` is above
  0, otherwise `No`. For shows, `Episodes watched` is `viewedLeafCount`, and `Watched` is `Yes` when
  every episode (`leafCount`) is watched, `Partly` when some are, and `No` when none are.
- `Collections`: see "Collections".

#### Scenario: A movie with two versions
- **WHEN** a movie has a 1080p version of 8 GB and a 4K version of 50 GB, both available
- **THEN** its row has `Resolution` `4K`, `Size (GB)` 58 and `Versions` 2

#### Scenario: A movie whose file is gone
- **WHEN** a movie's only media version has `deletedAt` set
- **THEN** its row has `Unavailable` `Yes`, `Size (GB)` 0, `Versions` 0 and empty media detail
  columns

#### Scenario: A mixed-quality show
- **WHEN** a show has 10 episodes in 1080p and 2 in 720p, one of the 720p episodes unavailable
- **THEN** its row has `Resolution` `1080p`, `Episodes` 12 and `Episodes unavailable` 1

#### Scenario: A show partly watched
- **WHEN** a show has `leafCount` 12 and `viewedLeafCount` 5
- **THEN** its row has `Watched` `Partly` and `Episodes watched` 5

#### Scenario: A movie started but not finished
- **WHEN** a movie has no `viewCount` and a `viewOffset` of 1,200,000
- **THEN** its row has `Watched` `Partly`

### Requirement: Collections
For each included library, the script SHALL read the library's collections from
`/library/sections/{id}/collections` and each collection's contents from
`/library/collections/{id}/children`. A movie row SHALL list the collections holding that movie. A
show row SHALL list the collections holding the show, one of its seasons or one of its episodes. An
episode row SHALL list the collections holding the episode, its season or its show. Names SHALL be
listed once each, sorted ignoring case, joined with `; `. If a library's collection list can't be
read, the `Collections` cells for that library SHALL be empty and the library named in `unavailable`
with `part` `collections`; if some collections' contents can't be read, `unavailable` SHALL have one
entry for that library with `part` `collection contents`, how many `collections` couldn't be read and
the first reason (without the collections' names, since the summary holds none), and the other
collections SHALL still be listed. Neither SHALL stop the export.

#### Scenario: A movie in two collections
- **WHEN** a movie is in the collections "Test Trilogy" and "Award Winners"
- **THEN** its `Collections` cell is `Award Winners; Test Trilogy`

#### Scenario: A collection holding one season
- **WHEN** a collection "Holiday Specials" holds season 2 of a show
- **THEN** the show's row lists "Holiday Specials", and with `--tv episodes` every season 2 episode
  row lists it and the season 1 rows don't

#### Scenario: Collections can't be read
- **WHEN** `/library/sections/{id}/collections` answers 500 for "Movies"
- **THEN** the "Movies" rows are still in the tab with empty `Collections` cells, and `unavailable`
  names "Movies" with `part` `collections`

### Requirement: Tabs built from other reports
The script SHALL run, side by side and only when a tab that needs them isn't skipped:
- `server_health.py --stuck-wait 0` (for `Server`);
- `library_report.py --recent 0 --growth-months 0 --music-examples 0 --duplicate-examples 500
  --upgrade-examples 500` (for `Server` and `Issues`);
- `episode_gaps.py --limit 500` (for `Episode gaps`);
- `playback_check.py --limit 500 --days 0` (for `Playback`; `--days 0` keeps Tautulli, people and
  devices out);
- `subtitles_and_languages.py --limit 500`, with each `--language` given to the export (for
  `Subtitles`).

Each SHALL be found in its own skill's `scripts` folder next to the export skill and run with the
same Python, as the dashboard runs its reports. A report that fails, runs longer than 30 minutes or
prints something that isn't a JSON object SHALL NOT stop the export: the tabs that needed it SHALL hold
a note saying the tab couldn't be built and why (an `OWNER_ONLY` error explained as only available to
the server owner, without the code), the summary's `tabs` SHALL give the reason, and the rest of the
workbook SHALL be saved. Only the fields named in this spec SHALL be copied from a report into the
workbook; in particular, nothing that describes only the moment the export was made (what is
streaming now, CPU and memory use, running tasks) SHALL be copied (see "Server tab").

#### Scenario: Playback check fails
- **WHEN** `playback_check.py` exits with an error
- **THEN** the workbook is saved, the `Playback` tab holds a note with the reason, the other tabs are
  filled in, and the script exits 0

#### Scenario: Someone is streaming during the export
- **WHEN** `server_health.py` reports a stream by `alex-test` on "Alex's iPhone" watching "Night of the
  Test"
- **THEN** the workbook says nothing about streams now: no stream count or bandwidth, and none of
  `alex-test`, "Alex's iPhone" or "Night of the Test" (unless it's also a title on the `Movies` tab)
  comes from that stream

### Requirement: Server tab
The `Server` tab SHALL have two columns, `Item` and `Value`, in sections, each section starting with
a heading row (the section name in `Item`, `Value` empty):
- **Export:** date and time made, Cinemetric version, tabs left out with `--skip`, and that watched
  status is for the Plex account Cinemetric is signed in with.
- **Server:** name, version, platform, whether an update is available (and its version), and remote
  access state. The server's public address SHALL NOT be included.
- **Streaming settings** and **Maintenance settings:** each setting `server_health.py` keeps, with a
  fixed plain-English label; on/off settings as `On` or `Off`, others as numbers.
- **Worth a look:** one row per `worth_a_look` item, with a fixed plain-English sentence for each
  `kind` in `Item` and its details (such as the limit or the tasks) in `Value`; `Nothing` when there
  are none. Items about the moment the export was made SHALL be left out: `transcode_too_slow`
  (someone's stream), `high_cpu`, `high_memory` and `task_not_progressing`.

The tab SHALL NOT include CPU or memory use (`resource_use`).

After the sections, one empty row, then a libraries table with its own row of column names:
`Library`, `Type`, `Items`, `Files`, `Size (GB)`, `Last scanned`, one row per library in
`library_report.py`'s report (including music and photos), with `Last scanned` the date part of
`server_health.py`'s `last_scanned` for the library with the same name. A part `server_health.py`
couldn't read SHALL be a row saying it isn't available and why.

#### Scenario: Busy at the moment of the export
- **WHEN** `server_health.py` reports CPU use of 91% with a `high_cpu` item, a `high_memory` item and
  a `task_not_progressing` item
- **THEN** the `Server` tab has no CPU or memory figures and no row for any of those three items

#### Scenario: Not the server owner
- **WHEN** `server_health.py` reports the update check as unavailable to anyone but the server owner
- **THEN** the `Server` section has a row saying the update check is only available to the server
  owner's account, and the rest of the tab is filled in

#### Scenario: A slow transcode
- **WHEN** `worth_a_look` has a `transcode_too_slow` item with `user` `alex-test` and a title
- **THEN** the `Worth a look` section has no row for it, and nothing from it appears in the workbook

#### Scenario: A low remote limit
- **WHEN** `worth_a_look` has a `remote_stream_limit_low` item with `limit_kbps` 4000
- **THEN** the `Worth a look` section has a row about the low remote streaming limit with 4000 kbps in
  `Value`

### Requirement: Issues tab
The `Issues` tab SHALL have the columns `Library`, `Issue`, `Title`, `Show`, `Season`, `Episode`,
`Year`, `Size (GB)`, `Details`, with one row per issue, in this order of `Issue`:
- `File missing`: every movie and episode with no media version Plex can still find, from the
  export's own listings (whatever `--tv` is).
- `Unmatched`: every movie and show with no `guid` or a `local://` one, from the export's own
  listings.
- `No poster`: every movie and show with no `thumb`, from the export's own listings.
- `Duplicate copies`: each example in each library's `duplicates`, with the extra space in
  `Size (GB)` and, in `Details`, the copies (resolution, codec and size) for a movie or the number of
  duplicated episodes for a show.
- `In more than one library`: each example in `cross_library_duplicates`, with the library names
  joined with `; ` in `Library`, the extra space in `Size (GB)` and each library's copy (or the number
  of episodes) in `Details`.
- `Low resolution`: each example in each library's `upgrades`, with the resolution and codec for a
  movie, or the number of episodes by resolution for a show, in `Details`.

Within an issue, rows SHALL be in library order, then by title. `library-report` gives a movie's title
as "Title (Year)"; the year SHALL go in `Year` and the rest in `Title`. When a report section has more
titles (or, for TV, episodes) than its examples cover, a note SHALL say how many were left out of that
issue in that library.

#### Scenario: Every missing file is listed
- **WHEN** 40 episodes across a library have no media version Plex can find
- **THEN** the `Issues` tab has 40 `File missing` rows for that library, each with show, season and
  episode, even though `library-report` itself lists at most 15 examples

#### Scenario: More duplicates than the limit
- **WHEN** a library's `duplicates` has `titles` 620 and 500 examples
- **THEN** the tab has 500 `Duplicate copies` rows for it and a note saying 120 more weren't listed

### Requirement: Episode gaps tab
The `Episode gaps` tab SHALL have the columns `Library`, `Show`, `Year`, `Season`,
`Missing episodes`, `Missing count`, `Unavailable episodes`, `Note`, with one row per season listed
in each listed show's `seasons` and one row per season in its `missing_seasons` (`Missing episodes`
`Whole season`). Episode numbers SHALL be written as text with ranges joined, such as `3, 5-7`.
`Note` SHALL say when a season continues the previous season's numbering, or, on the show's first
row, when the show starts at a later season. Rows SHALL follow the report's order of shows, then
season number. The tab SHALL end with notes for each library's `more_shows` (when above 0) and the
report's `limits` sentence.

#### Scenario: Several gaps in one season
- **WHEN** a listed show's season 3 has `missing` `[[3, 3], [5, 7]]`
- **THEN** its row has `Season` 3, `Missing episodes` `3, 5-7` and `Missing count` 4

### Requirement: Playback tab
The `Playback` tab SHALL have the columns `Library`, `Type`, `Title`, `Year`, `Episodes`,
`Episodes flagged`, `Resolution`, `Size (GB)`, `Bitrate (kbps)`, `Image subtitles`, `TrueHD audio`,
`DTS audio`, `Over bitrate limit`, `Details`. For a movie library, one row per flagged file of each
listed movie, with `1` in each cause column that applies and, in `Details`, the image subtitle
languages and the audio codec and whether a common alternative track exists. For a TV library, one
row per listed show, with `Episodes`, `Episodes flagged` and the number of episodes with each cause.
Rows SHALL follow the report's order. The tab SHALL end with notes for the bitrate limit used (and
`bitrate_limit_problem` when present), each library's `more` (when above 0) and the report's `limits`
sentence. Nothing from the report's history part SHALL be copied.

#### Scenario: A show with DTS episodes
- **WHEN** a listed show has 30 episodes, 12 of them with DTS audio
- **THEN** its row has `Episodes` 30, `Episodes flagged` 12 and `DTS audio` 12

### Requirement: Subtitles tab
The `Subtitles` tab SHALL have the columns `Library`, `Finding`, `Type`, `Title`, `Year`,
`Episodes`, `Episodes flagged`, `Which episodes`, `Resolution`, `Audio languages`,
`Subtitle languages`, `Forced subtitles`. `Finding` SHALL be a fixed plain-English label for each of
`foreign_no_subtitles`, `no_subtitles` and `unknown_language`, naming the library's language. For a
movie library, one row per listed file; for a TV library, one row per listed show, with `Which
episodes` written as text such as `S1 E2-3, E7` (adding the unnumbered episodes' titles). Languages
SHALL be written by name using `language_names`, or as the code when there's no name, joined with
`, `. Rows SHALL be grouped by finding in the order above, then follow the report's order. The tab
SHALL end with notes for each `language_problem`, each library's `more` per finding (when above 0) and
the report's `limits` sentence.

#### Scenario: A show with some foreign episodes
- **WHEN** a listed show under `foreign_no_subtitles` has `seasons`
  `[{"season": 1, "episodes": [[2, 3], [7, 7]], "some_versions": []}]` and `audio_languages`
  `{"es": 3}`
- **THEN** its row has `Which episodes` `S1 E2-3, E7` and `Audio languages` `Spanish`

### Requirement: The workbook format
The file SHALL be an Office Open XML workbook (`.xlsx`) built with Python's standard library. Every
tab's first row of column names SHALL be bold and stay in view when scrolling, and the `Movies`,
`TV Shows`,
`Issues`, `Episode gaps`, `Playback` and `Subtitles` tabs SHALL have filter buttons on their column
names. Numbers SHALL be stored as numbers and dates as dates shown as `YYYY-MM-DD`, so they sort
properly. Every other value SHALL be stored as plain text written into the cell itself (an inline
string). The workbook SHALL NOT contain any formula, macro, external link, hyperlink, data
connection or embedded object.

#### Scenario: Opening the file
- **WHEN** the file is opened in a spreadsheet program
- **THEN** it opens without warnings about links, macros or repairs, and shows the tabs in order

#### Scenario: Sorting by size
- **WHEN** the user sorts the `Movies` tab by `Size (GB)`
- **THEN** it sorts as numbers, not as text

### Requirement: Server text never runs
Every title, name and other value from a report or from Plex SHALL first be cleaned as described in
the security spec's "Server text is treated as data" (control characters replaced with spaces; cut to
120 characters; in `Collections`, each name cut before joining). A report's `limits` sentence and
error reasons SHALL have control characters replaced the same way but SHALL NOT be cut, since they're
fixed sentences longer than 120 characters. Characters not allowed in XML SHALL also be removed, and
`&`, `<`, `>` and quotes escaped. Text SHALL always be stored as an inline string, so text starting
with `=`, `+`, `-` or `@` is shown as written and never run as a formula.

#### Scenario: A title made to be a formula
- **WHEN** a movie's title is `=HYPERLINK("http://example.invalid","Click")`
- **THEN** the cell holds that exact text as an inline string, and the workbook contains no formula
  and no hyperlink

#### Scenario: A title made to break the file
- **WHEN** a movie's title is `</t></is></c><c><f>1+1</f>`
- **THEN** the cell shows that text and the workbook contains no formula

### Requirement: Where the file is saved
Without `--output`, the file SHALL be saved in Cinemetric's data folder (see "Settings location" in
the conventions spec) as `plex-export-<date>.xlsx`, where `<date>` is today's local date as
`YYYY-MM-DD`; with `--library`, as `plex-export-<names>-<date>.xlsx`, where `<names>` is each named
library in lower case with every run of characters other than `a` to `z` and `0` to `9` turned into
one `-` and any `-` at either end removed, joined with `-` and cut to 60 characters (`library` if
nothing is left); with `--tv episodes`, `-episodes` SHALL come before `-<date>`. A file of that name
in the data folder SHALL be replaced.

With `--output PATH` (`~` expanded): if `PATH` is an existing folder, the file SHALL be saved there
with the default name; otherwise `PATH` SHALL be the file to write, ending in `.xlsx` (any case), in a
folder that already exists. In a folder the user names, the script SHALL NOT create the folder or
change its permissions, and SHALL stop with `error: FILE_EXISTS: ...` when the file is already there,
unless `--replace` is given. These checks SHALL happen before Plex is contacted or any other script is
run. A path that isn't a folder and doesn't end in `.xlsx`, or whose folder doesn't exist, SHALL stop
the script with `error: BAD_OUTPUT: ...`.

Wherever it goes, the file SHALL be written in one step (to a temporary file in the same folder, then
moved into place) and created readable only by the user (`600`), with no moment where looser
permissions apply. On failure no partial file SHALL be left.

#### Scenario: Default place
- **WHEN** run with no `--output` on 9 October 2026
- **THEN** the file is `plex-export-2026-10-09.xlsx` in the data folder, the folder is `700` and the
  file is `600`

#### Scenario: Running twice the same day
- **WHEN** the default export runs twice on the same day
- **THEN** the second run replaces the first file and the data folder still holds one export for that
  day

#### Scenario: One library, episodes
- **WHEN** run with `--library "TV Shows" --tv episodes` on 9 October 2026
- **THEN** the file is `plex-export-tv-shows-episodes-2026-10-09.xlsx`

#### Scenario: A library name with slashes
- **WHEN** run with `--library "../Kids/Movies"`, a library of that name exists, and no `--output`
- **THEN** the file name is `plex-export-kids-movies-<date>.xlsx` and the file is in the data folder

#### Scenario: Saving to the user's Documents folder
- **WHEN** run with `--output ~/Documents`, which exists with permissions `755`
- **THEN** the file is saved there with the default name and is `600`, and the folder's permissions
  are still `755`

#### Scenario: The file is already there
- **WHEN** run with `--output ~/Documents/plex.xlsx` and that file exists, without `--replace`
- **THEN** the script stops with `error: FILE_EXISTS: ...` before contacting Plex or running another
  script, and the existing file is unchanged

#### Scenario: A folder that doesn't exist
- **WHEN** run with `--output ~/no-such-folder/plex.xlsx`
- **THEN** the script stops with `error: BAD_OUTPUT: ...` before contacting Plex

### Requirement: Options
The script SHALL accept `--library NAME` (repeatable), `--tv shows|episodes` (default `shows`),
`--language CODE` (repeatable, passed to `subtitles_and_languages.py`, which checks it), `--skip TAB`
(repeatable), `--output PATH`, `--replace` and `--check`. An unknown `--skip` value SHALL stop the
script with an error listing the allowed ones. `--check` SHALL only test the connection (see
"Connection check" in the conventions spec), SHALL NOT run any other script and SHALL NOT write a
file.

#### Scenario: Connection check
- **WHEN** run with `--check`
- **THEN** it prints the server name and version, runs no other script and writes no file

#### Scenario: Skipping a list tab
- **WHEN** run with `--skip movies`
- **THEN** the script stops with an error listing `server`, `issues`, `gaps`, `playback` and
  `subtitles`

### Requirement: Summary
On success the script SHALL print a JSON summary with `cinemetric_version`, `generated_at`, `server`
(name, version), `media_deletion_allowed`, `output` (the file's full path), `in_data_folder`,
`replaced` (whether an earlier file was replaced), `size_bytes`, `tv_rows` (`shows` or `episodes`),
`tabs` (each tab in the workbook with `name`, `rows` (data rows, not counting column names or notes)
and `problem` (why it couldn't be built, or `null`)), `skipped_tabs`, `libraries` (each included
library's `name`, `kind` and `rows` on its `Movies` or `TV Shows` tab), `skipped_libraries`, `unavailable` and
`watched_note` (saying watched status is for the Plex account Cinemetric is signed in with). The
summary SHALL NOT contain any title, show or collection name. Library names SHALL be cleaned as
described in the security spec.

#### Scenario: What reaches the chat
- **WHEN** a library holding a movie called "Night of the Test" is exported
- **THEN** "Night of the Test" is in the workbook and nowhere in the printed summary

#### Scenario: A tab that failed
- **WHEN** `subtitles_and_languages.py` fails
- **THEN** the `Subtitles` entry in `tabs` has `rows` 0 and `problem` giving the reason

### Requirement: No other people in the file
The workbook and the summary SHALL NOT contain any person's name, user name, account id, device or
player name, or anything read from watch history. Watched status SHALL come only from the library
listing's own fields for the signed-in account (`viewCount`, `viewOffset`, `viewedLeafCount`,
`lastViewedAt`).

#### Scenario: A shared server
- **WHEN** the server is shared with other people who have watched titles
- **THEN** the watched columns reflect only the signed-in account, the export script makes no request
  for watch history or accounts, and `playback_check.py` is run with `--days 0`
