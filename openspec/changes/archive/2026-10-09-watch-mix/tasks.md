## 1. Check the Plex details on a real server

- [x] 1.1 Check that `/library/sections/{id}/genre` lists a movie and a TV library's genres with a usable `key`, and that `/library/sections/{id}/all?type=1&genre=<key>` (movies) and `type=2` (shows) return every title in that genre, including titles whose listing entry shows other genres first
- [x] 1.2 Count how many genre requests a real movie and TV library need and how long they take; note it in the design
- [x] 1.3 Check that Plex history entries carry `ratingKey`, `grandparentKey`, `type`, `viewedAt` and `accountID` as `unwatched` and `year-in-review` expect, and that movie and episode listings carry `duration`, `year` and `originallyAvailableAt`
- [x] 1.4 Update the spec and design if any path or field differs from what they say

## 2. Script

- [x] 2.1 Create `plugins/cinemetric/skills/watch-mix/scripts/watch_mix.py` with copies of the shared helpers (`load_config`, `validate_url`, `PlexClient`, `TautulliClient`, `clean`, `media_deletion_allowed`), `ALLOWED_PATHS` for the seven Plex paths and the three allowed Tautulli commands
- [x] 2.2 Options and `--check`: `--months` (1 to 120), `--user`, `--library` (with the no-match and music-only errors), `--top` (1 to 20), `--source`
- [x] 2.3 The shelf: movie, show and episode listings in pages of 500, sizes (every version's parts, shows from their episodes), decades, best-version quality, and a library that can't be read noted in `unavailable`
- [x] 2.4 Genres from Plex's genre filter, merged by name ignoring case across libraries of the same kind, with a `(no genre)` group
- [x] 2.5 Plays: source choice and `fallback_reason`, `OWNER_ONLY`, the period with `months_before`, newest-first paging that stops past the period, the 100,000 cap, music and live TV left out
- [x] 2.6 Watch time per source (`play_duration` or `duration`, or finished plays times the shelf length) and `watch_time_method`
- [x] 2.7 Matching plays to the shelf in steps (rating key, then guid or title and year for movies, show title and season and episode number for episodes; added after a real server left 143 of 365 movie plays unmatched by key alone), `unmatched_plays`, and an episode whose show matches but not the episode going to `unknown` quality
- [x] 2.8 Group rows with shares, storage and `gap_points`, sorting, `watched_more` and `watched_less` with the small and unknown groups left out, `few_plays`
- [x] 2.9 `--user` matching with Tautulli `get_users` and Plex `/accounts`, `user_id` on every `get_history` request, `accountID` filtering, and the errors that don't fall back
- [x] 2.10 Report contents, the notes, `media_deletion_allowed` from `/:/prefs`, cleaning every genre name, and nothing about people or titles in a whole-server report

## 3. SKILL.md

- [x] 3.1 Write `plugins/cinemetric/skills/watch-mix/SKILL.md`: when to use it, how to call the script (`--user` only when the user asks about one person, `--months` for a named period), presentation order (the biggest differences first as plain sentences like "Horror is 18% of your movies but 3% of what's watched", then genres, decades and quality for movies and TV), always saying how watch time was measured, that genre shares can add up past 100%, that plays are grouped by today's files, unmatched plays, the `few_plays` caution and that recently added titles can look under-watched, facts only (no suggestions to add or remove anything), the media deletion line, and the rules every `SKILL.md` carries
- [x] 3.2 `allowed-tools` lists only `Read` and the script

## 4. Tests

- [x] 4.1 Add made-up fixtures in `tests/fixtures/watch-mix/` (no real names; titles from the public domain or invented), including a movie in three genres whose listing entry shows two
- [x] 4.2 Add `tests/test_watch_mix.py` covering everything listed for `watch-mix` in the testing spec
- [x] 4.3 List the new script in `tests/helpers.py` so the cross-script security, shared helper and media deletion checks run against it
- [x] 4.4 Run the full test suite and fix anything that fails

## 5. Docs, website and version

- [x] 5.1 README: new row in the Skills table; remove `watch-mix` from the Roadmap
- [x] 5.2 `openspec/ideas.md`: remove the `watch-mix` notes, update the line about the new skills, and note under `year-in-review` that the genre filter lookup in `watch_mix.py` is what favorite genres would reuse
- [x] 5.3 `website/index.html`: the new skill in the **Watching** group, with a description, an example request and a terminal demo panel using made-up data (seventeen skills)
- [x] 5.4 Bump the version to 0.31.0 in every script's `VERSION`, `plugin.json` and `marketplace.json`
- [x] 5.5 Try the skill against a real server: whole server with Tautulli, `--source plex`, `--user`, `--months 3`, and one library; note anything the tests don't cover (done: all five, plus `--check` and the `USER_NOT_FOUND` and music library errors. The whole server took about 16 seconds. One person with only a handful of plays gives very large gaps, which is what `few_plays` is for)
