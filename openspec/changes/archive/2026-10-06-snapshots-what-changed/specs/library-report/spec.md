## MODIFIED Requirements

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

## ADDED Requirements

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
