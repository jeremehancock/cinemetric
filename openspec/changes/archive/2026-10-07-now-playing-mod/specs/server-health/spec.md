## MODIFIED Requirements

### Requirement: Options
The script SHALL accept `--stale-days N` (days without a library scan that count as overdue, default
7, at least 1), `--stuck-wait SECONDS` (how long to wait before checking running tasks a second
time, default 15, limited to 0–300; `0` turns the stuck task check off), `--since DAYS` (which
snapshot `since_snapshot` compares with, limited to 1–90; see "Reading snapshots" in the conventions
spec), `--snapshot-items` (add the `snapshot` block) and `--now-playing` (see "Now playing only").

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

### Requirement: Now playing only
With `--now-playing`, the script SHALL request only `/status/sessions` and print a JSON object with
`cinemetric_version`, `checked_at` (seconds since the epoch) and `live_activity`, built exactly as in
the full report (see "Live streams"). It SHALL read no snapshots, save nothing and ignore the other
options. When `/status/sessions` fails, the script SHALL exit with an error the same way it does for
a failed connection, since there is nothing else to report. It is used by the Now Playing mod (see the
`now-playing-pane` spec).

#### Scenario: One stream
- **WHEN** run with `--now-playing` while one person is watching
- **THEN** the only Plex request is `/status/sessions`, and the output has that stream under
  `live_activity.streams` and nothing about updates, tasks or snapshots

#### Scenario: Server unreachable
- **WHEN** run with `--now-playing` and the server can't be reached
- **THEN** the script prints an error starting `error:` to stderr and exits with a non-zero code
