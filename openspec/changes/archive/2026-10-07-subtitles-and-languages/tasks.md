## 1. Check the Plex details on a real server

- [x] 1.1 Check whether `/:/prefs` has a default audio or subtitle language (it doesn't: only `LanguageInCloud`; see design.md)
- [x] 1.2 Check which language fields audio and subtitle tracks have in `/library/metadata/{ids}` (`languageCode`, `languageTag`, `language`, plus `selected`, `default`, `forced`, `hearingImpaired`)
- [x] 1.3 Check that library sections have a `language` attribute
- [x] 1.4 Check how a separate subtitle file (an `.srt` next to the video) appears in the detail listing, if a test file can be found; otherwise rely on the made-up fixtures (none on the test server: covered by fixtures)

## 2. Script

- [x] 2.1 Create `plugins/cinemetric/skills/subtitles-and-languages/scripts/subtitles_and_languages.py` with copies of the shared helpers (`load_config`, `validate_url`, `PlexClient`, `clean`, `media_deletion_allowed`) and `ALLOWED_PATHS` for the five paths; no Tautulli client
- [x] 2.2 Options and `--check`: `--language` (up to 5, 2 or 3 letters, region dropped, bibliographic codes turned into Plex's), `--library`, `--limit` (0 to 500)
- [x] 2.3 Choosing libraries and `skipped_libraries`, with the errors for no match and only non-video libraries
- [x] 2.4 Reading movies, episodes and shows, separate media versions, `unavailable`, detail batches of 100 and `details_missing`
- [x] 2.5 A track's language and matching, the main audio track (copied from `playback-check`), full vs forced subtitles
- [x] 2.6 The user's language per library: the option, or the library's language, or `language` `null` with `language_problem`
- [x] 2.7 The three findings and `forced_only` per file
- [x] 2.8 Language summary (`audio_languages`, `subtitle_languages`, 15-language cap and `other`) and `language_names`
- [x] 2.9 Lists per finding for movies and shows, sorting, `--limit` and `more`; library counts and `totals`
- [x] 2.10 `media_deletion_allowed` from one `/:/prefs` request, reading only that setting; the `limits` sentence

## 3. SKILL.md

- [x] 3.1 Write `plugins/cinemetric/skills/subtitles-and-languages/SKILL.md`: when to use it, how to call the script (turning "Spanish subtitles" into `--language es`), saying which language was assumed and offering `--language`, presentation order (foreign audio with no subtitles first, then no subtitles in your language, then language not set, then the summary), explaining forced tracks in plain words, pointing to `playback-check` for transcoding, facts only, the media deletion line, and the rules every `SKILL.md` carries
- [x] 3.2 `allowed-tools` lists only `Read` and the script

## 4. Tests

- [x] 4.1 Add made-up fixtures in `tests/fixtures/subtitles-and-languages/` (no real names; titles invented or from the public domain), including a separate subtitle file, a forced-only film, a dub, tracks with no language and a library with no language
- [x] 4.2 Add `tests/test_subtitles_and_languages.py` covering everything listed for `subtitles-and-languages` in the testing spec
- [x] 4.3 Add a test that runs the same made-up files through `subtitles_and_languages.py` and `playback_check.py` and expects the same main audio track
- [x] 4.4 Add the new script to the cross-script security and media deletion tests (`tests/test_security.py`, `tests/test_media_deletion.py`, `tests/helpers.py`)
- [x] 4.5 Run the full test suite and fix anything that fails

## 5. Docs, website and version

- [x] 5.1 README: new row in the Skills table and an example question; remove `subtitles-and-languages` from the Roadmap
- [x] 5.2 `openspec/ideas.md`: remove the `subtitles-and-languages` notes and add it to the "done" line
- [x] 5.3 `website/index.html`: the new skill in the "Your library" group, right after `playback-check`, with a description, an example request and a terminal demo panel using made-up data (fourteen skills); check the group still lays out well at phone, tablet and desktop widths
- [x] 5.4 Bump the version to 0.28.0 in every script's `VERSION`, `plugin.json` and `marketplace.json`
- [x] 5.5 Try the skill against a real server: the default language, `--language es`, one library with `--library`, and `--limit 0`
