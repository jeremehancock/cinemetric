## MODIFIED Requirements

### Requirement: Sources used
With Plex, the script SHALL request only `/`, `/accounts`, `/status/sessions/history/all` and
`/status/sessions`. With Tautulli, it SHALL run only `get_tautulli_info`, `get_home_stats`,
`get_history` and `get_plays_by_date`. Current sessions SHALL always come from Plex's
`/status/sessions`, whichever source the history comes from.

#### Scenario: Building a Tautulli report
- **WHEN** the report is built from Tautulli
- **THEN** only those four commands are sent to Tautulli

#### Scenario: Current sessions with Tautulli as the source
- **WHEN** the history comes from Tautulli and Plex is set up
- **THEN** current sessions are read from Plex's `/status/sessions`, not from Tautulli

### Requirement: Report contents
The report SHALL contain `cinemetric_version`, `generated_at`, `period_days`, `fallback_reason`,
`source`, `now_watching`, `now_watching_unavailable`, `totals` (plays, watch_hours, active_users),
`plays_by_type`, `top_movies`, `top_shows`, `top_music`, `top_users`, `top_platforms`,
`most_concurrent_streams`, `daily` (one entry per day), `trend` (plays in the earlier and later
halves of the period) and `recent_plays`, newest first.

#### Scenario: Comparing halves of the period
- **WHEN** the period is 30 days
- **THEN** `trend` compares the first 15 days' plays with the last 15 days'

## ADDED Requirements

### Requirement: Current sessions
`now_watching` SHALL be a list with one entry per session Plex reports as current, each with `user`,
`title` (episodes as "Show S01E02", tracks as "Artist - Track", others as "Title (Year)"), `type`,
`player`, `platform`, `state` (as Plex reports it, e.g. `playing` or `paused`), `progress_pct`
(`null` when the length is unknown) and `live_tv`. It SHALL NOT include playback method, bandwidth
or source quality. When nothing is playing, `now_watching` SHALL be an empty list and
`now_watching_unavailable` `null`.

Reading current sessions SHALL NOT stop the report. If Plex isn't set up, the request is refused, or
it fails for any other reason, `now_watching` SHALL be `null`, `now_watching_unavailable` SHALL say
why (a 401 or 403 is described as "only available to the server owner's account"), and the rest of
the report SHALL be built as usual. A refused sessions request SHALL NOT cause `OWNER_ONLY`.
`--check` SHALL NOT read current sessions.

#### Scenario: Two people watching
- **WHEN** Plex reports one episode playing and one movie paused
- **THEN** `now_watching` has two entries with their users, titles, devices, states and progress,
  and `now_watching_unavailable` is `null`

#### Scenario: Nothing playing
- **WHEN** Plex reports no current sessions
- **THEN** `now_watching` is an empty list and `now_watching_unavailable` is `null`

#### Scenario: Shared server with Tautulli
- **WHEN** the history comes from Tautulli and Plex refuses `/status/sessions` with 403
- **THEN** the report is built from Tautulli, `now_watching` is `null` and
  `now_watching_unavailable` says it's only available to the server owner's account

#### Scenario: Tautulli only, no Plex
- **WHEN** only Tautulli is set up
- **THEN** the report is built from Tautulli, `now_watching` is `null` and
  `now_watching_unavailable` says Plex is not set up

#### Scenario: Sessions request fails, history works
- **WHEN** the history comes from Plex and `/status/sessions` returns a server error
- **THEN** the history report is still produced, with `now_watching` `null` and the reason in
  `now_watching_unavailable`
