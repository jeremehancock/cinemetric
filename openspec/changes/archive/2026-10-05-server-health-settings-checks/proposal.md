## Why

`server-health` can say that someone is transcoding right now, but not whether a server setting makes
transcoding more likely or heavier. The script already downloads every setting from `/:/prefs` and
throws away all but five maintenance ones, so a handful of useful checks (hardware transcoding off, a
low remote streaming limit, video transcoding turned off) cost no extra requests. This is the
smallest item on the Roadmap and was picked as the next quick win.

## What Changes

- The script keeps a few more settings from the `/:/prefs` response it already fetches. The setting
  ids were checked against a real server (Plex on Linux, with an Intel GPU):
  - Streaming: `HardwareAcceleratedCodecs` (use hardware acceleration when available),
    `HardwareAcceleratedEncoders` (hardware-accelerated video encoding), `TranscoderCanOnlyRemuxVideo`
    (disable video stream transcoding), `WanPerStreamMaxUploadRate` (limit remote stream bitrate, in
    kbps, 0 means no limit), `WanTotalMaxUploadRate` (total upload limit for remote streams, in kbps,
    0 means no limit) and `TranscoderTempDirectory` (only whether a custom folder is set; the path
    itself is never printed).
  - Maintenance: `autoEmptyTrash` (empty trash automatically after every scan).
- The streaming settings appear in a new part of the report, `server.streaming_settings`. The trash
  setting joins `background.maintenance_settings`.
- Three new `worth_a_look` kinds, all stated as facts about how the server is set up:
  - `hardware_transcoding_off`: hardware acceleration is turned off.
  - `video_transcoding_off`: the server is set to never transcode video.
  - `remote_stream_limit_low`: the per-stream remote limit is set below 8 Mbps, the lowest choice Plex
    itself labels as 1080p.
- `SKILL.md` explains what each setting does and what it's set to. It never tells the user to change
  a setting, matching the "facts, not advice" rule in `openspec/ideas.md`.
- README: the `server-health` Roadmap item is removed and the skills table mentions settings checks.
  Website: the server-health feature list mentions streaming settings. `openspec/ideas.md`: the
  `server-health` section is removed, since it's done.
- Bug fix found while testing: Plex sends `-1` for an update check that has never run, and the script
  showed it as a date in 1969. Dates of 0 or below now come out as `null` ("never"). The same date
  helper in `watch_activity.py` gets the same fix.
- Version bump to 0.11.0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `server-health`: "Only maintenance settings are kept" is renamed to "Only selected settings are
  kept" and widened to the new list; "Partial results instead of failure" adds streaming settings as
  an optional part; "Things worth a look" adds the three new kinds.

## Impact

- `plugins/cinemetric/skills/server-health/scripts/server_health.py`: more ids kept from `/:/prefs`,
  `/:/prefs` read once for both settings parts, new `streaming_settings` part and three new
  `worth_a_look` kinds. No new Plex paths.
- `plugins/cinemetric/skills/server-health/SKILL.md`: the new part and flags, explained as facts.
- `tests/test_server_health.py` and its sample `/:/prefs` fixture.
- `README.md`, `website/index.html`, `openspec/ideas.md`.
- `watch_activity.py`: the same date fix.
- `VERSION` in all six scripts, `plugin.json` and `marketplace.json`.
- The dashboard is unchanged: it ignores `worth_a_look` kinds it doesn't know.
