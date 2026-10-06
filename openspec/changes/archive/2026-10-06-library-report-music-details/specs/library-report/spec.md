## MODIFIED Requirements

### Requirement: Options
The script SHALL accept `--library NAME` (repeatable, case-insensitive; error if nothing matches),
`--recent N` (recently added items per library, default 10, limited to 0–100), `--large-gb N`
(size at which a file counts as very large, default 40), `--duplicate-examples N` (duplicate
examples listed per library and across libraries, default 15, limited to 0–500),
`--upgrade-examples N` (upgrade examples listed per library, default 15, limited to 0–500),
`--growth-months N` (months covered by each `growth` section, default 12, limited to 0–120) and
`--music-examples N` (mixed and lossy album examples listed per music library, default 15, limited
to 0–500).

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

## ADDED Requirements

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
