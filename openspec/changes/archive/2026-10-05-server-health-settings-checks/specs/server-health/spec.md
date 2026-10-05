## RENAMED Requirements

- FROM: `### Requirement: Only maintenance settings are kept`
- TO: `### Requirement: Only selected settings are kept`

## MODIFIED Requirements

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
