## MODIFIED Requirements

### Requirement: Skill shape
Each skill SHALL live in `plugins/cinemetric/skills/<name>/` as a `SKILL.md` plus one script in
`scripts/`. The script collects the facts and prints them; Claude turns them into the written report
by following `SKILL.md`. The `dashboard`, `year-in-review` and `export` skills are the exceptions: their pages (or, for
`export`, its workbook) are written by rules in the script, not by Claude.

#### Scenario: Adding a new skill
- **WHEN** a new skill is added
- **THEN** it has a `SKILL.md` and a single script under `scripts/`, and the script prints JSON that
  `SKILL.md` tells Claude how to present

#### Scenario: A recap page
- **WHEN** the year-in-review script runs
- **THEN** it writes the recap page itself by fixed rules and also prints JSON that `SKILL.md` tells
  Claude how to summarize

#### Scenario: An export
- **WHEN** the export script runs
- **THEN** it writes the workbook itself by fixed rules and prints a JSON summary that `SKILL.md`
  tells Claude how to present

### Requirement: Connection check
The `library-report`, `server-health`, `watch-activity`, `users-and-shares`, `unwatched`,
`what-to-watch`, `episode-gaps`, `playback-check`, `year-in-review`, `title-lookup`, `subtitles-and-languages`, `show-progress`, `collections-and-playlists`, `watch-mix` and `export` scripts SHALL accept `--check`,
which only tests the configured connections and prints a short JSON result instead of building a
report.

#### Scenario: Testing the connection
- **WHEN** a report script is run with `--check`
- **THEN** it contacts the server once to confirm the address and token work, and prints the server
  name and version

### Requirement: Settings location
Connection settings SHALL be read from `$XDG_CONFIG_HOME/cinemetric/config.json` (default
`~/.config/cinemetric/config.json`). Keys: `plex_url`, `plex_token`, `verify_tls`, `client_id`,
`tautulli_url`, `tautulli_api_key`, `tautulli_verify_tls`. The environment variables `PLEX_URL`,
`PLEX_TOKEN`, `TAUTULLI_URL` and `TAUTULLI_API_KEY` SHALL take priority over the file. A script SHALL
read the file only when the environment doesn't already provide the settings it needs, and a problem
with the file SHALL stop a script only when the script needs the file for Plex. Files the dashboard
creates, workbooks `export` saves (unless the user names another place), and snapshots (in a `snapshots` folder), SHALL live in `$XDG_DATA_HOME/cinemetric` (default
`~/.local/share/cinemetric`; `%LOCALAPPDATA%\cinemetric` on Windows; `CINEMETRIC_DATA_DIR` overrides
it).

#### Scenario: Environment variables set
- **WHEN** `PLEX_URL` and `PLEX_TOKEN` are set and the config file also has values
- **THEN** the environment variables are used

#### Scenario: Environment variables set and the file is unsafe
- **WHEN** `PLEX_URL` and `PLEX_TOKEN` are set and the config file is readable by other users
- **THEN** every report script still runs against Plex, and none of them reads the file

#### Scenario: Where snapshots go
- **WHEN** `XDG_DATA_HOME` is `/tmp/x` and a snapshot is saved
- **THEN** it is under `/tmp/x/cinemetric/snapshots/`

#### Scenario: Where an export goes
- **WHEN** `XDG_DATA_HOME` is `/tmp/x` and an export runs without `--output`
- **THEN** the workbook is in `/tmp/x/cinemetric/`

### Requirement: Media deletion setting
Every script that reads from the user's Plex server (`setup`, `library-report`, `server-health`,
`watch-activity`, `users-and-shares`, `unwatched`, `what-to-watch`, `episode-gaps`, `playback-check`,
`year-in-review`, `title-lookup`, `subtitles-and-languages`, `show-progress`, `collections-and-playlists`, `watch-mix` and `export`) SHALL report whether Plex's "Allow media deletion" setting is on, in a
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
