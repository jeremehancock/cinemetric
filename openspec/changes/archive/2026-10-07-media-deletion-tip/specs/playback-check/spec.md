## MODIFIED Requirements

### Requirement: Sources used
The script `skills/playback-check/scripts/playback_check.py` SHALL request only `/`,
`/library/sections`, `/library/sections/{id}/all`, `/library/metadata/{ids}` and `/:/prefs` from the
user's Plex server, reading library items in pages of 500. `{ids}` SHALL be 1 to 100 numeric rating
keys separated by commas, and any other form SHALL be refused by the path allowlist. From `/:/prefs`
the script SHALL read only `WanPerStreamMaxUploadRate` and `allowMediaDeletion` (see "Media deletion
setting" in the conventions spec), requesting it at most once per run; no other setting SHALL appear
in its output.

When Tautulli is set up, the script SHALL run only the Tautulli commands `get_tautulli_info`,
`get_history` and `get_stream_data`. It SHALL NOT contact plex.tv or any other address.

#### Scenario: Building a report
- **WHEN** the script builds a report with Tautulli set up
- **THEN** every request goes to the configured Plex server (one of the five allowed paths, with
  `GET`) or to the configured Tautulli address (one of the three allowed commands)

#### Scenario: Asking for too many titles at once
- **WHEN** the script tries to request `/library/metadata/` with 101 rating keys
- **THEN** it stops with the blocked request error and nothing is sent

#### Scenario: Tautulli isn't set up
- **WHEN** only Plex is configured
- **THEN** the script makes no Tautulli request and the report is still built

### Requirement: Bitrate above the limit
The bitrate limit SHALL be `--max-bitrate KBPS` when given, otherwise the server's
`WanPerStreamMaxUploadRate` when it is above 0. A file SHALL have the cause `over_bitrate_limit` when
its media version's `bitrate` is above the limit. When there is no limit (the server's value is 0 or
missing and no `--max-bitrate` is given), the check SHALL be skipped, `bitrate_limit` SHALL be `null`
and no file SHALL have this cause. When `--max-bitrate` is given, the server's
`WanPerStreamMaxUploadRate` SHALL be ignored, though `/:/prefs` is still requested once for the media
deletion setting.
If the server's setting can't be read (for example with an account that isn't the server owner's),
the check SHALL be skipped the same way and `bitrate_limit_problem` SHALL give the reason; the rest of
the report SHALL still be built.

#### Scenario: The setting can't be read
- **WHEN** `/:/prefs` answers with HTTP 401 and no `--max-bitrate` is given
- **THEN** `bitrate_limit` is `null`, `bitrate_limit_problem` explains why, and the script exits 0

#### Scenario: The server has a 12 Mbps remote limit
- **WHEN** `WanPerStreamMaxUploadRate` is 12000 and a file's bitrate is 18000
- **THEN** the file has the cause `over_bitrate_limit` and `bitrate_limit` is
  `{"kbps": 12000, "source": "server"}`

#### Scenario: No limit set
- **WHEN** `WanPerStreamMaxUploadRate` is 0 and no `--max-bitrate` is given
- **THEN** `bitrate_limit` is `null` and no file has the cause `over_bitrate_limit`

#### Scenario: A limit chosen by the user
- **WHEN** the server has no limit and the script is run with `--max-bitrate 8000`
- **THEN** files above 8000 kbps have the cause `over_bitrate_limit` and `bitrate_limit` is
  `{"kbps": 8000, "source": "option"}`

#### Scenario: A limit chosen by the user, settings read once
- **WHEN** the script is run with `--max-bitrate 8000`
- **THEN** `/:/prefs` is requested once, `bitrate_limit` is `{"kbps": 8000, "source": "option"}`
  whatever the server's limit is, and `media_deletion_allowed` comes from the same answer
