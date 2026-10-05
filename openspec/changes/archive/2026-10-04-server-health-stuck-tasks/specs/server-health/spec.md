## MODIFIED Requirements

### Requirement: Options
The script SHALL accept `--stale-days N` (days without a library scan that count as overdue, default
7, at least 1) and `--stuck-wait SECONDS` (how long to wait before checking running tasks a second
time, default 15, limited to 0–300; `0` turns the stuck task check off).

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

### Requirement: Partial results instead of failure
Only `/` is required. Every other part (update check, remote access, CPU and memory, live activity,
running tasks, stuck task check, library scans, maintenance tasks, maintenance settings) SHALL be
optional: if it fails, the part is `null` (or, for the stuck task check, each `progress_moved` is
`null`) and listed in `unavailable` with a reason. A 401 or 403 on an optional part SHALL be reported
as "only available to the server owner's account", since the token already worked for `/`.

#### Scenario: Connected to a shared server
- **WHEN** the user isn't the server owner and `/updater/status` returns 403
- **THEN** `server.update` is `null` and `unavailable` lists "update check" as only available to the
  server owner's account

#### Scenario: Second task check fails
- **WHEN** the first `/activities` request works but the second one fails
- **THEN** `running_now` still lists the tasks from the first check, each `progress_moved` is `null`,
  nothing is flagged as `task_not_progressing`, and `unavailable` lists "stuck task check" with the
  reason

### Requirement: Things worth a look
The script SHALL flag facts for Claude to explain in `worth_a_look`, each with a `kind`:
- `update_available`: Plex reports a newer release.
- `remote_access_not_working`: remote access state is anything other than `mapped`.
- `transcode_too_slow`: a transcode is not throttled and runs below 1x speed.
- `scheduled_scans_not_running`: scheduled scans are on and a library, not scanning now, hasn't been
  scanned for more than `--stale-days` days.
- `automatic_scans_off`: both scheduled scans and scanning on folder change are off.
- `important_maintenance_disabled`: database backup, database optimization, old bundle cleanup or old
  cache cleanup is off.
- `high_cpu` (average host CPU ≥ 85%) and `high_memory` (average host memory ≥ 90%).
- `task_not_progressing`: one or more running tasks have `progress_moved` set to `false`. The item
  lists each such task's title and progress, and `seconds_between_checks`.

When only folder-change scanning is on, an old last-scanned date SHALL NOT be flagged, because those
small scans don't update it.

#### Scenario: Only folder-change scanning
- **WHEN** scheduled scans are off, scanning on folder change is on, and a library was last scanned a
  month ago
- **THEN** nothing about scans is flagged

#### Scenario: A task that isn't moving
- **WHEN** a library scan is at 40% in both checks, with the same detail text
- **THEN** `worth_a_look` has one `task_not_progressing` item listing that scan at 40% and
  `seconds_between_checks` of 15

## ADDED Requirements

### Requirement: Checking whether running tasks are moving
A task SHALL be watched if it has a progress value and its type doesn't start with
`provider.subscription.` or `grabber.` (DVR and Live TV tasks, which follow a recording in real time
and normally sit still while it runs). If the first `/activities` request lists at least one watched
task and `--stuck-wait` is above 0, the script SHALL wait that many seconds and request `/activities`
once more. It SHALL NOT wait when no watched task is running. Tasks SHALL be matched between the
two checks by their `uuid`, or by type and title when a task has no `uuid`. Each task in
`running_now` SHALL get `progress_moved`:
- `true` if it is in both checks and its progress or its detail text (`subtitle`) changed;
- `false` if it is in both checks and both its progress and detail text are the same;
- `null` if it isn't watched, finished before the second check, can't be matched to exactly
  one task (two tasks share the same match key), or there was no second check.

Tasks that appear only in the second check SHALL be ignored. The script SHALL NOT describe any task as
failed; it only reports whether progress was seen.

#### Scenario: Nothing running
- **WHEN** the first `/activities` request returns no tasks
- **THEN** the script doesn't wait, requests `/activities` only once, and `running_now` is empty

#### Scenario: Only DVR tasks running
- **WHEN** the only running tasks are a Live TV recording (`grabber.grab`) and DVR subscription
  refreshes (`provider.subscription.refresh`) that sit at 50%
- **THEN** the script doesn't wait, each task's `progress_moved` is `null`, and nothing is flagged

#### Scenario: A task that is moving
- **WHEN** a scan is at 40% in the first check and 55% in the second
- **THEN** its `progress_moved` is `true` and nothing is flagged

#### Scenario: Same progress, different item
- **WHEN** a scan is at 40% in both checks but its detail text changed from "Arrival" to "Blade Runner"
- **THEN** its `progress_moved` is `true`

#### Scenario: A task finishes during the wait
- **WHEN** a task is in the first check but not the second
- **THEN** its `progress_moved` is `null` and it is not flagged
