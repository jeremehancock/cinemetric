## 1. Check the details on a real server

- [x] 1.1 Check that movie and episode listings carry `viewCount`, `viewOffset`, `lastViewedAt`, `contentRating`, `titleSort`, `duration`, `guid`, `thumb` and, per media version, `videoResolution`, `videoCodec`, `audioCodec`, `audioChannels`, `container` and `bitrate`; and that show listings carry `leafCount`, `viewedLeafCount`, `lastViewedAt`, `guid` and `thumb`
- [x] 1.2 Check that `/library/collections/{id}/children` lists seasons and episodes (not only whole titles) with rating keys that link back to their show, so show and episode rows can pick up a collection holding a season or episode (the test server's 205 collections hold only movies, so this couldn't be seen; children are matched by rating key against the show, season and episode keys from the episode listing, as `collections-and-playlists` does, which doesn't depend on what fields a season child carries)
- [x] 1.3 Build a small test workbook by hand (inline strings, numbers, a date, a frozen bold header with filters, a title `=1+1`, a title containing `</t>`, accented titles) and open it in Excel or LibreOffice and in Google Sheets: no repair or link warnings, text shown as written, nothing run, dates and numbers sort properly (done in LibreOffice: every hostile title shown as written and nothing run; Excel and Google Sheets left for the user to open)
- [x] 1.4 Run the five reports with the export's options on the real server and note how long each takes, and the exact field names for the `Server` tab (update, remote access, CPU and memory, stream totals and bandwidth, settings, `worth_a_look`, library scan dates)
- [x] 1.5 Update the spec and design if any path, field or behavior differs from what they say

## 2. Script: library read

- [x] 2.1 Create `plugins/cinemetric/skills/export/scripts/export.py` with copies of the shared helpers (`load_config`, `validate_url`, `PlexClient`, `clean`, `media_deletion_allowed`, `data_dir`, `ensure_private_dir`), `ALLOWED_PATHS` for the six Plex paths, and its own file writer under a new name (not a changed copy of the shared `write_page`, which always creates the folder and sets it to `700`)
- [x] 2.2 Options and `--check`: `--library` (with the no-match and music-only errors), `--tv shows|episodes`, `--language`, `--skip` (with the unknown value and `library` errors), `--output`, `--replace`
- [x] 2.3 Output path checks before Plex is contacted or any script is run: default name and library slug, an existing folder, an `.xlsx` file in an existing folder, `FILE_EXISTS`, `BAD_OUTPUT`, `~` expanded
- [x] 2.4 Listings: movies, shows and episodes in pages of 500, a library that can't be read noted in `unavailable`, and stopping without a file when no library can be read
- [x] 2.5 `Library` columns for movies and episodes: best version Plex can still find, size of every version still there, `Versions`, `Unavailable`, length, dates, watched status
- [x] 2.6 Show rows: episode totals, most common media values with the tie rules, `Episodes`, `Episodes unavailable`, `Episodes watched` and `Watched` from `leafCount` and `viewedLeafCount`
- [x] 2.7 Collections: list and children per library, mapping collections that hold shows, seasons or episodes onto the right rows, and failures noted without stopping
- [x] 2.8 Row order for the `Library` tab, and the `File missing`, `Unmatched` and `No poster` issues from the same listings

## 3. Script: other tabs

- [x] 3.1 Running the reports side by side as the dashboard does (sibling skill folders, same Python, 30-minute limit, non-JSON output treated as a failure), only for tabs not skipped, with the options in the spec, `--library` passed on, and `episode_gaps.py` left out when no TV library is included
- [x] 3.2 `Server` tab: the sections from `server_health.py` (no stream names, no public address, unavailable parts, fixed labels for settings and `worth_a_look` kinds) and the libraries table from `library_report.py` with scan dates
- [x] 3.3 `Issues` tab: duplicates, titles in more than one library and low-resolution titles from `library_report.py`, the order, and notes for examples left out
- [x] 3.4 `Episode gaps`, `Playback` and `Subtitles` tabs: rows, episode number text, language names, and the notes (`more`, `limits`, bitrate limit, `language_problem`)
- [x] 3.5 A failed report: note in each tab that needed it, `OWNER_ONLY` explained without the code, `problem` in the summary

## 4. Script: workbook and summary

- [x] 4.1 Workbook writer with `zipfile`: content types, workbook with the tabs in order, styles (bold header, date format), one sheet per tab with frozen header and filters, inline strings, numbers, dates as date numbers, notes after an empty row
- [x] 4.2 Text safety: cleaning every text value, removing characters not allowed in XML, escaping `&`, `<`, `>` and quotes, and never writing a formula, hyperlink or external link
- [x] 4.3 Writing to a `600` temporary file, then moving it into place (replacing in the data folder or with `--replace`, otherwise failing if the file appeared), never touching a user-named folder's permissions, and removing the temporary file on failure
- [x] 4.4 The JSON summary (`tabs`, `skipped_tabs`, `libraries` and the rest), `media_deletion_allowed` from `/:/prefs`, and no titles, show or collection names in it

## 5. SKILL.md

- [x] 5.1 Write `plugins/cinemetric/skills/export/SKILL.md`: when to use it, how to call the script (`--library` when the user names one, `--tv episodes` when they want episodes, `--skip` when they want a quicker export or fewer tabs, `--language` when they name a subtitle language, `--output` when they name a place, `--replace` only after the user agrees to replace an existing file), saying beforehand that it can take a few minutes, what to say afterwards (the full path, the tabs and their rows, tabs that couldn't be built and why, whose watched status it is, offering to save it somewhere easier to find when it went to the data folder), explaining `FILE_EXISTS` and `BAD_OUTPUT`, not reading the workbook back into the chat unless asked, the media deletion line, and the rules every `SKILL.md` carries
- [x] 5.2 `allowed-tools` lists only `Read` and the script

## 6. Tests

- [x] 6.1 Add made-up fixtures in `tests/fixtures/export/` (no real names; titles from the public domain or invented): Plex listings and collections including titles with commas, quotes, accents, leading `=`, `+`, `-` and `@`, and XML-breaking text, a movie with two versions, a missing file, a mixed-quality show, unmatched and posterless titles, and collections holding a movie, a season and an episode; and report outputs for each of the five scripts in their real shapes, including a stream with a person's name and a failed report
- [x] 6.2 Add `tests/test_export.py` covering everything listed for `export` in the testing spec, including unzipping the workbook and checking every part is valid XML, listed in the content types, and has no `<f>` (formula), hyperlink or external link parts
- [x] 6.3 List the new script in `tests/helpers.py`, and run `python3 tools/shared_helpers.py`, so the cross-script security, shared helper and media deletion checks run against it
- [x] 6.4 Run the full test suite and fix anything that fails

## 7. Docs, website and version

- [x] 7.1 README: new row in the Skills table; remove `export` from the Roadmap (and the line about the last group still waiting for its skill)
- [x] 7.2 `openspec/ideas.md`: remove the `export` notes and the line about new skills per group, and add an `export` entry under updates to existing skills for possible later additions (a `--with-people` option with the privacy catch, and more tabs such as unwatched titles or collections)
- [x] 7.3 `website/index.html`: the new skill in the **Your server** group, with a description, an example request and a terminal demo panel using made-up data (eighteen skills)
- [x] 7.4 Bump the version to 0.32.0 in every script's `VERSION`, `plugin.json` and `marketplace.json`
- [x] 7.5 Try the skill against a real server: the default export, `--tv episodes`, one library, `--skip playback --skip subtitles`, `--output` to an existing folder and to a file that exists (with and without `--replace`), and `--check`; open the workbook in a spreadsheet program, note how long it took, and note anything the tests don't cover (done on 2026-10-09: every option behaved as specified; the full export took about 2 minutes 20 seconds, without playback and subtitles about 40 seconds, and the episode workbook (18,939 rows, 1.7 MB) opened in LibreOffice in 3 seconds. Excel and Google Sheets weren't available here and are left for a person to open)

## 8. Changes after review

- [x] 8.1 Leave out everything about what is streaming now: the stream counts and bandwidth, and `transcode_too_slow` items (spec, design, script, tests)
- [x] 8.2 Put movies and TV on separate `Movies` and `TV Shows` tabs, each with only the columns that fit it, present only when a library of that kind is included, with a note when one of its libraries couldn't be read (spec, design, script, tests, SKILL.md, README, website)
- [x] 8.3 Leave out CPU and memory use, and the Worth a look items drawn from moment-to-moment readings (`high_cpu`, `high_memory`, `task_not_progressing`) (spec, design, script, tests, SKILL.md, README)
- [x] 8.4 Website: a screenshot of a real workbook's Movies tab (made-up titles, opened in LibreOffice) instead of the terminal demo, taken by the new `tools/export_screenshot.py`; column widths now leave room for each column name's filter button
