# changes Specification

## Purpose

Say what changed on a Plex server since an earlier day. The script runs the library-report,
server-health and users-and-shares scripts, prints the "since the last snapshot" part each of them
works out, and saves, prunes, lists and deletes the snapshots they compare with (saved only when
this script or the dashboard runs, at most one per server per day). Script:
`skills/changes/scripts/changes.py`. How snapshots are chosen and read is in the conventions and
security specs; how Claude presents the result is in the skill's `SKILL.md`.
## Requirements
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

### Requirement: Trends
`changes.py trends --server-id ID` SHALL read that server's snapshot files dated within the last 90
days (today included) and print, oldest first. Without `--server-id` it SHALL use the server whose
folder has the most recent snapshot. It SHALL print:
- `server_id` (null when it isn't letters and digits) and `dates`: the date of every readable
  snapshot (see "Snapshots are read as data" in the security spec);
- `library`: `total_size_gb` (the sum of every library's `size_gb` that day) and `libraries`, one
  entry per library in the newest snapshot that has a `library` area, in that snapshot's order, each
  with `key`, `name` and `type` from that snapshot, `size_gb`, and `counts` holding one list per count
  name that library has in that snapshot;
- `sharing`: `people` (the number of entries in that day's sharing area), `home`, `managed` and
  `friend` (those entries by `kind`) and `pending` (those whose `status` is `pending`).

Every list SHALL have one value per date, lined up with `dates`. A value SHALL be `null` when that
day's snapshot has no such area, or has a library area without that library, or without that count.
Libraries SHALL be matched by key, so a renamed library keeps its earlier values. The output SHALL
contain no titles and no people's names. A server id that isn't letters and digits, or a server
with no readable snapshots, SHALL give empty `dates` and lists, not an error. The script SHALL make no
network requests and run no other script.

#### Scenario: A month of snapshots
- **WHEN** snapshots exist for 30 different days and `trends` runs with that server's id
- **THEN** `dates` has 30 dates, oldest first, and every library and sharing list has 30 values

#### Scenario: A day without the sharing area
- **WHEN** one day's snapshot has `library` and `health` but no `sharing`
- **THEN** that day's values in every `sharing` list are `null` and its library values are filled in

#### Scenario: A renamed library
- **WHEN** library key `3` was called "Films" in older snapshots and "Movies" in the newest
- **THEN** one library entry with key `3` and name "Movies" holds the values from every day

#### Scenario: A removed library
- **WHEN** a library is in older snapshots but not in the newest one
- **THEN** it has no entry in `libraries`, and its sizes still count toward the older days'
  `total_size_gb`

#### Scenario: Old and damaged files
- **WHEN** the folder has a snapshot dated 95 days ago and one that isn't valid JSON
- **THEN** neither date appears in `dates` and the command succeeds

#### Scenario: No names
- **WHEN** `trends` runs for a server shared with a friend called "Sam"
- **THEN** "Sam" appears nowhere in the output

#### Scenario: No server id given
- **WHEN** snapshots exist for two servers, the newest one for server `def456`, and `trends` runs
  without `--server-id`
- **THEN** it prints `def456`'s trends

#### Scenario: A strange server id
- **WHEN** `trends` runs with `--server-id ../x`
- **THEN** it prints empty `dates` and lists, exits 0, and reads nothing outside the snapshots folder

