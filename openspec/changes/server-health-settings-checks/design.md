## Context

`server_health.py` already requests `/:/prefs` (the server's full settings list) and keeps five
settings through the `PREF_IDS` table, discarding the rest. That list holds more than settings: it
also carries values that must never be printed (for example the server's online token), which is why
the spec says "keep only these" instead of "drop these".

The setting ids below were read from a real server on 2026-10-05 (Plex on Linux with an Intel Alder
Lake GPU), printing only ids, labels, types and on/off or number values:

| id | label in Plex | type | default |
| --- | --- | --- | --- |
| `HardwareAcceleratedCodecs` | Use hardware acceleration when available | bool | on |
| `HardwareAcceleratedEncoders` | Use hardware-accelerated video encoding | bool | on |
| `TranscoderCanOnlyRemuxVideo` | Disable video stream transcoding | bool | off |
| `WanPerStreamMaxUploadRate` | Limit remote stream bitrate | int (kbps) | 0 (no limit) |
| `WanTotalMaxUploadRate` | External network total upload limit (kbps) | int | 0 (no limit) |
| `TranscoderTempDirectory` | Transcoder temporary directory | text | empty |
| `autoEmptyTrash` | Empty trash automatically after every scan | bool | on |

The choices Plex offers for `WanPerStreamMaxUploadRate` are labelled 4K (25 to 40 Mbps), 1080p (8 to
20 Mbps), 720p (3 and 4 Mbps), 480p (1.5 and 2 Mbps) and two lower kbps options.

## Goals / Non-Goals

**Goals:**
- Report a few settings that explain or affect transcoding, plus the trash setting, using the request
  the script already makes.
- Flag the clearest cases as facts, worded so Claude describes the setting rather than recommending a
  change.

**Non-Goals:**
- Telling the user to change settings. The skill stays read-only and advice-free on settings.
- Linking settings to live streams (for example "this remote stream is transcoding because of your
  limit"). Possible later, but it needs care to avoid claiming a cause the script can't prove.
- Per-device GPU and CPU transcode limits. Their ids include a device-specific prefix
  (`_<device>-TranscodeCountLimit`), so they can't go in a fixed table.
- Showing the new settings on the dashboard.
- Checking disk space for the transcoder folder. Plex doesn't report it through this interface.

## Decisions

**Fetch `/:/prefs` once, split into two parts.** Streaming settings describe how video is delivered,
so they sit under `server` next to remote access. The maintenance settings stay in
`background.maintenance_settings` with the same keys, so nothing that already reads them breaks.
The response is fetched once and both parts read from it; if the fetch fails, both parts are `null`
with the same reason. Alternative: one combined `settings` part. Rejected because it moves existing
keys and mixes two topics the report presents in different sections.

**Two tables instead of one.** `PREF_IDS` becomes `MAINTENANCE_PREFS` and `STREAMING_PREFS`, each
mapping a Plex id to its report name. The conversion rule stays the same: bool settings become
booleans, names ending in `_hour`, `_seconds` or `_kbps` become integers.

**Temporary folder as a yes/no.** Whether a custom folder is set is useful (the default puts
transcoding files inside Plex's own data folder, often on the system disk). The path itself adds
little and reveals the machine's folder layout, so only `true`/`false` is kept. This is handled as a
special case in the streaming table rather than a general "text settings" rule.

**Thresholds for flags.**
- `hardware_transcoding_off` only looks at `HardwareAcceleratedCodecs`, the main switch.
  `HardwareAcceleratedEncoders` is reported but not flagged, since it's an advanced setting and
  turning it off with decoding still on is a deliberate choice.
- `remote_stream_limit_low` uses below 8000 kbps because that's the boundary in Plex's own labels:
  anything lower is labelled 720p or less, so remote viewers can't get 1080p. It's tied to Plex's
  wording rather than a number Cinemetric invents.
- `autoEmptyTrash` is reported but never flagged. Some people turn it off on purpose so a drive that
  briefly disconnects doesn't wipe items from the library. Either choice is reasonable.

**Hardware settings without Plex Pass or a GPU.** Plex may leave the setting out or show it as on
even when no GPU is used. The script reports what the server says and doesn't flag missing
settings. `SKILL.md` notes that hardware transcoding needs a Plex Pass and supported hardware, and that
the setting being on doesn't prove a GPU is used (the live stream's `hardware` field shows that).

## Risks / Trade-offs

- [Ids differ between Plex versions or platforms] → Missing settings are left out and never flagged,
  so the worst case is a check that silently doesn't run. Ids were verified on a current server.
- [A flag reads as advice] → `SKILL.md` describes each flag as "here's what this setting does and
  what it's set to", in the same style as `automatic_scans_off` ("Fine if that's deliberate").
- [A new setting leaks something private] → Only fixed ids are kept, the only text setting is reduced
  to a boolean, and the existing test that a secret in `/:/prefs` never reaches the report covers the
  new code path too.
