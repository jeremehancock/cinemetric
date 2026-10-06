# server-health Specification

## Purpose

A read-only snapshot of how a Plex server is doing right now: version and updates, remote access, CPU
and memory, live streams, background tasks, library scans and maintenance. Script:
`skills/server-health/scripts/server_health.py`. How Claude presents it is in the skill's `SKILL.md`.
## Requirements
### Requirement: Plex paths used
The script SHALL request only `/`, `/updater/status`, `/myplex/account`, `/statistics/resources`,
`/status/sessions`, `/activities`, `/butler`, `/:/prefs` and `/library/sections`.

#### Scenario: Building the report
- **WHEN** the script builds a report
- **THEN** every request goes to one of those paths

### Requirement: Only selected settings are kept
The script SHALL request `/:/prefs` at most once per report and keep only the settings listed below,
discarding everything else without printing it. A listed setting the server doesn't return SHALL be
left out rather than guessed. The server's public address SHALL be left out of the remote access
details.

Kept in `background.maintenance_settings`:
- `ButlerStartHour` and `ButlerEndHour` as `maintenance_start_hour` and `maintenance_end_hour`
- `FSEventLibraryUpdatesEnabled` as `scan_on_folder_change`
- `ScheduledLibraryUpdatesEnabled` as `scheduled_scans_enabled`
- `ScheduledLibraryUpdateInterval` as `scheduled_scan_interval_seconds`
- `autoEmptyTrash` as `empty_trash_after_scan`

Kept in `server.streaming_settings`:
- `HardwareAcceleratedCodecs` as `hardware_acceleration`
- `HardwareAcceleratedEncoders` as `hardware_encoding`
- `TranscoderCanOnlyRemuxVideo` as `video_transcoding_disabled`
- `WanPerStreamMaxUploadRate` as `remote_stream_limit_kbps` (`0` means no limit)
- `WanTotalMaxUploadRate` as `remote_total_upload_limit_kbps` (`0` means no limit)
- `TranscoderTempDirectory` as `custom_transcoder_temp_folder`: `true` when it has a value, `false`
  when empty. The folder path itself SHALL NOT appear in the report.

On/off settings SHALL be booleans and hour, second and kbps settings SHALL be integers.

#### Scenario: Reading server settings
- **WHEN** `/:/prefs` returns all of the server's settings
- **THEN** `background.maintenance_settings` contains only the six maintenance settings,
  `server.streaming_settings` contains only the six streaming settings, and no other setting's id or
  value appears anywhere in the report

#### Scenario: Custom transcoder folder
- **WHEN** `TranscoderTempDirectory` is set to `/mnt/fast/transcode`
- **THEN** `custom_transcoder_temp_folder` is `true` and `/mnt/fast/transcode` doesn't appear in the
  report

#### Scenario: Setting missing on this server
- **WHEN** `/:/prefs` has no `HardwareAcceleratedCodecs` setting
- **THEN** `server.streaming_settings` has no `hardware_acceleration` key and nothing about hardware
  transcoding is flagged

#### Scenario: One request for both parts
- **WHEN** the script builds a report
- **THEN** `/:/prefs` is requested once

### Requirement: Partial results instead of failure
Only `/` is required. Every other part (update check, remote access, CPU and memory, streaming
settings, live activity, running tasks, stuck task check, library scans, maintenance tasks,
maintenance settings) SHALL be optional: if it fails, the part is `null` (or, for the stuck task
check, each `progress_moved` is `null`) and listed in `unavailable` with a reason. A 401 or 403 on an
optional part SHALL be reported as "only available to the server owner's account", since the token
already worked for `/`. When `/:/prefs` fails, both streaming settings and maintenance settings SHALL
be `null` and listed in `unavailable` with the same reason.

#### Scenario: Connected to a shared server
- **WHEN** the user isn't the server owner and `/updater/status` returns 403
- **THEN** `server.update` is `null` and `unavailable` lists "update check" as only available to the
  server owner's account

#### Scenario: Second task check fails
- **WHEN** the first `/activities` request works but the second one fails
- **THEN** `running_now` still lists the tasks from the first check, each `progress_moved` is `null`,
  nothing is flagged as `task_not_progressing`, and `unavailable` lists "stuck task check" with the
  reason

#### Scenario: Settings unavailable
- **WHEN** `/:/prefs` returns 403
- **THEN** `server.streaming_settings` and `background.maintenance_settings` are `null`, `unavailable`
  lists "streaming settings" and "maintenance settings" as only available to the server owner's
  account, `/:/prefs` was requested once, and the rest of the report is present

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

### Requirement: Live streams
For each stream, the report SHALL give the user, title, type, player, platform, state, whether it's
Live TV, progress, source quality, bandwidth, LAN/WAN location and playback method: "direct play" (no
transcode session), "transcode" (video or audio is transcoded) or "direct stream" (anything else).
Transcodes SHALL also include the video and audio decisions, hardware use, speed and whether they're
throttled. Totals SHALL count streams by method and add up bandwidth overall and by LAN/WAN.

#### Scenario: Nothing playing
- **WHEN** no one is streaming
- **THEN** `live_activity.streams` is empty and the totals are zero

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
- `hardware_transcoding_off`: `hardware_acceleration` is `false`.
- `video_transcoding_off`: `video_transcoding_disabled` is `true`.
- `remote_stream_limit_low`: `remote_stream_limit_kbps` is above 0 and below 8000 (the lowest choice
  Plex labels as 1080p). The item includes `limit_kbps`.

When only folder-change scanning is on, an old last-scanned date SHALL NOT be flagged, because those
small scans don't update it. A setting that is missing from `streaming_settings` SHALL NOT be flagged.

#### Scenario: Only folder-change scanning
- **WHEN** scheduled scans are off, scanning on folder change is on, and a library was last scanned a
  month ago
- **THEN** nothing about scans is flagged

#### Scenario: A task that isn't moving
- **WHEN** a library scan is at 40% in both checks, with the same detail text
- **THEN** `worth_a_look` has one `task_not_progressing` item listing that scan at 40% and
  `seconds_between_checks` of 15

#### Scenario: Hardware acceleration off
- **WHEN** `HardwareAcceleratedCodecs` is off
- **THEN** `worth_a_look` has a `hardware_transcoding_off` item

#### Scenario: Video transcoding turned off
- **WHEN** `TranscoderCanOnlyRemuxVideo` is on
- **THEN** `worth_a_look` has a `video_transcoding_off` item

#### Scenario: Low remote limit
- **WHEN** `WanPerStreamMaxUploadRate` is 4000
- **THEN** `worth_a_look` has a `remote_stream_limit_low` item with `limit_kbps` of 4000

#### Scenario: 1080p remote limit or no limit
- **WHEN** `WanPerStreamMaxUploadRate` is 8000, or is 0
- **THEN** nothing about the remote limit is flagged

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

