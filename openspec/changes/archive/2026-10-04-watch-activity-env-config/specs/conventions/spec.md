## MODIFIED Requirements

### Requirement: Settings location
Connection settings SHALL be read from `$XDG_CONFIG_HOME/cinemetric/config.json` (default
`~/.config/cinemetric/config.json`). Keys: `plex_url`, `plex_token`, `verify_tls`, `client_id`,
`tautulli_url`, `tautulli_api_key`, `tautulli_verify_tls`. The environment variables `PLEX_URL`,
`PLEX_TOKEN`, `TAUTULLI_URL` and `TAUTULLI_API_KEY` SHALL take priority over the file. A script SHALL
read the file only when the environment doesn't already provide the settings it needs, and a problem
with the file SHALL stop a script only when the script needs the file for Plex. Files the dashboard
creates SHALL live in `$XDG_DATA_HOME/cinemetric` (default `~/.local/share/cinemetric`;
`%LOCALAPPDATA%\cinemetric` on Windows).

#### Scenario: Environment variables set
- **WHEN** `PLEX_URL` and `PLEX_TOKEN` are set and the config file also has values
- **THEN** the environment variables are used

#### Scenario: Environment variables set and the file is unsafe
- **WHEN** `PLEX_URL` and `PLEX_TOKEN` are set and the config file is readable by other users
- **THEN** every report script still runs against Plex, and none of them reads the file
