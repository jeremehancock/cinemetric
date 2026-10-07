# title-lookup Specification

## Purpose

A read-only answer about one movie, show or episode on a Plex server: what it is, its files and
quality, the likely transcode causes for each file (the same rules as `playback-check`), a show's
seasons, and who watched it and how far they got. When several titles match, it lists them instead of
guessing. It states facts only and never suggests changing files. Script:
`skills/title-lookup/scripts/title_lookup.py`. How Claude presents it is in the skill's `SKILL.md`.

## Requirements
### Requirement: Sources used
The script `skills/title-lookup/scripts/title_lookup.py` SHALL request only `/`,
`/library/sections`, `/library/sections/{id}/all`, `/library/metadata/{ids}`,
`/library/metadata/{id}/allLeaves`, `/status/sessions/history/all`, `/accounts` and `/:/prefs` from the
user's Plex server, all with `GET`. `/accounts` SHALL be requested only to put names to Plex history
entries, and only each account's id and name SHALL be read from it. `{ids}` SHALL be 1 to 100 numeric rating keys separated by commas, and any
other form SHALL be refused by the path allowlist. From `/:/prefs` the script SHALL read only
`WanPerStreamMaxUploadRate` and `allowMediaDeletion` (see "Media deletion setting" in the conventions
spec), requesting it at most once per run; no other setting SHALL appear in its output.

When Tautulli is used, the script SHALL run only the Tautulli commands `get_tautulli_info` and
`get_history`. It SHALL NOT contact plex.tv or any other address.

#### Scenario: Looking up a movie with Tautulli set up
- **WHEN** the script looks up a movie with Tautulli set up
- **THEN** every request goes to the configured Plex server (one of the eight allowed paths, with
  `GET`) or to the configured Tautulli address (one of the two allowed commands)

#### Scenario: Asking for too many titles at once
- **WHEN** the script tries to request `/library/metadata/` with 101 rating keys
- **THEN** it stops with the blocked request error and nothing is sent

### Requirement: Finding the title
The script SHALL take a title as its first argument, or a rating key with `--key`. Only movie and TV
libraries SHALL be searched, movies with the movie listing (`type=1`) and shows with the show listing
(`type=2`), using Plex's `title` filter. A title SHALL match when its title or original title contains
the asked-for text, ignoring case, spaces and punctuation. If the filtered listings find nothing, the
script SHALL read the full listings and match the same way, so "spiderman" finds "Spider-Man". When
any title matches exactly (ignoring case, spaces and punctuation), only exact matches SHALL be kept. `--year N`,
`--library NAME` (repeatable, case-insensitive) and `--type movie|show` SHALL narrow the matches.
Titles with the same Plex `guid` in several libraries SHALL count as one match listing every library.

When exactly one match is left, the script SHALL report on it. When none or more than one is left, it
SHALL print `matches` (at most 20, each with `rating_key`, `title`, `year`, `type` and `libraries`),
`match_count` and `title` `null`, and exit 0. `--library` matching nothing, or only libraries other
than movie and TV libraries, SHALL stop the script with an error. `--key` with a rating key Plex
doesn't know SHALL stop the script with an error saying no title has that key.

#### Scenario: One clear match
- **WHEN** run with `"blade runner 2049"` and the server has "Blade Runner" and "Blade Runner 2049"
- **THEN** the report is about "Blade Runner 2049", because it matches exactly

#### Scenario: Several matches
- **WHEN** run with `"star"` and five titles contain "star"
- **THEN** `title` is `null`, `match_count` is 5 and `matches` lists all five

#### Scenario: Narrowing by year
- **WHEN** run with `"dune" --year 2021` and the server has Dune (1984) and Dune (2021)
- **THEN** the report is about Dune (2021)

#### Scenario: The same movie in two libraries
- **WHEN** "Up" is in Movies and in Kids Movies with the same `guid`
- **THEN** it is one match, and the report lists both libraries and both libraries' files

#### Scenario: Punctuation in the title
- **WHEN** run with `"spiderman"` and the server has "Spider-Man"
- **THEN** the report is about "Spider-Man"

#### Scenario: Nothing found
- **WHEN** no title contains the asked-for text
- **THEN** `matches` is empty, `match_count` is 0 and the script exits 0

### Requirement: Finding an episode
`--season N` and `--episode N` SHALL be accepted only together and only when the match is a show (or
`--key` names a show). The script SHALL find the episode in the show's `allLeaves` listing by season
and episode number and report on that episode, with the show's title alongside. If the show has no
such episode, the script SHALL report on the show and set `episode_not_found` to the asked-for season
and episode.

#### Scenario: A specific episode
- **WHEN** run with `"the office" --season 3 --episode 7` and that episode is on the server
- **THEN** the report is about that episode, with `show_title` "The Office"

#### Scenario: Episode not on the server
- **WHEN** season 3 has no episode 30
- **THEN** the report is about the show, and `episode_not_found` is `{"season": 3, "episode": 30}`

#### Scenario: Episode options with a movie
- **WHEN** `--season` and `--episode` are given and the only match is a movie
- **THEN** the script stops with an error saying season and episode only apply to shows

### Requirement: What is reported about the title
For the chosen title the report SHALL give `type` (`movie`, `show` or `episode`), `title`, `year`,
`rating_key`, `libraries`, `added_at`, `duration_minutes` (movies and episodes), `content_rating`,
`genres`, `audience_rating` and `critic_rating` (each `null` when Plex has none), `collections` (the
names of the Plex collections it belongs to) and `summary` cut to 300 characters. Every text value
from the server SHALL be cleaned as described in "Server text is treated as data" in the security
spec.

#### Scenario: A movie in two collections
- **WHEN** a movie's details list the collections "Pixar" and "Family Night"
- **THEN** `collections` is `["Pixar", "Family Night"]`

#### Scenario: A long summary
- **WHEN** a summary is 900 characters long
- **THEN** `summary` is cut to 300 characters

### Requirement: Files
For a movie or episode, `files` SHALL list each media version separately with `library`,
`resolution`, `video_codec`, `hdr` (true when Plex reports an HDR or Dolby Vision color profile),
`bit_depth`, `audio_codec`, `audio_channels`, `container`, `bitrate_kbps`, `size_bytes`, `path` and
`available` (false when the media version has a `deletedAt` value). `total_size_bytes` SHALL add up
the available files.

#### Scenario: A 4K and a 1080p version
- **WHEN** a movie has a 4K HEVC version and a 1080p H.264 version
- **THEN** `files` has two entries with their own resolution, codecs, size and path

#### Scenario: A file Plex can't find
- **WHEN** a media version has a `deletedAt` value
- **THEN** its entry has `available` false and its size is left out of `total_size_bytes`

### Requirement: Playback causes
Each available file SHALL get `playback_causes` using exactly the rules of the `playback-check` spec's
"Image-based subtitles", "TrueHD and DTS audio" and "Bitrate above the limit" requirements, with the
same cause names and details, the same limit (`--max-bitrate KBPS`, otherwise the server's
`WanPerStreamMaxUploadRate` above 0) and the same `bitrate_limit` field (`null` when there is no
limit). Subtitle and audio tracks SHALL come from `/library/metadata/{ids}`.

For a show, the report SHALL NOT list each episode's file. It SHALL give `playback_summary`: the
number of available episode files checked and how many have each cause, reading episode details in
batches of at most 100. Episodes the detail listing doesn't return SHALL be counted in
`details_missing`.

#### Scenario: Same answer as playback-check
- **WHEN** a file has an English PGS track and no other English subtitles
- **THEN** its `playback_causes` include `image_subtitles`, as `playback-check` reports for the same
  file

#### Scenario: A show with 250 episodes
- **WHEN** the title is a show with 250 episodes
- **THEN** episode details are read in 3 requests and `playback_summary` counts each cause

### Requirement: Seasons for a show
For a show, `seasons` SHALL list each season with `season`, `episodes` (episodes with at least one
available file), `unavailable` (episodes whose every file has a `deletedAt` value) and `size_bytes`.
Season 0 SHALL be listed as specials. The report SHALL give `episode_count`, `total_size_bytes` and
`first_added_at` and `last_added_at` across the show's episodes. It SHALL NOT work out gaps; that is
`episode-gaps`' job.

#### Scenario: Specials and a missing file
- **WHEN** a show has seasons 0, 1 and 2, and one season 2 episode's only file has a `deletedAt` value
- **THEN** `seasons` lists all three, season 2 has `unavailable` 1, and that episode isn't counted in
  `episodes`

### Requirement: Watching
Plays SHALL come from Tautulli or Plex following the `watch-activity` spec's "Choosing a source"
requirement, with the same `--source` values and `fallback_reason`. With Tautulli, `get_history` SHALL
be filtered by `rating_key` for a movie or episode and `grandparent_rating_key` for a show. With Plex,
`/status/sessions/history/all` SHALL be filtered with `metadataItemID` set to the title's rating key,
and only entries whose rating key (movie or episode) or show key (`grandparentRatingKey`, or the number
at the end of `grandparentKey`) is the title's SHALL count. At most 20,000 entries SHALL be read, with
`history_capped` set when that limit is reached.

`watching` SHALL give `source`, `plays`, `last_played_at`, `last_finished_at` and `people`: for each
person, `name`, `plays`, `last_played_at`, `finished` (whether any play was finished) and, for a show,
`episodes_finished` (distinct episodes finished). With Tautulli each person SHALL also have
`furthest_percent`; with Plex it SHALL be `null`, since Plex's history only records finished plays.
A play SHALL count as finished with Tautulli when `watched_status` is 1 or more, and always with Plex.
`people` SHALL be sorted by most recent play. Nothing about a person beyond these fields SHALL be
printed.

If the history can't be read for any reason other than `--source tautulli` failing (for example Plex
answers 401 or 403 on a server the user doesn't own), `watching` SHALL be `null`, `watching_unavailable`
SHALL give the reason, and the rest of the report SHALL still be printed with exit 0.

#### Scenario: Two people watched a movie
- **WHEN** Tautulli has a finished play by Alex and a play at 40% by Sam
- **THEN** `people` has Alex with `finished` true and Sam with `finished` false and `furthest_percent`
  40, and `last_finished_at` is Alex's play

#### Scenario: Episodes finished in a show
- **WHEN** Sam finished episodes 1, 2 and 3 of a show, and episode 2 twice
- **THEN** Sam has `episodes_finished` 3 and `plays` 4

#### Scenario: Not the server owner
- **WHEN** Plex is the source and `/status/sessions/history/all` answers 403
- **THEN** `watching` is `null`, `watching_unavailable` explains Plex only shares history with the
  owner, and the rest of the report is printed

#### Scenario: Never watched
- **WHEN** the title has no plays
- **THEN** `watching.plays` is 0, `people` is empty and `last_played_at` is `null`

### Requirement: Options
The script SHALL accept a title, `--key RATING_KEY`, `--year N`, `--library NAME` (repeatable),
`--type movie|show`, `--season N`, `--episode N`, `--source auto|tautulli|plex` (default `auto`),
`--max-bitrate KBPS` and `--check`. Exactly one of a title and `--key` SHALL be given, except with
`--check`. `--season` and `--episode` SHALL be whole numbers of 0 or more, and `--year` and
`--max-bitrate` SHALL be positive whole numbers.

#### Scenario: Neither a title nor a key
- **WHEN** the script runs with no title and no `--key`
- **THEN** it stops with an error saying a title or `--key` is needed

