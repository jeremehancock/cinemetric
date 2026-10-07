## 1. Check the Plex and Tautulli details on a real server

- [x] 1.1 Check that `/status/sessions/history/all` accepts `type=4` to return only episodes, and that episode entries carry `grandparentKey`, `parentIndex`, `index`, `accountID` and `viewedAt`; if `type` is ignored, filter in the script (see design.md)
- [x] 1.2 Check that Tautulli's `get_history` with `media_type=episode` returns `grandparent_rating_key`, `parent_media_index` and `media_index`, and accepts `grandparent_rating_key` and `user_id` filters together
- [x] 1.3 Check that `/library/sections/{id}/all?type=4` gives each episode's `grandparentRatingKey`, `parentIndex`, `index`, `addedAt` and media versions with `deletedAt`, as `episode-gaps` relies on
- [x] 1.4 Check whether history rows keep the same season and episode numbers after a file is replaced (the reason plays are matched by numbers, not rating key)

## 2. Script

- [x] 2.1 Create `plugins/cinemetric/skills/show-progress/scripts/show_progress.py` with copies of the shared helpers (`load_config`, `validate_url`, `PlexClient`, `TautulliClient`, `clean`, `media_deletion_allowed`), `ALLOWED_PATHS` for the six paths and `TAUTULLI_COMMANDS` for `get_tautulli_info`, `get_history` and `get_users`
- [x] 2.2 Options and `--check`, including the errors for bad numbers and a `--library` that matches no TV library
- [x] 2.3 Source choice and `fallback_reason` copied from `watch-activity`, `plex_history_note`, and `OWNER_ONLY` on 401 or 403
- [x] 2.4 Episode list: TV libraries only, `skipped_libraries`, episodes on the server (unavailable files, specials, unnumbered episodes, two copies of one episode), show titles and years
- [x] 2.5 History: Tautulli and Plex in pages up to 100,000 rows, `history_capped`, `history_since`, Live TV left out, private Tautulli fields dropped on reading, `/accounts` for names
- [x] 2.6 Matching rows to episodes by show key, season and episode; `unmatched_plays`
- [x] 2.7 Each person's place: `furthest`, `episodes_finished`, `episodes_left`, `next_episode`, `new_since_last_play`, `last_played_at` and `status` in the spec's order
- [x] 2.8 `recently_added` with `finished_new` per person and `nobody_started`
- [x] 2.9 `--user` (copied person matching and errors from `watch-activity`, `user_id` passed to Tautulli) and `--show` (matching, `SHOW_NOT_FOUND`, `SHOW_AMBIGUOUS`, filtering at the source, a show nobody watches)
- [x] 2.10 Report contents, sorting, `--top`, `show_count` and `status_counts`
- [x] 2.11 `media_deletion_allowed` from `/:/prefs`, reading only the allowed setting

## 3. SKILL.md

- [x] 3.1 Write `plugins/cinemetric/skills/show-progress/SKILL.md`: when to use it, how to call the script (turning "who's watching Severance" into `--show` and "what has Sam got going" into `--user`), presentation order (a short headline, shows with each person's place and status in plain words, then recently added episodes nobody has started), explaining that "caught up" means caught up with what's on the server and that positions are the furthest episode reached, mentioning the Plex history limit when `plex_history_note` is present, asking which show on `SHOW_AMBIGUOUS`, facts only, the media deletion line, and the rules every `SKILL.md` carries
- [x] 3.2 `allowed-tools` lists only `Read` and the script

## 4. Tests

- [x] 4.1 Add made-up fixtures in `tests/fixtures/show-progress/` (no real names, invented or public domain show titles)
- [x] 4.2 Add `tests/test_show_progress.py` covering everything listed for `show-progress` in the testing spec
- [x] 4.3 Add the new script to the cross-script security and media deletion tests
- [x] 4.4 Run the full test suite and fix anything that fails

## 5. Docs, website and version

- [x] 5.1 README: new row in the Skills table and an example question; remove "shows people stopped watching partway through" from the `unwatched` Roadmap line, keeping the per-person part
- [x] 5.2 `openspec/ideas.md`: remove the "Stopped partway" notes under `unwatched`, with a line saying `show-progress` covers it, and add `show-progress` to "Where things stand"
- [x] 5.3 `website/index.html`: the new skill in the Watching group with an icon, a description, an example request and a terminal demo panel using made-up data (fifteen skills)
- [x] 5.4 Bump the version to 0.29.0 in every script's `VERSION`, `plugin.json` and `marketplace.json`
- [x] 5.5 Try the skill against a real server: the whole server, one person, one show, a show nobody watches, two shows that match, and with each history source
