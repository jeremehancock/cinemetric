## 1. Script

- [x] 1.1 Replace `PREF_IDS` with `MAINTENANCE_PREFS` (the five existing settings plus `autoEmptyTrash` as `empty_trash_after_scan`) and `STREAMING_PREFS` (`HardwareAcceleratedCodecs`, `HardwareAcceleratedEncoders`, `TranscoderCanOnlyRemuxVideo`, `WanPerStreamMaxUploadRate`, `WanTotalMaxUploadRate`, `TranscoderTempDirectory`)
- [x] 1.2 Read `/:/prefs` once per report and build both parts from it; if the request fails, both parts are `null` and both are listed in `unavailable` with the same reason
- [x] 1.3 Convert values: bool settings to booleans, `_hour`/`_seconds`/`_kbps` names to integers, and `TranscoderTempDirectory` to `custom_transcoder_temp_folder` (`true` when non-empty) without keeping the path
- [x] 1.4 Add `server.streaming_settings` as the optional part "streaming settings"
- [x] 1.5 Add `hardware_transcoding_off`, `video_transcoding_off` and `remote_stream_limit_low` (with `limit_kbps`, when above 0 and below 8000) to `worth_a_look`; never flag a missing setting

- [x] 1.6 Treat Plex dates of 0 or below as "never" (`null`) in `when` and `days_ago`, so an update check that never ran isn't shown as 1969; same fix in `watch_activity.py`'s `when`

## 2. Tell Claude about it

- [x] 2.1 `SKILL.md`: list `streaming_settings` in the JSON overview and show it in the "Right now" section as a short line on how the server is set up for streaming (hardware acceleration, remote limit in Mbps or "no limit", total upload limit)
- [x] 2.2 `SKILL.md`: mention `empty_trash_after_scan` in "Background" only when it's off, as a fact (removed files stay in the library, shown as unavailable, until trash is emptied), without calling either choice wrong
- [x] 2.3 `SKILL.md`: explain the three new `worth_a_look` kinds as what the setting does and what it's set to, never "you should change it"; note hardware transcoding needs a Plex Pass and supported hardware, and that the setting being on doesn't prove a GPU is used
- [x] 2.4 `SKILL.md`: keep the "never offer to change settings" rule and make sure the new text doesn't contradict it

## 3. Docs

- [x] 3.1 README: remove the `server-health` Roadmap item and add "streaming settings" to the server-health row of the skills table
- [x] 3.2 Website: mention streaming settings in the server-health feature list in `website/index.html`, and add a streaming settings line under "Right now" in the example reply
- [x] 3.3 `openspec/ideas.md`: remove the `server-health` section and update "Suggested order"

## 4. Verify

- [x] 4.1 Update the sample `/:/prefs` fixture in `tests/` with the new settings (including a temp folder path and the existing secret) and update `test_only_maintenance_settings_are_kept`
- [x] 4.2 Tests: streaming settings read and converted; temp folder path never in the report; missing setting left out and not flagged; each new flag on and off (limit 4000 flagged, 8000 and 0 not); `/:/prefs` requested once; `/:/prefs` 403 makes both parts `null` with matching `unavailable` entries
- [x] 4.3 All tests pass: `python3 -m unittest discover -s tests`
- [x] 4.4 Run against the real server: valid JSON, existing fields unchanged, new settings match what Plex shows, no setting paths or secrets in the output (valid JSON; values match what Plex showed when the ids were checked; no flags raised on this server; no paths or tokens in the output)
- [x] 4.6 Tests that -1, 0 and empty dates come out as `null` in both scripts, and that an update check with `checkedAt` of -1 has no `last_checked`
- [x] 4.5 `openspec validate server-health-settings-checks` passes

## 5. Release

- [x] 5.1 Bump the version to 0.11.0 in all six scripts, `plugin.json` and `marketplace.json`
