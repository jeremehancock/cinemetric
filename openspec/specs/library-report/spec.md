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

### Requirement: Duplicates within a library
A copy SHALL be one of an item's media versions (a `Media` entry). A copy SHALL NOT be counted if
it has a `deletedAt` value (Plex can't find it) or a `proxyType` value (a Plex optimized version).
A copy's size SHALL be the total size of its parts, so a movie split across several files is one
copy. An item with two or more counted copies is a duplicate; its extra space SHALL be the total
size of all its copies except the largest one.

Each movie and show library's `duplicates` section SHALL contain `titles` (items with two or more
copies), `extra_copies` (copies beyond the first, summed over those items), `extra_gb` and
`examples`, ordered by extra space, largest first, up to the `--duplicate-examples` limit:
- movie: one example per movie with `title` (as in other movie labels), `extra_gb` and `copies`,
  each copy giving `resolution` (same buckets as the media breakdown), `video_codec` and `gb`.
- show: one example per show with `title` (the show), `episodes` (duplicated episodes in it) and
  `extra_gb`.

#### Scenario: Two versions of a movie
- **WHEN** a movie has a 4K copy of 60 GB and a 1080p copy of 12 GB
- **THEN** it counts as one title with one extra copy and 12 GB of extra space, and its example
  lists both copies

#### Scenario: A movie split into two files
- **WHEN** a movie has one `Media` entry with two parts
- **THEN** it is not a duplicate

#### Scenario: A copy Plex can't find
- **WHEN** a movie has two `Media` entries and one has a `deletedAt` value
- **THEN** it is not a duplicate (the missing file is reported only as unavailable)

#### Scenario: Optimized version
- **WHEN** a movie has its original copy plus a `Media` entry with a `proxyType` value
- **THEN** it is not a duplicate

#### Scenario: A duplicated season
- **WHEN** ten episodes of one show each have two copies
- **THEN** the library's `titles` counts ten, and the examples list that show once with
  `episodes` of 10

### Requirement: Duplicates across libraries
The script SHALL find movies, and episodes, whose `guid` appears in more than one of the libraries
being reported (only those chosen with `--library`, when given). Items with no `guid` or a
`local://` one SHALL be skipped. Each library's copy SHALL be that item's largest counted copy, so
extra copies inside a single library are not counted twice. The extra space SHALL be the total of
the libraries' copies except the largest one.

`cross_library_duplicates` SHALL contain `titles`, `extra_gb` and `examples` (largest extra space
first, up to the `--duplicate-examples` limit). A movie example SHALL give `title`, `extra_gb` and
`libraries`, each with `library`, `resolution` and `gb`. Episodes SHALL be grouped by show and
library set into one example with `title` (the show), `episodes`, `extra_gb` and `libraries` (the
library names).

#### Scenario: Same movie in two libraries
- **WHEN** a movie with guid `plex://movie/abc` is in "Movies" at 10 GB and in "4K Movies" at 55 GB
- **THEN** `cross_library_duplicates` counts it once with 10 GB of extra space, listing both
  libraries

#### Scenario: Unmatched items aren't compared
- **WHEN** two libraries each contain an item whose guid starts with `local://`
- **THEN** neither is counted as a cross-library duplicate

#### Scenario: Limited to one library
- **WHEN** the script runs with `--library Movies` only
- **THEN** `cross_library_duplicates` has `titles` of 0 and no examples

#### Scenario: No extra Plex requests
- **WHEN** the report finds duplicates
- **THEN** it has used only the Plex paths it already requests for the rest of the report

### Requirement: Upgrade candidates
Copies SHALL be counted as in "Duplicates within a library" (no `deletedAt`, no `proxyType`). An
item's best resolution SHALL be the highest resolution among its counted copies, ranked SD, 720p,
1080p, 2K, 4K. An item SHALL be an upgrade candidate when its best resolution is SD or 720p. Items
with no counted copies, or whose copies' resolutions are all unknown or unrecognised, SHALL NOT be
candidates.

An otherwise-candidate item SHALL NOT be listed when an item with the same `guid` in another library
being reported (only those chosen with `--library`, when given) has a counted copy at 1080p or
better; it SHALL instead be counted in `covered_elsewhere`. Items with no `guid` or a `local://` one
are never covered elsewhere.

Each movie and show library's `upgrades` section SHALL contain `titles` (candidates),
`by_resolution` (candidates per best resolution, keys `SD` and `720p`), `covered_elsewhere` and
`examples`, up to the `--upgrade-examples` limit:
- movie: one example per movie with `title` (as in other movie labels), `resolution` (its best),
  `video_codec` and `gb` of that best copy (the largest, if several share it). Ordered SD before
  720p, then by title.
- show: one example per show with `title` (the show), `episodes` (candidate episodes in it) and
  `by_resolution`. Ordered by `episodes`, most first, then by title.

#### Scenario: An old SD movie
- **WHEN** a movie's only copy is 480p, 1.4 GB, codec mpeg4
- **THEN** it is counted in `titles` and `by_resolution.SD`, and its example gives resolution SD,
  codec mpeg4 and 1.4 GB

#### Scenario: Already have a better copy in the same library
- **WHEN** a movie has a 720p copy and a 1080p copy
- **THEN** it is not an upgrade candidate

#### Scenario: Better copy only as an optimized version
- **WHEN** a movie has a 720p original and a 1080p `Media` entry with a `proxyType` value
- **THEN** it is an upgrade candidate at 720p

#### Scenario: Better copy in another library
- **WHEN** a 720p movie with guid `plex://movie/abc` is in "Movies" and the same guid is in
  "4K Movies" at 4K
- **THEN** "Movies" does not list it, and its `upgrades.covered_elsewhere` is 1

#### Scenario: Other library not being reported
- **WHEN** the script runs with `--library Movies` only and a 720p movie there is in 4K in
  "4K Movies"
- **THEN** "Movies" lists it as an upgrade candidate

#### Scenario: Unknown resolution
- **WHEN** a movie's only copy has no `videoResolution`
- **THEN** it is not an upgrade candidate

#### Scenario: A 720p series
- **WHEN** a show has 30 episodes whose only copies are 720p and 2 that are SD
- **THEN** the library's `titles` counts 32, and the examples list that show once with `episodes`
  of 32 and `by_resolution` of 2 SD and 30 720p

#### Scenario: No extra Plex requests for upgrades
- **WHEN** the report finds upgrade candidates
- **THEN** it has used only the Plex paths it already requests for the rest of the report

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

