## 1. Audio quality in the script

- [x] 1.1 Add the lossless and lossy codec lists (lowercase, plus "starts with `dsd`") and a helper that groups one codec as lossless, lossy or other
- [x] 1.2 Add a helper that classifies one track from its counted copies (reusing `copies()` rules: no `deletedAt`, no `proxyType`): its group, total size, and for lossy tracks the highest lossy bitrate and lossy codec
- [x] 1.3 Build the `audio_quality` section: `lossless` / `lossy` / `other` tracks and GB, `lossy_bitrate` buckets, album groups by `parentRatingKey`, `mixed_examples` (most lossy tracks first, then title) and `lossy_examples` (`tracks`, most common `codec`, average `kbps`, lowest first, unknown last, then title)
- [x] 1.4 Add `--music-examples N` (default 15, clamped to 0-500) and apply it to both example lists
- [x] 1.5 Music libraries: download artists with `get_all(sid, TYPE_ARTIST)`, take the artist count from it, and add `missing_artist_image_count` / `missing_artist_image_examples` to housekeeping

## 2. Tests

- [x] 2.1 Add offline tests in `tests/test_library_report.py` for each new spec scenario: FLAC and MP3 counts and GB, capital codec names, unrecognised or missing codec, a track in two formats, a copy Plex can't find, bitrate buckets including unknown, mixed album, all-MP3 album average and codec, lossy example ordering, empty library, example limit and clamping
- [x] 2.2 Housekeeping tests: album with no cover, artist with no photo, movie libraries have no artist fields
- [x] 2.3 Update the existing music tests (mock `get_all` now also serves artists) and check movie and photo libraries have no `audio_quality`; only allowed Plex paths are requested
- [x] 2.4 `python3 -m unittest discover -s tests` passes

## 3. Tell Claude about it

- [x] 3.1 `SKILL.md`: add lossless/lossy music, FLAC vs MP3, music bitrate and missing album art or artist photos to the `description` triggers, and document `--music-examples` in the run section
- [x] 3.2 `SKILL.md`: describe the `audio_quality` fields and the new housekeeping fields; for music, call missing posters "albums without cover art"
- [x] 3.3 `SKILL.md`: add music audio quality to the per-library section (share lossless by tracks and storage, lossy bitrate split) and mixed / all-lossy albums to "Worth a look"; lead with it when that's what the user asked
- [x] 3.4 `SKILL.md`: these are file formats, not a guarantee of sound quality; only list albums, never suggest re-ripping, replacing, converting or where to get files

## 4. Docs

- [x] 4.1 README: remove the `library-report` music item from Roadmap "Ideas for later"
- [x] 4.2 `openspec/ideas.md`: remove the `library-report` music note
- [x] 4.3 Website: add lossless vs lossy music to the library-report feature list in `website/index.html`

## 5. Verify

- [x] 5.1 Run against the real server: output is valid JSON, existing fields unchanged, and the music library shows about 5,674 lossless and 855 lossy tracks with 2 mixed albums (as found on 2026-10-06)
- [x] 5.2 Run `dashboard.py` against the new report and confirm the page still builds unchanged
- [x] 5.3 `openspec validate library-report-music-details` passes

## 6. Release

- [x] 6.1 Bump the version to 0.16.0 in all eight scripts, `plugin.json` and `marketplace.json`
