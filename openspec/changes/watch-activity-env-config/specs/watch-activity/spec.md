## MODIFIED Requirements

### Requirement: Choosing a source
`--source auto` (the default) SHALL use Tautulli if it's configured and fall back to Plex otherwise,
recording why in `fallback_reason` ("Tautulli is not set up", that its settings couldn't be read and
why, or that it is configured but failed and why). `--source tautulli` SHALL fail with
`TAUTULLI_NOT_CONFIGURED` if it isn't set up, fail with the reason if its settings couldn't be read,
and fail instead of falling back if Tautulli errors. `--source plex` SHALL use Plex only. When Plex is
set up from the environment and the config file can't be used, Tautulli SHALL be treated as
unavailable for that reason rather than stopping the report.

#### Scenario: Tautulli is down
- **WHEN** Tautulli is configured but can't be reached and `--source` is `auto`
- **THEN** the report comes from Plex and `fallback_reason` says Tautulli failed and why

#### Scenario: Plex from the environment, config file damaged
- **WHEN** `PLEX_URL` and `PLEX_TOKEN` are set, the Tautulli variables aren't, the config file is
  damaged, and `--source` is `auto`
- **THEN** the report comes from Plex and `fallback_reason` says Tautulli's settings couldn't be read
  and why
