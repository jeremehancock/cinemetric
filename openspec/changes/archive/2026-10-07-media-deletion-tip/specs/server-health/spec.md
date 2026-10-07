## MODIFIED Requirements

### Requirement: Only selected settings are kept
The script SHALL request `/:/prefs` at most once per report and keep only the settings listed below,
discarding everything else without printing it. A listed setting the server doesn't return SHALL be
left out rather than guessed. The server's public address SHALL be left out of the remote access
details. The same answer SHALL also give the top-level `media_deletion_allowed` field (see "Media
deletion setting" in the conventions spec); `allowMediaDeletion` SHALL NOT be added to either
settings list or to `worth_a_look`.

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
  `server.streaming_settings` contains only the six streaming settings, `media_deletion_allowed` is
  set from `allowMediaDeletion`, and no other setting's id or value appears anywhere in the report

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
- **THEN** `/:/prefs` is requested once, and it gives both settings parts and
  `media_deletion_allowed`

#### Scenario: Now playing only
- **WHEN** the script runs with `--now-playing`
- **THEN** `/:/prefs` isn't requested and the output has no `media_deletion_allowed` field
