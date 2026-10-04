# library-report Specification

## Purpose

A read-only summary of what's in a Plex server's libraries: counts, storage, video quality and codecs,
recent additions and housekeeping problems. Script: `skills/library-report/scripts/library_report.py`.
How Claude presents it is in the skill's `SKILL.md`.

## Requirements

### Requirement: Plex paths used
The script SHALL request only `/`, `/library/sections` and `/library/sections/{id}/all`, reading items
in pages of 500.

#### Scenario: Large library
- **WHEN** a library has more than 500 items of a type
- **THEN** the script fetches them page by page until it has them all

### Requirement: Options
The script SHALL accept `--library NAME` (repeatable, case-insensitive; error if nothing matches),
`--recent N` (recently added items per library, default 10, limited to 0–100) and `--large-gb N`
(size at which a file counts as very large, default 40).

#### Scenario: Unknown library name
- **WHEN** `--library Cartoons` matches no library
- **THEN** the script stops with an error saying no library matched

### Requirement: Report contents
The report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version, platform),
`totals` (libraries, files, size_gb) and one entry per library with `name`, `type`, `counts`, `media`,
`recently_added` and `housekeeping`. Per library type:
- movie: count of movies; media and housekeeping over movies.
- show: counts of shows, seasons and episodes; media over episodes; housekeeping over shows.
- artist (music): counts of artists, albums and tracks; media over tracks without video fields;
  recently added and housekeeping over albums.
- photo: count of photos only.
- any other type: a note that it isn't summarized.

#### Scenario: Photo library
- **WHEN** a library is a photo library
- **THEN** its entry has only a photo count, with no media, recently added or housekeeping sections

### Requirement: Media breakdown
`media` SHALL include the number of files and their total size in GB, resolution split (4K, 2K,
1080p, 720p, SD, or the raw value), video codecs, audio codecs, the number of 10-bit files, very
large files (up to 15 examples, largest first, plus a total) and files Plex lists as unavailable (up
to 15 examples plus a count). A file counts as 10-bit when its video profile contains "10"; the
report SHALL NOT call these files HDR, because the library listing doesn't say which files are HDR.

#### Scenario: A file Plex can't find
- **WHEN** a media item has a `deletedAt` value
- **THEN** it is counted in `unavailable_files` and listed in `unavailable_examples`

### Requirement: Housekeeping
`housekeeping` SHALL count items with no poster and items that are unmatched (no `guid`, or a
`local://` one), each with up to 15 examples.

#### Scenario: Unmatched movie
- **WHEN** a movie's `guid` starts with `local://`
- **THEN** it is counted in `unmatched_count`
