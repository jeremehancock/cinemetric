## MODIFIED Requirements

### Requirement: Options
The script SHALL accept `--stale-days N` (days without a library scan that count as overdue, default
7, at least 1), `--stuck-wait SECONDS` (how long to wait before checking running tasks a second
time, default 15, limited to 0–300; `0` turns the stuck task check off), `--since DAYS` (which
snapshot `since_snapshot` compares with, limited to 1–90; see "Reading snapshots" in the conventions
spec) and `--snapshot-items` (add the `snapshot` block).

#### Scenario: Custom threshold
- **WHEN** run with `--stale-days 14`
- **THEN** only libraries not scanned for more than 14 days count as overdue

#### Scenario: Stuck task check turned off
- **WHEN** run with `--stuck-wait 0` while a task is running
- **THEN** `/activities` is requested once, there is no wait, and every running task's
  `progress_moved` is `null`

#### Scenario: Out-of-range wait
- **WHEN** run with `--stuck-wait 9999`
- **THEN** the script waits at most 300 seconds

## ADDED Requirements

### Requirement: Server snapshot area
With `--snapshot-items`, the report SHALL include `snapshot`: `server_id` (the server's
`machineIdentifier` from `/`) and `area` with `version`, `update_version` (the available update's
version; `false` when Plex says there is no update; null when the update check failed) and
`remote_access` (the remote access state, or null when unknown). Without `--snapshot-items`,
`snapshot` SHALL NOT be in the output.

#### Scenario: Update available
- **WHEN** Plex 1.41.0 is installed and 1.41.1 is available
- **THEN** `snapshot.area` has `version` `1.41.0` and `update_version` `1.41.1`

### Requirement: Server changes since the last snapshot
The report SHALL include `since_snapshot`, comparing with the `health` area of the snapshot chosen as
in "Reading snapshots" (conventions spec), or `null` when there is none. It SHALL contain
`snapshot_date`, `days_ago` and `changes`, a list where each item has `kind` and `from` / `to`:
`version` (Plex was updated or downgraded), `update_version` (an update appeared, changed or went
away; `false` means no update was waiting) and `remote_access` (the state changed). A value that is
null on either side (unknown) SHALL NOT count as a change. No changes gives an empty list.

#### Scenario: Plex updated
- **WHEN** the snapshot has version `1.40.5` and the server now reports `1.41.0`
- **THEN** `changes` has `{"kind": "version", "from": "1.40.5", "to": "1.41.0"}`

#### Scenario: The waiting update was installed
- **WHEN** the snapshot has `update_version` `1.41.1` and Plex now says no update is waiting
- **THEN** `changes` has `{"kind": "update_version", "from": "1.41.1", "to": false}`

#### Scenario: Update check failed today
- **WHEN** the snapshot has `update_version` `1.41.1` and today's update check failed
- **THEN** `changes` has no `update_version` item
