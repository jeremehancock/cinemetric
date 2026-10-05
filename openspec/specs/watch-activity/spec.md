# watch-activity Specification

## Purpose

A read-only summary of who's watching a Plex server right now and what's been watched over time.
History comes from Tautulli when it's set up and from Plex's own history otherwise; current
sessions always come from Plex. Script: `skills/watch-activity/scripts/watch_activity.py`. How Claude
presents it is in the skill's `SKILL.md`.

## Requirements

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

### Requirement: Owner-only history
Plex only gives the full watch history to the server owner. If the Plex history request is refused
(401 or 403) but the token still works for `/`, the script SHALL fail with `OWNER_ONLY`.

#### Scenario: Connected to a shared server without Tautulli
- **WHEN** the history request returns 403 and `/` succeeds
- **THEN** the script stops with `error: OWNER_ONLY: ...`

### Requirement: Options
The script SHALL accept `--days N` (default 30, limited to 1–3650), `--top N` (entries per top list,
default 10, limited to 1–50) and `--recent N` (recent plays, default 15, limited to 0–100).

#### Scenario: Out-of-range value
- **WHEN** run with `--top 500`
- **THEN** top lists have at most 50 entries

### Requirement: Report contents
The report SHALL contain `cinemetric_version`, `generated_at`, `period_days`, `fallback_reason`,
`source`, `now_watching`, `now_watching_unavailable`, `totals` (plays, watch_hours, active_users),
`plays_by_type`, `top_movies`, `top_shows`, `top_music`, `top_users`, `top_platforms`,
`most_concurrent_streams`, `daily` (one entry per day), `trend` (plays in the earlier and later
halves of the period) and `recent_plays`, newest first.

#### Scenario: Comparing halves of the period
- **WHEN** the period is 30 days
- **THEN** `trend` compares the first 15 days' plays with the last 15 days'

### Requirement: Differences between sources
With Plex as the source, `watch_hours` SHALL be `null`, `top_platforms` empty and
`most_concurrent_streams` `null`, since Plex's history only counts plays. The period SHALL start at
midnight on its first day. At most 20,000 history entries SHALL be read, and `history_capped` SHALL be
true when that limit is reached. With Tautulli, Tautulli's own "Total" series SHALL be left out of
daily counts so plays aren't counted twice.

#### Scenario: Very large Plex history
- **WHEN** the period holds more than 20,000 plays
- **THEN** only the newest 20,000 are counted and `history_capped` is true

### Requirement: Connection check
`--check` SHALL test Plex and Tautulli separately. A Tautulli failure SHALL be reported in the result
(with `ok: false`) rather than as an error.

#### Scenario: Tautulli key changed
- **WHEN** `--check` runs and Tautulli rejects the key
- **THEN** the output has `ok: false` and the Tautulli error, and the Plex result is still shown

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

