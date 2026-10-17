## 1. Check the details on a real server

- [x] 1.1 Using the configured Plex connection (a `GET` of `/library/metadata/{id}` only), look at the audio and subtitle streams of a title with an embedded subtitle and a separate subtitle file (Black Doves S01E01 with its Bazarr `.en.hi.srt`, or Mission: Impossible - Ghost Protocol with its full and forced `.srt` files), and of one with several audio tracks (Pom Poko): confirm separate files have a `key` and embedded tracks don't, and check `hearingImpaired`, `forced`, `default`, `selected`, `channels`, `title`, `languageTag` and `languageCode`
- [x] 1.2 Note whether Plex gives the separate subtitle file's name anywhere in the stream; don't print it either way (record the answer in the design's Non-Goals)
- [x] 1.3 Update the spec and design if any field or behavior differs from what they say

## 2. Script

- [x] 2.1 Add `list_tracks(media)` to `title_lookup.py`: audio and subtitle streams across all parts in Plex's order, the fields in the spec, cleaned text, at most 50 of each, and the two counts
- [x] 2.2 Call it from `describe_file` only for available files whose details were read, leaving `check_file` and every other shared helper unchanged (`python3 tools/shared_helpers.py` still passes)

## 3. SKILL.md and README

- [x] 3.1 `SKILL.md`: add `audio_tracks`, `subtitle_tracks` and their counts to the field list; tell Claude to bring the tracks up when the user asks about audio, languages, dubs or subtitles for the title (or about a track being picked up or being the default), and otherwise mention them only briefly, such as "Japanese and English audio, English subtitles"; to write language codes as names; to explain the difference between `default` and `selected` when they point at different tracks; that `hearing_impaired` false isn't proof (the track name may still say SDH); to say when a list stopped at 50; and to point library-wide language questions to `cinemetric:subtitles-and-languages`
- [x] 3.2 README: the `title-lookup` row mentions each file's audio and subtitle tracks

## 4. Tests

- [x] 4.1 Extend the made-up fixtures in `tests/fixtures/title-lookup/` with a file holding two audio tracks (one default, one selected), an embedded forced subtitle, a separate SDH subtitle with a `key`, a track name with control characters over 120 characters, and a file with more than 50 subtitle tracks
- [x] 4.2 Add tests to `tests/test_title_lookup.py` for every scenario in the `title-lookup` "Files" delta, including no lists for unavailable files, files without details and whole shows, and unchanged playback causes
- [x] 4.3 Run the full test suite and fix anything that fails

## 5. Version and real-server try

- [x] 5.1 Bump the version to 0.33.0 in every script's `VERSION`, `plugin.json` and `marketplace.json`
- [x] 5.2 Try `title-lookup` against the real server on the titles from 1.1 and confirm the tracks match what Plex shows in its player's audio and subtitle menus (done on 2026-10-17 against Plex's own track labels, the names its player menus show, for Pom Poko, Mission: Impossible - Ghost Protocol and Black Doves S01E01: every track, flag and separate file matched; the player menus themselves are left for a person to open)
