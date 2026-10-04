# watch-activity Specification

## Purpose

A read-only summary of what's been watched on a Plex server, from Tautulli when it's set up and from
Plex's own history otherwise. Script: `skills/watch-activity/scripts/watch_activity.py`. How Claude
presents it is in the skill's `SKILL.md`.

## Requirements

### Requirement: Sources used
With Plex, the script SHALL request only `/`, `/accounts` and `/status/sessions/history/all`. With
Tautulli, it SHALL run only `get_tautulli_info`, `get_home_stats`, `get_history` and
`get_plays_by_date`.

#### Scenario: Building a Tautulli report
- **WHEN** the report is built from Tautulli
- **THEN** only those four commands are sent to Tautulli

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
`source`, `totals` (plays, watch_hours, active_users), `plays_by_type`, `top_movies`, `top_shows`,
`top_music`, `top_users`, `top_platforms`, `most_concurrent_streams`, `daily` (one entry per day),
`trend` (plays in the earlier and later halves of the period) and `recent_plays`, newest first.

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

