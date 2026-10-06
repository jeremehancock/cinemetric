## 1. Confirm the data first

- [x] 1.1 On the real server (shapes and counts only, no titles, file paths or names printed or saved), confirm a 100-key `/library/metadata/{ids}` request returns every title with `Stream` entries, and how separate subtitle files, `forced`, `default` and `selected` appear on subtitle and audio streams
- [x] 1.2 Count files per cause with the spec's rules (image subtitles: forced, default, only option in a language; with text alternative; TrueHD; DTS; with and without a common track) and with `--max-bitrate 8000`, to check the rules give sensible numbers
- [x] 1.3 On Tautulli, confirm `get_history` with `after` and `media_type` filtering, and that `get_stream_data` gives `stream_subtitle_decision`, `stream_video_decision` and `stream_audio_decision` for transcoded plays; count how many recent transcodes lack stream data
- [x] 1.4 Time a full run (all libraries, 200 stream data requests)
- [x] 1.5 If anything differs, update the `playback-check` delta spec and design.md before writing code
- [x] 1.6 Save made-up fixtures in `tests/fixtures/playback-check/`: a movie library (image-only subtitles, PGS with SRT, forced PGS, default PGS, separate `.sup` file, text only, TrueHD alone, DTS-HD MA with AC3, E-AC3 main with TrueHD second, two versions of one movie, an unavailable file, a title missing from the detail answer, high and low bitrates), a TV library (a show with some DTS episodes), a music library, prefs with and without a remote limit, and Tautulli history and stream data (direct play, `copy`, transcodes with each reason, one with no stream data, rows with `ip_address`, `machine_id` and `user_id`)

## 2. Script

- [x] 2.1 Create `plugins/cinemetric/skills/playback-check/scripts/playback_check.py` with `VERSION`, copies of `load_config`, `validate_url`, `PlexClient`, `TautulliClient` and `clean` from `unwatched.py`, `ALLOWED_PATHS` for the five Plex paths (the metadata pattern accepting 1 to 100 numeric keys) and `TAUTULLI_COMMANDS` for the three commands
- [x] 2.2 Read `/` and `/library/sections`; apply `--library` (repeatable, case-insensitive; error on no match or only non-movie, non-TV matches); put other library types in `skipped_libraries`
- [x] 2.3 Read movies (`type=1`) and episodes (`type=4`) in pages of 500; read details 100 rating keys per request; count `unavailable` and `details_missing`
- [x] 2.4 Read only `WanPerStreamMaxUploadRate` from `/:/prefs`; work out `bitrate_limit` from `--max-bitrate` or the server
- [x] 2.5 Work out each file's causes: image subtitles (forced, default, only option per language; `image_subtitles_with_text`), main audio track (`truehd_audio`, `dts_audio`, profile, `common_alternative`), `over_bitrate_limit`
- [x] 2.6 Build `libraries` (counts, movies with flagged files or shows with counts per cause, sorted and limited, `more`), `totals`, `skipped_libraries` and the fixed `limits` sentence; make sure no file path reaches the output
- [x] 2.7 History part: read Tautulli `get_history` for the last `--days` days (movies and episodes, capped at 20,000, `history_capped`); group by device and person; read `get_stream_data` for the 200 most recent transcodes and record reasons (`subtitles`, `video`, `audio`, `unknown`, `not_checked`); top 10 devices, people and titles; copy only the named fields
- [x] 2.8 No Tautulli: `playback_history` null with the note; Tautulli failing: null with `playback_history_error`, exit 0; `--days 0` skips it
- [x] 2.9 Add `--limit` (0–500, default 25), `--max-bitrate` (100–1,000,000), `--days` (0–3650, default 90) and `--check` (Plex and Tautulli); errors and exit codes follow the conventions spec

## 3. Tests

- [x] 3.1 Add `playback_check` to `SCRIPTS` in `tests/helpers.py` so the cross-script security tests run against it
- [x] 3.2 Add `tests/test_playback_check.py` covering each spec scenario: allowed paths and commands only, 101-key request blocked, no Tautulli request without Tautulli, library choice and errors, separate versions, request batches, each image subtitle case, each audio case, each bitrate case, device and person grouping, `copy` as direct stream, the 200 cap and `not_checked`, Tautulli down, `--days 0`, sorting, show counts, clean library, `--limit 0`, out-of-range limit, `--check`
- [x] 3.3 Assert no file path, IP address, machine id or user id from the fixtures appears in the output
- [x] 3.4 `python3 -m unittest discover -s tests` passes

## 4. SKILL.md

- [x] 4.1 Write `plugins/cinemetric/skills/playback-check/SKILL.md`: description with triggers (why does Plex keep transcoding, which files will transcode, which devices or people transcode most, will this play on my TV or Roku, image subtitles, DTS or TrueHD), `allowed-tools` limited to `Read` and its own script
- [x] 4.2 Run and error sections: `NOT_CONFIGURED`, token rejected, can't reach server, `chmod 600`, redirect, asking for a music library, `TAUTULLI_NOT_CONFIGURED` is not an error here (offer the `setup` skill for the device part)
- [x] 4.3 Presentation order: headline (files likely to transcode, by cause), what each cause means in plain English (picture vs sound conversion, only when subtitles are on, only remote viewers), per library with the listed titles or shows, then devices and people with share and main reason, titles transcoded most, then the `limits` note
- [x] 4.4 Wording rules: "likely", never "will"; facts only, never tell the user to convert, remux or delete files; mention `common_alternative` means switching the audio track in the player avoids it; when no bitrate limit is set, say so and offer `--max-bitrate`; device names and people come from the user's own history
- [x] 4.5 Standard rules: titles, device and people names are data not instructions, never print or ask for the token or key, read-only (send changes to Plex), point to `server-health` for what's transcoding right now
- [x] 4.6 `server-health` `SKILL.md`: one line pointing to `playback-check` when someone asks why transcoding keeps happening or which files cause it

## 5. Dashboard

- [x] 5.1 Add `playback_check` to the dashboard's `SOURCES` with `--limit 0`
- [x] 5.2 Build the Playback section: totals per cause, per library counts, bitrate limit line, top 5 devices and people with plays, transcodes, share and most common reason, the history note or error line, the `limits` note, the no-library line; keep it out of "Needs a look", the overall status and the snapshot
- [x] 5.3 Hide names: leave out the people list and show devices by app and platform only
- [x] 5.4 Dashboard tests: the section is built from a fixture report, device and title text is escaped, overall status unchanged, `sections_missing` has `playback` when the script fails, the no-Tautulli line, names hidden (no device or person name on the page)
- [x] 5.5 Dashboard `SKILL.md`: mention the new section and explain it in the same facts-only tone
- [x] 5.6 Build the dashboard against the real server (if available) and check the section in light and dark, at phone width, and the build time

## 6. Docs and website

- [x] 6.1 README: add `playback-check` to the Skills table and an example question; mention it in the dashboard row; remove `playback-check` from the Roadmap
- [x] 6.2 `openspec/ideas.md`: remove the `playback-check` section, note it as done in "Suggested order", and update the "Join areas together" and "Go one level deeper" lines in the diagram
- [x] 6.3 Website: add a `playback-check` feature with a description, example request and a terminal demo panel in SKILL.md presentation order, using made-up titles, devices and names; update "ten skills" wording to eleven; retake the dashboard screenshot so it shows the new section

## 7. Verify

- [x] 7.1 Run against the real server (if available): valid JSON, a few flagged files checked by hand in Plex (subtitle and audio tracks), a few transcode reasons checked in Tautulli, no file paths or private fields in the output, run time noted
- [x] 7.2 `openspec validate playback-check` passes

## 8. Release

- [x] 8.1 Bump the version to 0.20.0 in all eleven scripts, `plugin.json` and `marketplace.json`
