## MODIFIED Requirements

### Requirement: Options
The script SHALL accept `--library NAME` (repeatable, case-insensitive; error if nothing matches),
`--recent N` (recently added items per library, default 10, limited to 0–100), `--large-gb N`
(size at which a file counts as very large, default 40) and `--duplicate-examples N` (duplicate
examples listed per library and across libraries, default 15, limited to 0–500).

#### Scenario: Unknown library name
- **WHEN** `--library Cartoons` matches no library
- **THEN** the script stops with an error saying no library matched

#### Scenario: Asking for every duplicate
- **WHEN** the script runs with `--duplicate-examples 500`
- **THEN** each `duplicates` section and `cross_library_duplicates` lists up to 500 examples

#### Scenario: Out-of-range example count
- **WHEN** the script runs with `--duplicate-examples 9999`
- **THEN** it lists at most 500 examples per section

### Requirement: Report contents
The report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version, platform),
`totals` (libraries, files, size_gb), `cross_library_duplicates`, and one entry per library with
`name`, `type`, `counts`, `media`, `recently_added` and `housekeeping`. Per library type:
- movie: count of movies; media, housekeeping and `duplicates` over movies.
- show: counts of shows, seasons and episodes; media and `duplicates` over episodes; housekeeping
  over shows.
- artist (music): counts of artists, albums and tracks; media over tracks without video fields;
  recently added and housekeeping over albums; no `duplicates` section.
- photo: count of photos only.
- any other type: a note that it isn't summarized.

#### Scenario: Photo library
- **WHEN** a library is a photo library
- **THEN** its entry has only a photo count, with no media, recently added, housekeeping or
  duplicates sections

#### Scenario: Music library
- **WHEN** a library is a music library
- **THEN** its entry has no `duplicates` section

## ADDED Requirements

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
