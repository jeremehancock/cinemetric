## MODIFIED Requirements

### Requirement: Connection check
The `library-report`, `server-health`, `watch-activity`, `users-and-shares`, `unwatched`,
`what-to-watch`, `episode-gaps`, `playback-check`, `year-in-review`, `title-lookup`, `subtitles-and-languages`, `show-progress` and `collections-and-playlists` scripts SHALL accept `--check`,
which only tests the configured connections and prints a short JSON result instead of building a
report.

#### Scenario: Testing the connection
- **WHEN** a report script is run with `--check`
- **THEN** it contacts the server once to confirm the address and token work, and prints the server
  name and version

### Requirement: Media deletion setting
Every script that reads from the user's Plex server (`setup`, `library-report`, `server-health`,
`watch-activity`, `users-and-shares`, `unwatched`, `what-to-watch`, `episode-gaps`, `playback-check`,
`year-in-review`, `title-lookup`, `subtitles-and-languages`, `show-progress` and `collections-and-playlists`) SHALL report whether Plex's "Allow media deletion" setting is on, in a
top-level `media_deletion_allowed` field. The script SHALL request `/:/prefs` at most once per run and
take the value of the `allowMediaDeletion` setting as a boolean. Every other setting in that answer
SHALL be discarded without being printed. The field SHALL be `null` when Plex isn't configured, when
the request fails for any reason (including 401 or 403 on a server the user doesn't own), or when the
setting is missing. A `null` SHALL NOT stop the report, change its exit code or add an entry to
`unavailable`. `--check` and `server-health`'s `--now-playing` mode SHALL NOT request `/:/prefs`.
The helper that reads it, `media_deletion_allowed`, is a shared helper as described in
"Self-contained scripts".

#### Scenario: Media deletion allowed
- **WHEN** a report script runs and `/:/prefs` has `allowMediaDeletion` set to `true`
- **THEN** the report has `media_deletion_allowed` `true`

#### Scenario: Media deletion switched off
- **WHEN** `/:/prefs` has `allowMediaDeletion` set to `false`
- **THEN** the report has `media_deletion_allowed` `false`

#### Scenario: Not the server owner
- **WHEN** `/:/prefs` answers 403
- **THEN** `media_deletion_allowed` is `null`, the rest of the report is built as usual, the script
  exits 0 and nothing about it is added to `unavailable`

#### Scenario: Secrets in the settings answer
- **WHEN** `/:/prefs` also returns `PlexOnlineToken` and other settings
- **THEN** none of their ids or values appear anywhere in the output

#### Scenario: Connection check
- **WHEN** a script runs with `--check`
- **THEN** `/:/prefs` isn't requested
