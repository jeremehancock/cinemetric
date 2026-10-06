## Why

`server-health` explains transcoding that is happening right now, but not the follow-up question:
"why does this keep happening, and which of my files will cause it?" The usual causes are few and
well known (image-based subtitles, TrueHD or DTS audio, files bigger than the remote streaming
limit), and Plex already knows every file's audio, subtitles and bitrate. This is the
`playback-check` idea from the Roadmap and `openspec/ideas.md`.

## What Changes

- A new read-only skill, `playback-check`, with one script, `playback_check.py`. For each movie and
  TV library it reads every file once and reports which files are likely to transcode on common
  devices, and why:
  - **image-based subtitles** (PGS, VobSub and similar): Plex has to draw them into the picture,
    which means converting the whole video. Files where a language has only image-based subtitles,
    and files with a forced image-based track, are counted separately, since those are the ones
    that trigger it most;
  - **TrueHD or DTS audio** as the file's main track: many TVs and streaming sticks can't play it, so
    Plex converts the sound (a light job, the picture is untouched). Files that also carry a common
    track (AC3, E-AC3, AAC) are noted;
  - **bitrate above the remote streaming limit** set on the server (or a limit the user names with
    `--max-bitrate`): remote viewers get a converted copy. With no limit set and none given, this
    check is skipped and the report says so.
- **With Tautulli set up:** which devices and which people transcode most over the last 90 days (or
  `--days N`), how often compared with their total plays, and why, read from Tautulli's details for
  each transcoded play (subtitles drawn in, video, audio). Also the titles transcoded most often.
  Without Tautulli this part is left out with a note: Plex's own history doesn't record transcodes.
- **Facts, not a device database.** The script reports these few universal causes and says "likely",
  never "will". It doesn't guess per device what a given TV supports.
- **No sampling needed.** The library listing already has each file's audio codec and bitrate.
  Subtitle tracks need each title's detail page, but Plex returns up to 100 titles per request
  (checked on the owner's server: about 210 requests and under a minute for 21,000 movies and
  episodes).
- Options: `--library NAME` (repeatable), `--limit N` (titles listed per library), `--max-bitrate
  KBPS`, `--days N`, `--check`.
- **Dashboard:** a new Playback section: totals per cause, the remote limit used, and the devices and
  people that transcode most. People's names (and device names, which often contain them) are left
  out when names are hidden. Like the Unwatched section, it doesn't change the page's overall
  status.
- `server-health` `SKILL.md` gets one line pointing to `playback-check` when someone asks why
  transcoding keeps happening (no script change).
- README: new row in the Skills table; `playback-check` comes out of the Roadmap and
  `openspec/ideas.md`. Website: a new skill with a demo panel (eleven skills).
- Version bump to 0.20.0.

## Capabilities

### New Capabilities

- `playback-check`: what the script requests from Plex and Tautulli, which libraries and files are
  checked, how each cause is detected, how transcodes are grouped by device and person and why each
  happened, what the report contains, and options.

### Modified Capabilities

- `dashboard`: "Built from the other report scripts" adds `playback_check.py`; "Rule-based page" adds
  what's hidden from the new section when names are hidden; a new "Playback section" requirement.
- `conventions`: "Connection check" adds the new script.
- `security`: "Only known destinations" gets a scenario saying `playback-check` contacts only the
  configured Plex server and Tautulli address.
- `testing`: "Tests check the specs" adds `playback-check` coverage and a scenario for a file wrongly
  flagged.
- `website`: "Shows every skill" adds `playback-check` (eleven skills).

## Impact

- New: `plugins/cinemetric/skills/playback-check/SKILL.md` and
  `plugins/cinemetric/skills/playback-check/scripts/playback_check.py` (with copies of the shared
  helpers: `load_config`, `validate_url`, `PlexClient`, `TautulliClient` and `clean`).
- New: `tests/test_playback_check.py` and made-up fixtures in `tests/fixtures/playback-check/`. The
  cross-script security tests gain the new script.
- Changed: `dashboard.py`, the dashboard `SKILL.md` and dashboard tests; the `server-health`
  `SKILL.md` (one pointer line, no script change).
- `README.md`, `openspec/ideas.md`, `website/index.html` (and the dashboard screenshot, retaken to
  show the new section).
- `VERSION` in all eleven scripts, `plugin.json` and `marketplace.json`.
- One new Plex path pattern (`/library/metadata/<ids>`, read-only) and two read-only Tautulli
  commands (`get_history`, `get_stream_data`) for this script. No new destinations.
