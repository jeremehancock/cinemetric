## 1. Check the Plex and Tautulli details on a real server

- [x] 1.1 Check whether `/library/sections/{id}/all?type=1&title=...` matches part of a title, ignoring case; if not, switch to matching titles in the script (see design.md)
- [x] 1.2 Check that `/library/metadata/{id}/allLeaves` lists every episode of a show with season and episode numbers and media versions
- [x] 1.3 Check what `/status/sessions/history/all` does with `metadataItemID` for a movie and for a show, and use it as a speedup only if it gives the same entries as filtering in the script
- [x] 1.4 Check where collections, HDR / Dolby Vision color details and bit depth appear in `/library/metadata/{id}`

## 2. Script

- [x] 2.1 Create `plugins/cinemetric/skills/title-lookup/scripts/title_lookup.py` with copies of the shared helpers (`load_config`, `validate_url`, `PlexClient`, `TautulliClient`, `clean`, `media_deletion_allowed`), `ALLOWED_PATHS` for the eight paths and `TAUTULLI_COMMANDS` for `get_tautulli_info` and `get_history`
- [x] 2.2 Options and `--check`, including the errors for a missing title, bad numbers and episode options with a movie
- [x] 2.3 Finding the title: search movie and TV libraries, exact match beats "contains", narrowing by year, library and type, merging by `guid`, `matches` for none or several, `--key`
- [x] 2.4 Finding an episode with `--season` and `--episode`, and `episode_not_found`
- [x] 2.5 Title facts: type, year, libraries, added date, length, ratings, genres, collections, cleaned summary cut to 300 characters
- [x] 2.6 Files for movies and episodes, with `available` and `total_size_bytes`
- [x] 2.7 Copy `playback-check`'s cause rules and the bitrate limit; `playback_causes` per file, and `playback_summary` with detail batches of 100 and `details_missing` for shows
- [x] 2.8 Seasons for a show: episodes, unavailable, sizes, specials, first and last added
- [x] 2.9 Watching: source choice and `fallback_reason` as in `watch-activity`, Tautulli and Plex history for one title, people with plays, finished, episodes finished and furthest percent, `history_capped`, and `watching_unavailable` without failing the report
- [x] 2.10 `media_deletion_allowed` from `/:/prefs`, reading only the two allowed settings

## 3. SKILL.md

- [x] 3.1 Write `plugins/cinemetric/skills/title-lookup/SKILL.md`: when to use it, how to call the script (turning "S03E07" into `--season 3 --episode 7`), asking which title when there are several matches and running again with `--key`, presentation order (what it is, files, playback, seasons, watching), pointing to `episode-gaps` and `playback-check` for more, facts only, the media deletion line, and the rules every `SKILL.md` carries
- [x] 3.2 `allowed-tools` lists only `Read` and the script

## 4. Tests

- [x] 4.1 Add made-up fixtures in `tests/fixtures/title-lookup/` (no real names, titles from the public domain or invented)
- [x] 4.2 Add `tests/test_title_lookup.py` covering everything listed for `title-lookup` in the testing spec
- [x] 4.3 Add a shared test that runs the same made-up files through `title_lookup.py` and `playback_check.py` and expects the same causes
- [x] 4.4 Add the new script to the cross-script security and media deletion tests
- [x] 4.5 Run the full test suite and fix anything that fails

## 5. Docs, website and version

- [x] 5.1 README: new row in the Skills table and an example question; remove `title-lookup` from the Roadmap
- [x] 5.2 `openspec/ideas.md`: remove the `title-lookup` notes
- [x] 5.3 `website/index.html`: the new skill with a description, an example request and a terminal demo panel using made-up data (thirteen skills)
- [x] 5.4 Bump the version to 0.27.0 in every script's `VERSION`, `plugin.json` and `marketplace.json`
- [x] 5.5 Try the skill against a real server: a movie, a movie in two libraries, a show, an episode, several matches and no match (the test server has no title in two libraries, so that case is covered by the tests only)
