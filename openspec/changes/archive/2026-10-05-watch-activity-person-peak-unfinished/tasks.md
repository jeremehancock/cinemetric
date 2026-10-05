## 1. Choosing one person

- [x] 1.1 Add `get_users` to `TAUTULLI_COMMANDS` and confirm its response shape against the real Tautulli (plain list or `{"data": [...]}`); handle both
- [x] 1.2 Add `--user NAME` to the argument parser (ignored by `--check`) and a `PersonError(ReportError)` class
- [x] 1.3 Write one `pick_person(name, people)` helper used by both sources: exact match on any of a person's names ignoring case, else a unique partial match, else `USER_NOT_FOUND` (up to 30 known names) or `USER_AMBIGUOUS` (the matching names). Names go through `clean`
- [x] 1.4 In `build_report`, re-raise `PersonError` instead of falling back to Plex under `--source auto`

## 2. Report on one person

- [x] 2.1 Tautulli: look the person up with `get_users` and pass `user_id` to both `get_home_stats` calls, both `get_plays_by_date` calls and `get_history`
- [x] 2.2 Plex: pick the person from the `/accounts` names and skip history entries from other accounts
- [x] 2.3 Filter `now_watching` to sessions whose user name equals one of the person's names, ignoring case
- [x] 2.4 Add `user` (matched display name, or `null`) to the report

## 3. Most streams at once

- [x] 3.1 Read the "Concurrent Transcodes" row too and add `transcodes` / `transcodes_when` to `most_concurrent_streams` (`null` when the row is missing)
- [x] 3.2 Add `most_concurrent_streams_unavailable`: `null` with Tautulli, a plain reason with Plex
- [x] 3.3 With a person chosen, leave `most_concurrent_streams` `null` with a reason (found on the real server: Tautulli ignores `user_id` for this stat)

## 4. Unfinished titles

- [x] 4.1 Add a paged Tautulli history reader: `after` = period start, `grouping=1`, `media_type` movie then episode, `length=1000`, stop at 20,000 rows in total, plus the person's `user_id` when one is chosen
- [x] 4.2 Group rows by `(user_id, rating_key)`, skip Live TV, keep groups with no `watched_status` 1, and build entries with `user`, `title`, `type`, `furthest_pct`, `plays`, `last_played`
- [x] 4.3 Sort newest `last_played` first, limit to `--top`, and add `unfinished`, `unfinished_count`, `unfinished_capped`
- [x] 4.4 Plex source: `unfinished` and `unfinished_count` `null`, with the reason in `unfinished_unavailable`

## 5. Tests

- [x] 5.1 Extend `tests/fixtures/watch-activity/tautulli.json`: `get_users`, the extra history rows for unfinished cases (abandoned twice, finished on a later try, two people with one finished, a Live TV row, a music row), and route `get_history` by `media_type` / `start` in `tautulli_route`
- [x] 5.2 Add a second account's plays to `tests/fixtures/watch-activity/plex.json` and a second session by another user
- [x] 5.3 Tests for choosing a person: exact name in a different case, partial name, two matches, no match with Tautulli under `--source auto` (no fallback), no match with Plex, and `--check` ignoring `--user`
- [x] 5.4 Tests for the person filter: Plex counts only their plays, every Tautulli history and stats request carries their `user_id`, `now_watching` keeps only their session, `user` is set
- [x] 5.5 Tests for the busiest moment: Tautulli gives streams and transcodes with times; Plex gives `null` plus the reason
- [x] 5.6 Tests for unfinished titles: each spec scenario, the `--top` limit and `unfinished_count`, the 20,000-row cap, and Plex giving `null` plus the reason
- [x] 5.7 Check the security allowlist tests still pass with `get_users` added
- [x] 5.8 `python3 -m unittest discover -s tests` passes

## 6. Tell Claude about it

- [x] 6.1 watch-activity `SKILL.md`: add `--user` to `argument-hint` and the run section ("what has Sam watched" → `--user Sam`), and add one-person questions, peak streams and unfinished titles to the `description` triggers
- [x] 6.2 watch-activity `SKILL.md`: explain `USER_NOT_FOUND` (offer the listed names) and `USER_AMBIGUOUS` (ask which one) in the errors section
- [x] 6.3 watch-activity `SKILL.md`: list the new fields; when `user` is set, write the report about that person and say who was matched if it was a partial match
- [x] 6.4 watch-activity `SKILL.md`: busiest moment as its own short part (streams and transcodes at peak, when), pointing to `server-health` for bandwidth in Mbps; with Plex, one line from `most_concurrent_streams_unavailable`
- [x] 6.5 watch-activity `SKILL.md`: a "Started but not finished" part: facts only, note that recently played ones may still be in progress and that "not finished" means within this period, mention `unfinished_capped`, and with Plex one line from `unfinished_unavailable`

## 7. Docs

- [x] 7.1 README: add one person, busiest moment and unfinished titles to the watch-activity row of the skills table, and remove the `watch-activity` item from the Roadmap
- [x] 7.2 `openspec/ideas.md`: remove the `watch-activity` notes and update "Suggested order" so `unwatched` is next
- [x] 7.3 Website: add the new abilities (and an example question like "What has Sam watched lately?") to the watch-activity section of `website/index.html`

## 8. Verify

- [x] 8.1 Run against the real server: valid JSON, existing fields unchanged without `--user`, `--user` with a real name narrows everything, and the `unfinished` list matches what Tautulli's history page shows
- [x] 8.2 Run `dashboard.py` and confirm the page still builds unchanged
- [x] 8.3 `openspec validate watch-activity-person-peak-unfinished` passes

## 9. Release

- [x] 9.1 Bump the version to 0.12.0 in all six scripts, `plugin.json` and `marketplace.json`
