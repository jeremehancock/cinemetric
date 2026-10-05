## MODIFIED Requirements

### Requirement: Options
The script SHALL accept `--library NAME` (repeatable, case-insensitive; error if nothing matches),
`--recent N` (recently added items per library, default 10, limited to 0–100), `--large-gb N`
(size at which a file counts as very large, default 40), `--duplicate-examples N` (duplicate
examples listed per library and across libraries, default 15, limited to 0–500),
`--upgrade-examples N` (upgrade examples listed per library, default 15, limited to 0–500) and
`--growth-months N` (months covered by each `growth` section, default 12, limited to 0–120).

#### Scenario: Unknown library name
- **WHEN** `--library Cartoons` matches no library
- **THEN** the script stops with an error saying no library matched

#### Scenario: Asking for every duplicate
- **WHEN** the script runs with `--duplicate-examples 500`
- **THEN** each `duplicates` section and `cross_library_duplicates` lists up to 500 examples

#### Scenario: Out-of-range example count
- **WHEN** the script runs with `--duplicate-examples 9999`
- **THEN** it lists at most 500 examples per section

#### Scenario: Asking for every upgrade candidate
- **WHEN** the script runs with `--upgrade-examples 500`
- **THEN** each `upgrades` section lists up to 500 examples

#### Scenario: Out-of-range upgrade example count
- **WHEN** the script runs with `--upgrade-examples -5`
- **THEN** each `upgrades` section lists no examples but still gives its counts

#### Scenario: Out-of-range growth months
- **WHEN** the script runs with `--growth-months 500`
- **THEN** each `growth` section covers 120 months

### Requirement: Report contents
The report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version, platform),
`totals` (libraries, files, size_gb), `growth` (all reported libraries combined),
`cross_library_duplicates`, and one entry per library with `name`, `type`, `counts`, `media`,
`recently_added`, `growth` and `housekeeping`. Per library type:
- movie: count of movies; media, housekeeping, `duplicates` and `upgrades` over movies; growth over
  movies.
- show: counts of shows, seasons and episodes; media, `duplicates`, `upgrades` and growth over
  episodes; housekeeping over shows.
- artist (music): counts of artists, albums and tracks; media and growth over tracks without video
  fields; recently added and housekeeping over albums; no `duplicates` or `upgrades` section.
- photo: count of photos only.
- any other type: a note that it isn't summarized.

#### Scenario: Photo library
- **WHEN** a library is a photo library
- **THEN** its entry has only a photo count, with no media, recently added, growth, housekeeping,
  duplicates or upgrades sections

#### Scenario: Music library
- **WHEN** a library is a music library
- **THEN** its entry has a `growth` section counted over tracks, and no `duplicates` or `upgrades`
  section

## ADDED Requirements

### Requirement: Growth by month
A `growth` section SHALL contain `months`: one row per calendar month for the last `--growth-months`
months, oldest first, ending with the current month (which is still in progress). Months SHALL use
the computer's local time zone, as `recently_added` does. Each row SHALL give `month` (`YYYY-MM`),
`added` (items whose `addedAt` falls in that month) and `gb` (the total size of all those items'
files as they are now, counting every part of every `Media` entry, as the media breakdown does).
Months with nothing added SHALL be listed with zeros. Items with no `addedAt` SHALL NOT be counted.

A library's `growth` SHALL also give `added` and `gb` for the whole period covered. The top-level
`growth` SHALL have the same shape, each month adding up every reported library that has a `growth`
section.

Growth SHALL use only the data the script already requests for the rest of the report.

#### Scenario: Movies added over two months
- **WHEN** a movie library has two movies of 10 GB and 5 GB added in March 2026 and one of 20 GB
  added in May 2026, and the report runs in May 2026 with `--growth-months 3`
- **THEN** its `growth.months` is March (2 added, 15 GB), April (0, 0 GB) and May (1, 20 GB), and
  its `growth` totals are 3 added and 35 GB

#### Scenario: Added before the period
- **WHEN** a movie was added three years ago and the report runs with the default 12 months
- **THEN** it is not counted in any `growth` row or total

#### Scenario: A show library
- **WHEN** ten episodes of one show were added this month
- **THEN** the library's current month has `added` of 10

#### Scenario: Combined across libraries
- **WHEN** a movie library added 2 movies and a TV library added 5 episodes in the same month
- **THEN** the top-level `growth` row for that month has `added` of 7 and the sum of both sizes

#### Scenario: No months asked for
- **WHEN** the script runs with `--growth-months 0`
- **THEN** each `growth` section has an empty `months` list and totals of 0

#### Scenario: No extra Plex requests for growth
- **WHEN** the report includes growth
- **THEN** it has used only the Plex paths it already requests for the rest of the report
