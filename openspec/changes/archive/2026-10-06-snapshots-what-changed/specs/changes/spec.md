## ADDED Requirements

### Requirement: Built from the report scripts
The script `skills/changes/scripts/changes.py` SHALL get its data by running `library_report.py`,
`server_health.py` (with `--stuck-wait 0`) and `users_and_shares.py`, each with `--snapshot-items`
and, when given, `--since DAYS`, side by side. It SHALL never contact Plex, plex.tv or Tautulli
itself. A report that fails or runs longer than 30 minutes SHALL leave its area out, with the reason
in `sections_missing`. If every report fails, the script SHALL fail with the first error, keeping its
code (`NOT_CONFIGURED`, `OWNER_ONLY`).

#### Scenario: Connected to someone else's server
- **WHEN** `users_and_shares.py` fails with `OWNER_ONLY`
- **THEN** the library and server changes are still reported and saved, and `sections_missing` has a
  `sharing` entry

#### Scenario: Not set up
- **WHEN** every report fails with `NOT_CONFIGURED`
- **THEN** the script prints `error: NOT_CONFIGURED: ...` and exits 1, and no snapshot is saved

### Requirement: Report contents
The default run SHALL print `server` (name), `snapshot_saved` (the date saved, or null when nothing
could be saved), `library`, `health` and `sharing` (each that report's `since_snapshot`, or null when
the report failed) and `sections_missing`. It SHALL add nothing of its own: every comparison comes
from the reports.

#### Scenario: Normal run
- **WHEN** all three reports succeed and an earlier snapshot exists
- **THEN** `library`, `health` and `sharing` are the three `since_snapshot` sections and
  `snapshot_saved` is today's date

#### Scenario: First run
- **WHEN** no earlier snapshot exists
- **THEN** `library`, `health` and `sharing` are null, and `snapshot_saved` is today's date

### Requirement: Saving a snapshot
A snapshot SHALL be saved at `<data folder>/snapshots/<server id>/<YYYY-MM-DD>.json` (local date),
where `<server id>` is the `server_id` from the reports' `snapshot` blocks and contains only letters
and digits. The file SHALL hold `format` (1), `cinemetric_version`, `date`, `saved_at`, `server_name`
and the areas that were available: `library`, `health` and `sharing`, each copied from that report's
`snapshot` block. If blocks name different server ids, or no block is available, nothing SHALL be
saved. When today's file already exists, the new file SHALL keep that file's areas that this save
doesn't have and replace the rest. The file SHALL be written to a temporary file in the same folder
and renamed into place.

#### Scenario: Two saves on one day
- **WHEN** the morning save had all three areas and the evening save has only `library` and `health`
- **THEN** today's file has the evening's `library` and `health` and the morning's `sharing`

#### Scenario: A strange server id
- **WHEN** a `snapshot` block's `server_id` contains `/` or `..`
- **THEN** nothing is saved, `snapshot_saved` is null, and no file is created outside the snapshots
  folder

### Requirement: Keeping 90 days
After saving, the script SHALL delete snapshot files dated more than 90 days before today in every
server's folder. Only files named `YYYY-MM-DD.json` SHALL be deleted; anything else is left alone.

#### Scenario: An old snapshot
- **WHEN** a snapshot dated 91 days ago exists and a new one is saved
- **THEN** the 91-day-old file is deleted and one dated 90 days ago is kept

#### Scenario: Another file in the folder
- **WHEN** the folder also contains `notes.txt`
- **THEN** it is not deleted

### Requirement: Saving without fetching
`changes.py save` SHALL read one JSON object from stdin with any of the keys `library`, `health` and
`sharing`, each a report printed with `--snapshot-items`, and save their `snapshot` blocks as above.
It SHALL make no network requests and run no other script. It SHALL print `snapshot_saved`.
Input larger than 50 MB or not valid JSON SHALL be refused with an error.

#### Scenario: The dashboard saves
- **WHEN** the dashboard pipes its three reports to `changes.py save`
- **THEN** today's snapshot is saved and no network connection is opened

### Requirement: Listing and forgetting
`changes.py list` SHALL print, per server folder, the server name from its newest readable file, the
number of snapshots, and the oldest and newest dates. `changes.py forget` SHALL delete the whole
snapshots folder and print how many files were removed. Neither SHALL contact anything.

#### Scenario: Forgetting
- **WHEN** `changes.py forget` runs
- **THEN** the snapshots folder no longer exists and the dashboard's other files are untouched

### Requirement: Options
The default run SHALL accept `--since DAYS` (at least 1, at most 90), passed on to each report.

#### Scenario: What changed this week
- **WHEN** run with `--since 7`
- **THEN** each report is run with `--since 7`

#### Scenario: Out of range
- **WHEN** run with `--since 500`
- **THEN** 90 is used
