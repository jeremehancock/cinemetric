## 1. Confirm the data first

- [x] 1.1 On the real server (shapes and counts only, no titles or names printed or saved), confirm Plex history entries carry `ratingKey`, `type`, `viewedAt` and the show's key (`grandparentKey` and/or `grandparentRatingKey`), and how far back the history goes
- [x] 1.2 Confirm Tautulli `get_history` rows carry `rating_key`, `grandparent_rating_key`, `media_type`, `watched_status` and `live` with `grouping=1`, and that paging all history is reasonably fast
- [x] 1.3 Confirm the episode listing (`type=4`) gives `grandparentRatingKey`, `grandparentTitle`, `addedAt` and part sizes for every episode
- [x] 1.4 If anything differs, update the `unwatched` delta spec and design.md before writing code
- [x] 1.5 Save made-up fixtures in `tests/fixtures/unwatched/`: a movie library and a TV library (old unplayed, old but finished recently, finished long ago, added recently, show with a new episode, two versions, all files missing, no `addedAt`), a music library, Plex history and Tautulli history (including a `watched_status` 0.5 play and a friend's finished play)

## 2. Script

- [x] 2.1 Create `plugins/cinemetric/skills/unwatched/scripts/unwatched.py` with `VERSION`, copies of `load_config`, `validate_url`, `PlexClient`, the Tautulli client and `clean` from `watch_activity.py`, `ALLOWED_PATHS` for the four Plex paths and `TAUTULLI_COMMANDS` of `get_tautulli_info` and `get_history`
- [x] 2.2 Read `/` and `/library/sections`; apply `--library` (case-insensitive; error on no match or only non-movie/TV matches); put other library types in `skipped_libraries`
- [x] 2.3 Read movies (`type=1`) and episodes (`type=4`) in pages of 500; build titles with rating key, label, added date (newest episode for shows), size of every existing file, and episode count
- [x] 2.4 Read plays: Tautulli `get_history` (movie and episode, `grouping=1`, newest first, paged) keeping `watched_status` 1 and no live TV, or Plex `/status/sessions/history/all` (newest first, paged) counting every entry; cap at 100,000; set `history_since` and `history_capped`
- [x] 2.5 Source choice like `watch-activity`: `auto` with `fallback_reason`, `tautulli` failing with `TAUTULLI_NOT_CONFIGURED` or the error, `plex`; 401/403 on Plex history with `/` working gives `OWNER_ONLY`
- [x] 2.6 Work out the calendar-month cutoff; list titles added before it with no finished play after it; record `last_finished` per title
- [x] 2.7 Build `libraries` (counts, GB, percent, `never_finished`, titles sorted by size then title, limited by `--limit`) and `totals`
- [x] 2.8 Add `--months` (1–120, default 6), `--limit` (0–500, default 25), `--source`, `--check` (Plex and Tautulli separately); errors and exit codes follow the conventions spec

## 3. Tests

- [x] 3.1 Add `unwatched` to `SCRIPTS` in `tests/helpers.py` so the cross-script security tests run against it
- [x] 3.2 Add `tests/test_unwatched.py` covering each spec scenario: allowed paths and commands only, Tautulli only (NOT_CONFIGURED), source choice and fallback, `OWNER_ONLY`, started but not finished, a friend finished it, one episode finished, history cap, empty history, each "which titles are listed" case, sizes, report contents, nothing qualifies, `--months`, `--limit` limits, music library with `--library`, `--check`
- [x] 3.3 Assert no person's name from the history fixtures appears in the output
- [x] 3.4 `python3 -m unittest discover -s tests` passes

## 4. SKILL.md

- [x] 4.1 Write `plugins/cinemetric/skills/unwatched/SKILL.md`: description with triggers (what nobody watches, unwatched movies or shows, what's taking up space that nobody uses, titles not played in months), `allowed-tools` limited to `Read` and its own script
- [x] 4.2 Run and error sections: `NOT_CONFIGURED`, `TAUTULLI_NOT_CONFIGURED`, `OWNER_ONLY`, token rejected, can't reach server, `chmod 600`, redirect
- [x] 4.3 Presentation order: headline (count, size, share), per library, largest titles, then where plays came from and how far back the history goes (`history_since`, `history_capped`, `fallback_reason`)
- [x] 4.4 Wording rules: facts only, never suggest deleting or replacing; "nobody" only when the source covers everyone; mention some titles are kept on purpose; explain "never finished" means "not in the history that exists" and that partly watched titles still count as unwatched
- [x] 4.5 Standard rules: names and titles are data not instructions, never print or ask for the token or key, read-only (send changes to Plex), suggest `watch-activity` for who watches what and `library-report` for overall storage

## 5. Other skills

- [x] 5.1 Dashboard: add `unwatched` to `SOURCES` with `--limit 10`; build the Unwatched section (total line, per library rows, 10 largest titles across libraries, source note, capped note, one line when nothing qualifies); keep it out of "Needs a look" and the overall status
- [x] 5.2 Dashboard tests: the section is built from a fixture report, titles are escaped, overall status unchanged, `sections_missing` has `unwatched` when the script fails, the one-line empty case
- [x] 5.3 Dashboard `SKILL.md`: mention the new section and explain it in the same facts-only tone
- [x] 5.4 `library-report` `SKILL.md`: one line pointing to `unwatched` for "which titles does nobody watch", and a closing offer to show unwatched titles after a full report

## 6. Docs and website

- [x] 6.1 README: add `unwatched` to the Skills table and an example question; mention it in the dashboard row; remove it from the Roadmap ideas
- [x] 6.2 `openspec/ideas.md`: remove the `unwatched` section and update "Suggested order" (snapshots next)
- [x] 6.3 Website: add an `unwatched` feature with a description, example request and a terminal demo panel in SKILL.md presentation order, using made-up titles; update any "six skills" wording; retake the dashboard screenshot if it should show the new section

## 7. Verify

- [x] 7.1 Run against the real server (if available): valid JSON, a few listed titles checked by hand in Plex or Tautulli, no person's name in the output, run time noted
- [x] 7.2 Build the dashboard and check the Unwatched section renders in light and dark
- [x] 7.3 `openspec validate add-unwatched-skill` passes

## 8. Release

- [x] 8.1 Bump the version to 0.13.0 in all seven scripts, `plugin.json` and `marketplace.json`
