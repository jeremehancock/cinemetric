## MODIFIED Requirements

### Requirement: Self-contained scripts
Each script SHALL run on its own, without importing code from another skill. Shared helpers (config
loading, address checks, the GET-only Plex client, text cleaning, and finding and reading snapshots)
are copied into each script that needs them. A change to one copy of a shared helper SHALL be made to
every copy.

#### Scenario: Fixing a bug in a shared helper
- **WHEN** a bug is fixed in `load_config`, `validate_url`, `PlexClient`, `clean` or the snapshot
  reading helper in one script
- **THEN** the same fix is applied to every script that has a copy of that helper

### Requirement: Settings location
Connection settings SHALL be read from `$XDG_CONFIG_HOME/cinemetric/config.json` (default
`~/.config/cinemetric/config.json`). Keys: `plex_url`, `plex_token`, `verify_tls`, `client_id`,
`tautulli_url`, `tautulli_api_key`, `tautulli_verify_tls`. The environment variables `PLEX_URL`,
`PLEX_TOKEN`, `TAUTULLI_URL` and `TAUTULLI_API_KEY` SHALL take priority over the file. A script SHALL
read the file only when the environment doesn't already provide the settings it needs, and a problem
with the file SHALL stop a script only when the script needs the file for Plex. Files the dashboard
creates, and snapshots (in a `snapshots` folder), SHALL live in `$XDG_DATA_HOME/cinemetric` (default
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

## ADDED Requirements

### Requirement: Reading snapshots
`library_report.py`, `server_health.py` and `users_and_shares.py` SHALL read snapshots but never write
them; only `changes.py` writes, prunes or deletes them. To compare, a report SHALL use the newest
snapshot file for this server (folder named by the server's `machineIdentifier`) that is readable (see
"Snapshots are read as data" in the security spec), has `format` 1 and contains the report's area, and
whose date is before today's local date. With `--since DAYS`, it SHALL use the newest such file dated
at least DAYS days before today, or, if none is that old, the oldest such file. `since_snapshot` SHALL
give that file's `snapshot_date` and `days_ago`. A problem reading snapshots SHALL never stop a report;
`since_snapshot` is then `null`.

#### Scenario: A snapshot from earlier today
- **WHEN** snapshots exist for today and for 3 days ago
- **THEN** the report compares with the one from 3 days ago

#### Scenario: What changed this week
- **WHEN** run with `--since 7` and snapshots exist for 1, 6, 8 and 20 days ago
- **THEN** the report compares with the one from 8 days ago

#### Scenario: Not old enough
- **WHEN** run with `--since 30` and the oldest snapshot is from 5 days ago
- **THEN** the report compares with it and `days_ago` is 5

#### Scenario: Snapshot missing the area
- **WHEN** yesterday's snapshot has no `sharing` area and last week's does
- **THEN** `users_and_shares.py` compares with last week's

#### Scenario: Another server's snapshots
- **WHEN** the user switched servers and snapshots exist only for the old one
- **THEN** `since_snapshot` is `null`
