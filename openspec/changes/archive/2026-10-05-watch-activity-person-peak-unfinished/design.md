## Context

`watch_activity.py` builds its report from Tautulli when it's set up and from Plex's own history
otherwise. Three additions from the roadmap (`openspec/ideas.md`, "watch-activity") go into this
change: one person, most streams at once, and started but never finished.

What already exists:

- `most_concurrent_streams` is already in the report, from Tautulli's `most_concurrent` home stat. The
  script picks the "Concurrent Streams" row and ignores the others ("Concurrent Transcodes", and in
  real Tautulli also direct stream and direct play rows). With Plex it's `null` with no explanation.
- Tautulli's `get_history` is only asked for the newest `--recent` rows.
- The Plex path already has every play's `accountID` and an account name map from `/accounts`.

Checked against Tautulli's API reference (wiki, "Tautulli API Reference") on 2026-10-05. The connected
server runs Tautulli v2.18.2:

- `get_home_stats` accepts `user_id` (and `section_id`, `before`, `after`).
- `get_plays_by_date` accepts `user_id` (comma separated list).
- `get_history` accepts `user`, `user_id`, `after`, `media_type`, `grouping`, `start`, `length`, and
  returns `started`, `stopped`, `watched_status`, `percent_complete`, `rating_key`, `user_id`,
  `live`.
- `get_users` returns each user's `user_id`, `friendly_name` and `username` (exact shape still to
  confirm against the real server: a plain list is expected).

## Goals / Non-Goals

**Goals:**
- Answer "what has this person watched lately?" with the same report, narrowed to one person.
- Make the busiest-moment figure more useful for bandwidth planning, and explain its absence with Plex.
- List titles people started and didn't finish, as plain facts.

**Non-Goals:**
- Working out the peak from Plex history. Plex history entries only have `viewedAt` (when the play was
  logged), not start and stop times, so any figure would be a guess.
- Bandwidth in Mbps. Tautulli's history rows don't include bitrate without one request per play
  (`get_stream_data`). Bandwidth right now is `server-health`'s job.
- "Abandoned shows" (someone stopped watching a series). That needs the show's episode list from the
  library, which this script doesn't read.
- Dashboard changes. It doesn't pass `--user` and ignores unknown fields.
- More than one person per run.

## Decisions

**1. Look people up with `get_users`, not from the `top_users` stat.**
`top_users` only lists people who played something in the period, so a person who watched nothing
would come back as "not found" instead of "no plays". `get_users` lists everyone Tautulli knows. It's
one extra read-only command, added to `TAUTULLI_COMMANDS` and the "Sources used" requirement.

**2. Match names: exact first, then a unique partial match.**
Users will type "sam" for "Samantha", and Claude shouldn't have to guess spellings. An exact match
(ignoring case) on either the friendly name or username wins outright, so "sam" still works when both
"sam" and "Samantha" exist. If the partial match finds several people, stop and list them so Claude
can ask. Not-found lists up to 30 known names so Claude can suggest the right one. Names are already
shown in normal reports, so listing them isn't new exposure.

**3. Person errors don't trigger the Plex fallback.**
`build_report` currently turns any Tautulli `ReportError` into a fallback to Plex under `--source
auto`. A wrong name isn't a Tautulli failure, and silently switching to Plex (where the name might
match someone else, or where the data is thinner) would be confusing. Use a small `PersonError`
subclass of `ReportError` that the fallback re-raises.

**4. With Tautulli, filter on the server; with Plex, filter in the script.**
Tautulli takes `user_id` on all three history commands, so its stats come back already narrowed. The
Plex path already loops over every history entry, so it just skips other accounts. Current sessions
are filtered in the script by comparing the session's user name with the person's names (for Tautulli:
friendly name and username; Plex sessions report the Plex username, which Tautulli stores as
`username`).

Alternative considered: Tautulli's `get_history` `user` parameter (by name). Rejected because
`get_home_stats` and `get_plays_by_date` only take `user_id`, so the id is needed anyway.

Found during implementation (2026-10-05, Tautulli v2.18.2): `get_home_stats` honors `user_id` for
top lists but **not** for `most_concurrent`. Every person got the server-wide peak. So with a person
chosen, `most_concurrent_streams` is `null` with a reason, rather than showing a misleading number.
Working out a per-person peak from history start and stop times is possible later if wanted.

**5. Peak transcodes from the same stat row set.**
Read the "Concurrent Transcodes" row next to "Concurrent Streams" and add `transcodes` /
`transcodes_when`. No new request. Total streams answer "how much upload do I need at peak?";
transcodes answer "how hard does the server work at peak?". Plex gets a reason string instead of a
silent `null`, using the same `*_unavailable` pattern as `now_watching_unavailable`.

**6. Unfinished titles from a full read of the period's history, grouped.**
- Request `get_history` with `after=<period start>`, `grouping=1` and `media_type` set, once for
  `movie` and once for `episode`, paging with `start`/`length=1000`. Grouping makes Tautulli merge a
  play that was paused and resumed later into one row, so "stopped at 40%, came back, finished" shows
  as finished.
- Music is left out (skipping songs is normal and would flood the list). Live TV rows (`live` = 1) are
  left out because there's no "end" to reach.
- Key by `(user_id, rating_key)`. Unfinished means no row in the period has `watched_status` 1.
  Tautulli sets that from its own "watched" percentage setting, so the report agrees with what
  Tautulli's own pages show.
- Cap at 20,000 rows across both media types, matching `PLEX_HISTORY_CAP`, with `unfinished_capped`.
- Always on (no flag). For the default 30 days this is one or two requests per type. The dashboard
  pays the same small cost.

Alternative considered: only look at the `--recent` rows already fetched. Rejected: far too few rows
to say anything was never finished.

Limitation, said plainly in SKILL.md: "never finished" means "not finished within this period". A
movie finished 60 days ago and partly rewatched last week shows as unfinished in a 30-day report.

**7. Titles look like `recent_plays`.**
Use Tautulli's `full_title` (cleaned), so episodes read as "Show - Episode name" like recent plays
already do.

## Risks / Trade-offs

- [`get_users` shape differs from the docs] → Verify against the real server during implementation;
  handle both a plain list and a `{"data": [...]}` wrapper, since other Tautulli commands use the
  wrapper.
- [Session user names don't match Tautulli names, so `now_watching` drops the person's own session] →
  Compare against both friendly name and username. Verify on the real server with an active stream if
  possible; if it still misses, note it in SKILL.md rather than guessing.
- [Large history on long periods (`--days 365`) is slow] → Paging at 1,000 rows and the 20,000 cap
  bound it to about 20 requests. `unfinished_capped` tells Claude the list may be incomplete.
- [The unfinished list feels like it's judging people] → Facts only in the JSON (who, what, how far,
  when). SKILL.md keeps the existing "no judgments about viewing habits" rule and adds that recently
  played entries may simply still be in progress.
- [Partial match picks the wrong person] → Only when exactly one person matches, and `user` in the
  report shows who was chosen so Claude can say it.

## Migration Plan

None needed: new option and new fields only. Ships with a version bump.

## Open Questions

- None blocking. Exact `get_users` response shape is confirmed during implementation (task list).
