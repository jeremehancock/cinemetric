## MODIFIED Requirements

### Requirement: Sources used
With Plex, the script SHALL request only `/`, `/accounts`, `/status/sessions/history/all` and
`/status/sessions`. With Tautulli, it SHALL run only `get_tautulli_info`, `get_home_stats`,
`get_history`, `get_plays_by_date` and `get_users`. Current sessions SHALL always come from Plex's
`/status/sessions`, whichever source the history comes from.

#### Scenario: Building a Tautulli report
- **WHEN** the report is built from Tautulli
- **THEN** only commands from that list are sent to Tautulli

#### Scenario: Current sessions with Tautulli as the source
- **WHEN** the history comes from Tautulli and Plex is set up
- **THEN** current sessions are read from Plex's `/status/sessions`, not from Tautulli

### Requirement: Options
The script SHALL accept `--days N` (default 30, limited to 1–3650), `--top N` (entries per top list,
default 10, limited to 1–50), `--recent N` (recent plays, default 15, limited to 0–100) and
`--user NAME` (report on one person only; default everyone). `--check` SHALL ignore `--user`.

#### Scenario: Out-of-range value
- **WHEN** run with `--top 500`
- **THEN** top lists have at most 50 entries

#### Scenario: No person given
- **WHEN** run without `--user`
- **THEN** the report covers everyone and `user` is `null`

### Requirement: Report contents
The report SHALL contain `cinemetric_version`, `generated_at`, `period_days`, `user`,
`fallback_reason`, `source`, `now_watching`, `now_watching_unavailable`, `totals` (plays,
watch_hours, active_users), `plays_by_type`, `top_movies`, `top_shows`, `top_music`, `top_users`,
`top_platforms`, `most_concurrent_streams`, `most_concurrent_streams_unavailable`, `daily` (one entry
per day), `trend` (plays in the earlier and later halves of the period), `recent_plays` (newest
first), `unfinished`, `unfinished_count` and `unfinished_unavailable`.

`most_concurrent_streams`, when present, SHALL contain `streams` and `when` (the most streams at once
and when that happened) and `transcodes` and `transcodes_when` (the most transcoding streams at once
and when). `transcodes` and `transcodes_when` SHALL be `null` when Tautulli doesn't report them.

#### Scenario: Comparing halves of the period
- **WHEN** the period is 30 days
- **THEN** `trend` compares the first 15 days' plays with the last 15 days'

#### Scenario: Busiest moment with Tautulli
- **WHEN** Tautulli reports a peak of 3 streams and a peak of 1 transcode in the period
- **THEN** `most_concurrent_streams` has `streams` 3 and `transcodes` 1, each with its own time, and
  `most_concurrent_streams_unavailable` is `null`

### Requirement: Differences between sources
With Plex as the source, `watch_hours` SHALL be `null` and `top_platforms` empty, since Plex's
history only counts plays. Also with Plex, `most_concurrent_streams` SHALL be `null` with
`most_concurrent_streams_unavailable` saying Plex's history doesn't record when plays started and
stopped, and `unfinished` and `unfinished_count` SHALL be `null` with `unfinished_unavailable` saying
Plex's history only records finished plays. With Tautulli, `unfinished_unavailable` SHALL be `null`,
and so SHALL `most_concurrent_streams_unavailable` unless a person is chosen (see "Report on one
person"). The period SHALL start at midnight on its first day. At most 20,000 Plex history entries
SHALL be read, and `history_capped` SHALL be true when that limit is reached. With Tautulli,
Tautulli's own "Total" series SHALL be left out of daily counts so plays aren't counted twice.

#### Scenario: Very large Plex history
- **WHEN** the period holds more than 20,000 plays
- **THEN** only the newest 20,000 are counted and `history_capped` is true

#### Scenario: Plex as the source
- **WHEN** the report comes from Plex
- **THEN** `most_concurrent_streams`, `unfinished` and `unfinished_count` are `null`, and
  `most_concurrent_streams_unavailable` and `unfinished_unavailable` each give the reason

## ADDED Requirements

### Requirement: Choosing one person
With `--user NAME`, the script SHALL find the person in the source the history comes from: with
Tautulli, among `get_users`' friendly names and usernames; with Plex, among `/accounts` names. Matching
SHALL ignore upper and lower case. An exact match on any of a person's names SHALL win; otherwise a
person SHALL be chosen when exactly one person's name contains NAME. If no one matches, the script
SHALL fail with `USER_NOT_FOUND` and list the names it knows (at most 30). If more than one person
matches and none exactly, it SHALL fail with `USER_AMBIGUOUS` and list the matching names. These
errors SHALL NOT cause `--source auto` to fall back from Tautulli to Plex. `user` in the report
SHALL be the matched person's display name (Tautulli's friendly name, or the Plex account name).

#### Scenario: Exact name, different case
- **WHEN** run with `--user ALEX-TEST` and a person named `alex-test` exists
- **THEN** the report is about `alex-test` and `user` is `alex-test`

#### Scenario: Part of a name
- **WHEN** run with `--user sam`, one person is called `Samantha` and no one is called `sam`
- **THEN** the report is about `Samantha`

#### Scenario: Two people match
- **WHEN** run with `--user sam` and both `Samantha` and `Sammy` exist
- **THEN** the script stops with `error: USER_AMBIGUOUS: ...` naming both

#### Scenario: Nobody matches with Tautulli
- **WHEN** Tautulli is the source, `--source` is `auto` and no one matches
- **THEN** the script stops with `error: USER_NOT_FOUND: ...` and does not fall back to Plex

### Requirement: Report on one person
When a person is chosen, every part of the report SHALL cover only that person: totals, plays by
type, top lists, `top_users` (just them), platforms, `daily`, `trend`, `recent_plays` and
`unfinished`. With Tautulli, the person's `user_id` SHALL be passed to `get_home_stats`,
`get_plays_by_date` and `get_history`; with Plex, history entries SHALL be kept only when their
account matches. `now_watching` SHALL keep only sessions whose user name equals one of the person's
names, ignoring case. Tautulli's `most_concurrent` stat ignores `user_id`, so when a person is chosen
`most_concurrent_streams` SHALL be `null` and `most_concurrent_streams_unavailable` SHALL say Tautulli
only counts streams at once for the whole server.

#### Scenario: One person with Plex
- **WHEN** the source is Plex, run with `--user alex-test`, and the history holds plays by
  `alex-test` and another account
- **THEN** totals, top lists, daily counts and recent plays count only `alex-test`'s plays

#### Scenario: One person with Tautulli
- **WHEN** the source is Tautulli and `alex-test` is chosen
- **THEN** every `get_home_stats`, `get_plays_by_date` and `get_history` request carries that
  person's `user_id`

#### Scenario: Busiest moment for one person
- **WHEN** the source is Tautulli and a person is chosen
- **THEN** `most_concurrent_streams` is `null` and `most_concurrent_streams_unavailable` says the
  figure is only available for the whole server

#### Scenario: Someone else is watching now
- **WHEN** a person is chosen and Plex reports one session by them and one by someone else
- **THEN** `now_watching` has only their session

### Requirement: Unfinished titles
With Tautulli, the script SHALL read the period's movie and episode history with `get_history`
(grouped, so a play resumed later counts as one play), in pages, up to 20,000 rows in total, and set
`unfinished_capped` to true when that limit is reached. Live TV SHALL be left out. A title SHALL count
as unfinished for a person when that person played it in the period and none of their plays of it in
the period was marked watched. Each `unfinished` entry SHALL have `user`, `title` (as in
`recent_plays`), `type`, `furthest_pct` (the highest percent reached), `plays` and `last_played`.
`unfinished` SHALL be sorted by `last_played`, newest first, and hold at most `--top` entries;
`unfinished_count` SHALL be the total before that limit.

#### Scenario: Started and abandoned
- **WHEN** a person played a movie twice in the period, reaching 20% and then 35%, and never finished
  it
- **THEN** `unfinished` has one entry for that person and movie with `furthest_pct` 35 and `plays` 2

#### Scenario: Finished on a later try
- **WHEN** a person stopped a movie at 40% and later watched it to the end in the same period
- **THEN** that movie isn't in `unfinished` for that person

#### Scenario: Two people, one finished
- **WHEN** one person finished an episode and another stopped it halfway
- **THEN** `unfinished` lists only the person who stopped halfway

#### Scenario: More than the top limit
- **WHEN** 25 titles are unfinished and `--top` is 10
- **THEN** `unfinished` holds the 10 most recently played and `unfinished_count` is 25
