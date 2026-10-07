# library-report Specification

## Purpose

A read-only summary of what's in a Plex server's libraries: counts, storage, video quality and codecs,
recent additions and housekeeping problems. Script: `skills/library-report/scripts/library_report.py`.
How Claude presents it is in the skill's `SKILL.md`.
## Requirements
### Requirement: Plex paths used
The script SHALL request only `/`, `/library/sections`, `/library/sections/{id}/all` and `/:/prefs`,
reading items in pages of 500. `/:/prefs` SHALL be read only for the media deletion setting (see "Media deletion setting" in the conventions spec).

#### Scenario: Large library
- **WHEN** a library has more than 500 items of a type
- **THEN** the script fetches them page by page until it has them all

### Requirement: Options
The script SHALL accept `--library NAME` (repeatable, case-insensitive; error if nothing matches),
`--recent N` (recently added items per library, default 10, limited to 0–100), `--large-gb N`
(size at which a file counts as very large, default 40), `--duplicate-examples N` (duplicate
examples listed per library and across libraries, default 15, limited to 0–500),
`--upgrade-examples N` (upgrade examples listed per library, default 15, limited to 0–500),
`--growth-months N` (months covered by each `growth` section, default 12, limited to 0–120),
`--music-examples N` (mixed and lossy album examples listed per music library, default 15, limited
to 0–500), `--since DAYS` (which snapshot `since_snapshot` compares with, limited to 1–90; see
"Reading snapshots" in the conventions spec) and `--snapshot-items` (add the `snapshot` block).
`--snapshot-items` together with `--library` SHALL be refused with an error, because a snapshot must
cover every library.

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

#### Scenario: Asking for every lossy album
- **WHEN** the script runs with `--music-examples 500`
- **THEN** each `audio_quality` section lists up to 500 mixed and up to 500 lossy album examples

#### Scenario: Out-of-range music example count
- **WHEN** the script runs with `--music-examples -1`
- **THEN** each `audio_quality` section lists no examples but still gives its counts

#### Scenario: Snapshot of some libraries only
- **WHEN** the script runs with `--snapshot-items --library Movies`
- **THEN** it stops with an error and makes no request

### Requirement: Report contents
The report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version, platform),
`totals` (libraries, files, size_gb), `growth` (all reported libraries combined),
`cross_library_duplicates`, and one entry per library with `name`, `type`, `counts`, `media`,
`recently_added`, `growth` and `housekeeping`. Per library type:
- movie: count of movies; media, housekeeping, `duplicates` and `upgrades` over movies; growth over
  movies.
- show: counts of shows, seasons and episodes; media, `duplicates`, `upgrades` and growth over
  episodes; housekeeping over shows.
- artist (music): counts of artists, albums and tracks; media, growth and `audio_quality` over
  tracks, with media having no video fields; recently added over albums; housekeeping over albums
  plus missing artist photos; no `duplicates` or `upgrades` section. Artists SHALL be read from the
  artist listing (`/library/sections/{id}/all` with `type=8`), and the artist count SHALL be the
  number of artists in it.
- photo: count of photos only.
- any other type: a note that it isn't summarized.

#### Scenario: Photo library
- **WHEN** a library is a photo library
- **THEN** its entry has only a photo count, with no media, recently added, growth, housekeeping,
  duplicates, upgrades or audio quality sections

#### Scenario: Music library
- **WHEN** a library is a music library
- **THEN** its entry has `growth` and `audio_quality` sections counted over tracks, and no
  `duplicates` or `upgrades` section

#### Scenario: Movie library
- **WHEN** a library is a movie library
- **THEN** its entry has no `audio_quality` section

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
`local://` one), each with up to 15 examples. For a music library, where the items are albums, it
SHALL also give `missing_artist_image_count` (artists with no `thumb`) and
`missing_artist_image_examples` (up to 15 artist names).

#### Scenario: Unmatched movie
- **WHEN** a movie's `guid` starts with `local://`
- **THEN** it is counted in `unmatched_count`

#### Scenario: Album with no cover art
- **WHEN** an album in a music library has no `thumb`
- **THEN** it is counted in `missing_poster_count` and listed as "Artist - Album" in
  `missing_poster_examples`

#### Scenario: Artist with no photo
- **WHEN** an artist in a music library has no `thumb`
- **THEN** it is counted in `missing_artist_image_count` and its name is listed in
  `missing_artist_image_examples`

#### Scenario: Movie library housekeeping
- **WHEN** a library is a movie library
- **THEN** its `housekeeping` has no artist fields

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

### Requirement: Music audio quality
A track's copies SHALL be counted as in "Duplicates within a library" (no `deletedAt`, no
`proxyType`). Each copy SHALL be grouped by its `audioCodec`, compared without regard to case:
- lossless: `flac`, `alac`, `pcm`, `aiff`, `ape`, `wavpack`, `tta`, `mlp`, `truehd`, and any codec
  starting with `dsd`
- lossy: `mp3`, `mp2`, `aac`, `vorbis`, `opus`, `wma`, `wmav1`, `wmav2`, `wmapro`, `ac3`, `eac3`,
  `dca`, `dts`, `musepack`
- other: any other value, or none.

A track SHALL be lossless if any of its counted copies is lossless, otherwise lossy if any is
lossy, otherwise other. Tracks with no counted copies SHALL NOT be counted. A track's size SHALL be
the total size of every part of its counted copies.

A lossy track's bitrate SHALL be the highest `bitrate` (in kbps) among its lossy counted copies, and
SHALL be put in one of `under_192`, `192_to_255`, `256_and_up`, or `unknown` when no lossy copy has
a bitrate above zero.

Tracks SHALL be grouped into albums by `parentRatingKey`. An album SHALL be `mixed` when it has at
least one lossless and at least one lossy track, `lossless` when it has lossless tracks and no lossy
ones, and `lossy` when it has lossy tracks and no lossless ones. Albums whose tracks are all other
SHALL NOT be counted in any album group. An album's label SHALL be "Artist - Album" from its tracks'
`grandparentTitle` and `parentTitle`.

Each music library's `audio_quality` section SHALL contain:
- `lossless`, `lossy` and `other`, each with `tracks` and `gb`
- `lossy_bitrate`: lossy track counts with keys `under_192`, `192_to_255`, `256_and_up` and
  `unknown`
- `albums`: album counts with keys `lossless`, `lossy` and `mixed`
- `mixed_examples`: one per mixed album with `title`, `lossless_tracks` and `lossy_tracks`, ordered
  by `lossy_tracks`, most first, then by title
- `lossy_examples`: one per lossy album with `title`, `tracks` (its lossy tracks), `codec` (the
  lossy codec most of those tracks use, lowercase) and `kbps` (the average of those tracks' known
  bitrates, rounded to a whole number, or null when none is known), ordered by `kbps`, lowest first
  with unknown last, then by title.

Both example lists SHALL be limited to `--music-examples`.

Audio quality SHALL use only the track listing the script already requests for the rest of the
report.

#### Scenario: A FLAC and MP3 collection
- **WHEN** a music library has 8 FLAC tracks of 30 MB and 4 MP3 tracks of 8 MB at 320 kbps
- **THEN** `lossless` is 8 tracks and 0.2 GB, `lossy` is 4 tracks and 0.0 GB, and
  `lossy_bitrate.256_and_up` is 4

#### Scenario: Codec names in capitals
- **WHEN** a track's `audioCodec` is `FLAC`
- **THEN** it is counted as lossless

#### Scenario: Unrecognised codec
- **WHEN** a track's `audioCodec` is `xyz` or missing
- **THEN** it is counted in `other` and not in `lossless` or `lossy`

#### Scenario: A track in two formats
- **WHEN** a track has one MP3 copy and one FLAC copy
- **THEN** it counts as one lossless track whose size is both copies together

#### Scenario: A copy Plex can't find
- **WHEN** a track's only copy has a `deletedAt` value
- **THEN** it is not counted in `audio_quality`

#### Scenario: Low bitrate MP3s
- **WHEN** a track's only copy is an MP3 at 128 kbps
- **THEN** it is counted in `lossy_bitrate.under_192`

#### Scenario: Bitrate not known
- **WHEN** a lossy track's copies have no `bitrate`
- **THEN** it is counted in `lossy_bitrate.unknown`

#### Scenario: An album with a few MP3s
- **WHEN** an album has 10 FLAC tracks and 2 MP3 tracks
- **THEN** it counts in `albums.mixed`, and its `mixed_examples` entry has `lossless_tracks` of 10
  and `lossy_tracks` of 2

#### Scenario: An all-MP3 album
- **WHEN** an album's 12 tracks are all MP3, six at 128 kbps and six at 192 kbps
- **THEN** it counts in `albums.lossy`, and its `lossy_examples` entry has `tracks` of 12, `codec`
  of `mp3` and `kbps` of 160

#### Scenario: Lowest bitrate first
- **WHEN** one lossy album averages 256 kbps and another 128 kbps
- **THEN** the 128 kbps album is listed first in `lossy_examples`

#### Scenario: Empty music library
- **WHEN** a music library has no tracks
- **THEN** its `audio_quality` has zero counts and empty example lists

#### Scenario: No extra Plex requests for audio quality
- **WHEN** the report includes audio quality
- **THEN** it has used only the Plex paths it already requests for the rest of the report

### Requirement: Library snapshot area
With `--snapshot-items`, the report SHALL include `snapshot`: `server_id` (the server's
`machineIdentifier` from `/`) and `area`, which has one entry per library keyed by Plex's library key,
each with `name`, `type`, `counts` and `size_gb` (as in the report), plus:
- `items`: `{ratingKey: label}` for every movie (movie libraries), show (TV libraries) or album
  (music libraries), using the same labels as the rest of the report (show labels are the show title);
- `episodes`: for TV libraries, `{show ratingKey: number of episodes}`;
- `unavailable`: `{ratingKey: label}` of every item with a file Plex marks unavailable (episodes for
  TV libraries, tracks for music libraries).

Without `--snapshot-items`, `snapshot` SHALL NOT be in the output.

#### Scenario: A movie library
- **WHEN** the script runs with `--snapshot-items` on a library with 3 movies, one of them unavailable
- **THEN** that library's `items` has 3 entries and `unavailable` has 1

#### Scenario: A normal run
- **WHEN** the script runs without `--snapshot-items`
- **THEN** the output has no `snapshot` key

### Requirement: Library changes since the last snapshot
The report SHALL include `since_snapshot`, comparing the libraries it read with the `library` area of
the snapshot chosen as in "Reading snapshots" (conventions spec), or `null` when there is none. It
SHALL contain `snapshot_date`, `days_ago`, `libraries` and `totals`. Each entry in `libraries` SHALL
have `name`, `type` and `status`:
- `new` (key not in the snapshot) or `removed` (key not in this run, only when the run covered every
  library): with `counts` and `size_gb` only;
- otherwise `same`, plus `renamed_from` when the name differs, and: `counts_change` and
  `size_gb_change` (new minus old), `added` and `removed` (titles whose `ratingKey` appeared or
  disappeared), for TV libraries `episodes_added` and `episodes_removed` (shows whose episode count
  went up or down, with the difference; a new show counts all its episodes as added),
  `became_unavailable` (in `unavailable` now, not before) and `available_again` (in `unavailable`
  before, not now, and the item still exists).

Each list SHALL have a `_count` with the full number and at most 25 named examples, sorted by name.
For `episodes_added` and `episodes_removed`, each example is `{show, count}` and `_count` is the
number of episodes.
Libraries with no change SHALL still be listed with `status` `same` and zero counts. `totals` SHALL
add up `added`, `removed`, `episodes_added`, `episodes_removed`, `became_unavailable`,
`available_again` and `size_gb_change` across libraries. With `--library`, only the chosen libraries
SHALL be compared and none counts as removed.

#### Scenario: Movies added and removed
- **WHEN** the snapshot's Movies library has keys 1, 2, 3 and this run has 2, 3, 4
- **THEN** Movies has `added_count` 1 naming movie 4 and `removed_count` 1 naming movie 1

#### Scenario: New episodes
- **WHEN** a show had 8 episodes in the snapshot and has 10 now
- **THEN** `episodes_added` lists that show with 2

#### Scenario: A drive went offline
- **WHEN** 300 episodes are unavailable now and none were in the snapshot
- **THEN** `became_unavailable_count` is 300 and 25 are named

#### Scenario: No snapshot yet
- **WHEN** no usable snapshot exists for this server
- **THEN** `since_snapshot` is `null` and the rest of the report is unchanged

