## Why

`title-lookup` already reads every audio and subtitle track of a file from Plex (it needs them to work
out whether the file is likely to transcode), but it only prints a small part of them: the languages
of picture subtitles that cause a transcode, and the main audio track's codec when it's TrueHD or DTS.
So it can't answer simple questions about one file: which audio track is the default, whether there
are forced English subtitles, or whether Plex picked up a subtitle file that was just added next to the
video. These came up while checking a library's audio and subtitle languages, where the only way to
see the tracks the way Plex sees them was to go around Cinemetric.

## What Changes

- Each available file in a `title-lookup` report (movies and single episodes) gets two new lists:
  - `audio_tracks`: every audio track Plex knows, in Plex's order, with its language, track name,
    codec, channels, whether it's the file's default track, and whether it's the track Plex has
    selected for the signed-in account.
  - `subtitle_tracks`: every subtitle track Plex knows, in Plex's order, with its language, track
    name, codec, whether it's forced, for the hearing impaired (SDH), the file's default, selected for
    the signed-in account, and whether it's a separate subtitle file rather than one inside the video
    file.
- Each list is capped at 50 tracks, with `audio_track_count` and `subtitle_track_count` giving the
  full numbers, so a file with dozens of tracks can't flood the report.
- Track names come from the file, so they're cleaned like every other server text (control
  characters removed, cut to 120 characters).
- No new Plex requests: the tracks come from the same `/library/metadata/{ids}` answer the script
  already reads. Whole shows still get only the episode summary; track lists appear for a movie or a
  single episode.
- The playback rules shared with `playback-check` don't change, so both skills keep giving the same
  playback answer for the same file.
- `SKILL.md` tells Claude about the new fields and when to bring them up. README's `title-lookup` row
  mentions audio and subtitle tracks.
- Version bump to 0.33.0.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `title-lookup`: "Files" adds `audio_tracks`, `subtitle_tracks` and their counts for each available
  file, with the fields above, the 50-track cap and cleaned track names.
- `testing`: "Tests check the specs" adds the track lists to what the `title-lookup` tests cover.

## Impact

- Changed: `plugins/cinemetric/skills/title-lookup/scripts/title_lookup.py` (a new function that lists
  the tracks, called from `describe_file`; `check_file`, a shared helper, is left alone).
- Changed: `plugins/cinemetric/skills/title-lookup/SKILL.md`, `README.md`.
- Changed: `tests/test_title_lookup.py` and the made-up fixtures in `tests/fixtures/title-lookup/`.
- `VERSION` in every script, `plugin.json` and `marketplace.json`.
- No new Plex paths, no Tautulli or plex.tv changes, no new destinations, nothing written to disk.
