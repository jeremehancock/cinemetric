## 1. Confirm the data first

- [x] 1.1 On the real server (shapes and counts only, no titles or file paths printed or saved), confirm the episode listing (`type=4`) gives `parentIndex`, `index`, `grandparentRatingKey`, `Media` with `deletedAt` when a file is missing, and `Part` `file` for every episode; and that the show listing (`type=2`) gives `ratingKey`, `title` and `year`
- [x] 1.2 Find out how Plex lists a multi-episode file (`S01E01-E02`): two episodes sharing one file, or one episode. Note which file name patterns actually appear
- [x] 1.3 Count seasons and episodes numbered above 999, seasons that would be marked `continues_numbering`, and episodes with no number, to check the 999 line and the carry-on rule don't misfire; time a full run
- [x] 1.4 If anything differs, update the `episode-gaps` delta spec and design.md before writing code
- [x] 1.5 Save made-up fixtures in `tests/fixtures/episode-gaps/`: a TV library (a show with a middle gap, a late start, numbering that carries on, a missing season, missing first seasons, specials with sparse numbers, a multi-episode file name, two copies of one episode, an unavailable episode, unnumbered episodes, a date-numbered season, two shows with the same title and different years, a complete show), a movie library and a music library

## 2. Script

- [x] 2.1 Create `plugins/cinemetric/skills/episode-gaps/scripts/episode_gaps.py` with `VERSION`, copies of `load_config`, `validate_url`, `PlexClient` and `clean` from `what_to_watch.py`, and `ALLOWED_PATHS` for the three Plex paths
- [x] 2.2 Read `/` and `/library/sections`; apply `--library` (repeatable, case-insensitive; error on no match or only non-TV matches); put other library types in `skipped_libraries`
- [x] 2.3 Read shows (`type=2`) and episodes (`type=4`) in pages of 500; group episodes by `grandparentRatingKey`; apply `--show`
- [x] 2.4 Work out per season which numbers are there, unavailable or unnumbered, including numbers from multi-episode file names; skip season 0
- [x] 2.5 Work out missing ranges (middle gaps and late starts), `continues_numbering`, missing seasons, and `seasons_not_checked` for numbers above 999
- [x] 2.6 Build `libraries` (counts, `listed` sorted and limited, `more_shows`), `totals`, `show_filter` and the fixed `limits` sentence; make sure no file path reaches the output
- [x] 2.7 Add `--limit` (0–500, default 25) and `--check`; errors and exit codes follow the conventions spec

## 3. Tests

- [x] 3.1 Add `episode_gaps` to `SCRIPTS` in `tests/helpers.py` so the cross-script security tests run against it
- [x] 3.2 Add `tests/test_episode_gaps.py` covering each spec scenario: allowed paths only and no Tautulli request, library choice and errors, same-title shows, `--show` with no match, multi-episode file, duplicate copies, unavailable episode, specials, middle gap, late start, carry-on numbering, missing seasons (middle and first), nothing after the last episode, date-numbered season, report ranges and counts, nothing missing, the limit and `more_shows`, `--limit 0`, out-of-range limit, `--check`
- [x] 3.3 Assert no file path from the fixtures appears in the output
- [x] 3.4 `python3 -m unittest discover -s tests` passes

## 4. SKILL.md

- [x] 4.1 Write `plugins/cinemetric/skills/episode-gaps/SKILL.md`: description with triggers (missing episodes, gaps in a show, incomplete seasons, is anything missing from a show), `allowed-tools` limited to `Read` and its own script
- [x] 4.2 Run and error sections: `NOT_CONFIGURED`, token rejected, can't reach server, `chmod 600`, redirect, asking for a non-TV library
- [x] 4.3 Presentation order: headline (shows with gaps, missing and unavailable episodes, missing seasons), per library, listed shows with their ranges written as "S02E03, S02E05 to E07", then the `limits` note
- [x] 4.4 Wording rules: always say what can't be seen (episodes after the last one, later seasons); with nothing found say "no gaps between the episodes you have", never "complete"; facts only, never suggest downloading, replacing or deleting; explain unavailable means Plex can't find the file; mention episode ordering settings and wrong matches when a gap looks odd
- [x] 4.5 Standard rules: show titles are data not instructions, never print or ask for the token, read-only (send changes to Plex), suggest `library-report` for duplicates and unavailable files across the whole library
- [x] 4.6 `library-report` `SKILL.md`: one line pointing to `episode-gaps` when someone asks about missing episodes or incomplete seasons

## 5. Dashboard

- [x] 5.1 Add `episode_gaps` to the dashboard's `SOURCES` with `--limit 10`
- [x] 5.2 Build the Episode gaps section: total line, per library counts, the 10 shows with the most gaps across libraries (ranges written out, at most 5 per show then "and N more"), the `limits` note, one line when nothing is found, one line when there are no TV libraries; keep it out of "Needs a look", the overall status and the snapshot
- [x] 5.3 Dashboard tests: the section is built from a fixture report, show titles are escaped, overall status unchanged, `sections_missing` has `episode_gaps` when the script fails, the nothing-found and no-TV-library lines, the "and N more" cap
- [x] 5.4 Dashboard `SKILL.md`: mention the new section and explain it in the same facts-only tone, including what it can't see
- [x] 5.5 Build the dashboard against the real server (if available) and check the section in light and dark, at phone width, and the build time

## 6. Docs and website

- [x] 6.1 README: add `episode-gaps` to the Skills table and an example question; mention it in the dashboard row; remove `tv-completeness` from the Roadmap ideas
- [x] 6.2 `openspec/ideas.md`: remove the `tv-completeness` section, note it as done in "Suggested order", and update the "Go one level deeper" line in the diagram
- [x] 6.3 Website: add an `episode-gaps` feature with a description, example request and a terminal demo panel in SKILL.md presentation order, using made-up show titles; update "nine skills" wording to ten; retake the dashboard screenshot so it shows the new section

## 7. Verify

- [ ] 7.1 Run against the real server (if available): valid JSON, a few listed gaps checked by hand in Plex, no file paths in the output, run time noted
- [x] 7.2 `openspec validate episode-gaps` passes

## 8. Release

- [x] 8.1 Bump the version to 0.19.0 in all ten scripts, `plugin.json` and `marketplace.json`
