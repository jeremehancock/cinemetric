## MODIFIED Requirements

### Requirement: Options
The script SHALL accept `--library NAME` (repeatable, case-insensitive; error if nothing matches),
`--recent N` (recently added items per library, default 10, limited to 0–100), `--large-gb N`
(size at which a file counts as very large, default 40), `--duplicate-examples N` (duplicate
examples listed per library and across libraries, default 15, limited to 0–500) and
`--upgrade-examples N` (upgrade examples listed per library, default 15, limited to 0–500).

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

### Requirement: Report contents
The report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version, platform),
`totals` (libraries, files, size_gb), `cross_library_duplicates`, and one entry per library with
`name`, `type`, `counts`, `media`, `recently_added` and `housekeeping`. Per library type:
- movie: count of movies; media, housekeeping, `duplicates` and `upgrades` over movies.
- show: counts of shows, seasons and episodes; media, `duplicates` and `upgrades` over episodes;
  housekeeping over shows.
- artist (music): counts of artists, albums and tracks; media over tracks without video fields;
  recently added and housekeeping over albums; no `duplicates` or `upgrades` section.
- photo: count of photos only.
- any other type: a note that it isn't summarized.

#### Scenario: Photo library
- **WHEN** a library is a photo library
- **THEN** its entry has only a photo count, with no media, recently added, housekeeping,
  duplicates or upgrades sections

#### Scenario: Music library
- **WHEN** a library is a music library
- **THEN** its entry has no `duplicates` or `upgrades` section

## ADDED Requirements

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
