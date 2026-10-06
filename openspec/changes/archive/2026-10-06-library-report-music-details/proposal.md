## Why

"Fuller music details" is on the README Roadmap. For a music library, `library-report` today gives
counts, storage, an audio codec tally, recently added albums and albums missing artwork, but it
doesn't answer the questions people who collect music actually ask: how much of my music is
lossless, which albums are only in MP3, and which albums have a mix of both?

A check against a real server (2026-10-06, 6,529 tracks) confirmed the track listing the report
already downloads includes each file's `audioCodec`, `container`, `bitrate` and its album
(`parentRatingKey`). So lossless vs lossy can be worked out with no extra requests. Bit depth and
sample rate (for spotting "hi-res" files) are not in the listing; they would need one request per
track, so they're left out.

Albums with no cover art are already counted, as the music library's "missing posters". Artists
with no photo are not, and the artist listing is one small extra request on a path the script
already uses.

## What Changes

- Each music library gets an `audio_quality` section:
  - tracks and storage that are lossless (FLAC, ALAC, WAV/AIFF, APE, WavPack, DSD, ...), lossy
    (MP3, AAC, Ogg Vorbis, Opus, WMA, ...) or an unrecognised format
  - lossy tracks split by bitrate (under 192 kbps, 192 to 255, 256 and up, unknown), since a 128 kbps
    MP3 and a 320 kbps one are quite different
  - albums that are all lossless, all lossy, or mixed
  - examples of mixed albums (with their lossless and lossy track counts) and of all-lossy albums
    (lowest bitrate first)
- Music housekeeping adds artists with no photo, with examples. Album cover counting is unchanged.
- A new `--music-examples N` option (default 15, limited to 0-500) sets how many mixed and lossy
  album examples are listed.
- `SKILL.md`: describes the new fields, calls the music library's missing posters "albums without
  cover art", triggers on questions about lossless/lossy music, FLAC vs MP3 and missing album art,
  and stays facts-only (it never suggests re-ripping, replacing or converting files).
- README: the music Roadmap item is removed (now done). Website: the library-report feature list
  mentions lossless vs lossy music. `openspec/ideas.md`: the music note is removed.
- Version bump to 0.16.0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `library-report`: "Plex paths used" is unchanged (artists come from the same `/all` path);
  "Options" adds `--music-examples`; "Report contents" adds `audio_quality` and the artist listing
  for music libraries; "Housekeeping" adds missing artist photos for music; a new "Music audio
  quality" requirement defines lossless, lossy and the album groupings.

## Impact

- `plugins/cinemetric/skills/library-report/scripts/library_report.py`: new audio quality code and
  option; music libraries fetch the artist list instead of only counting artists (one request per
  500 artists, same path).
- `plugins/cinemetric/skills/library-report/SKILL.md`: description, field list and presentation.
- `tests/test_library_report.py`: new offline tests for the spec scenarios.
- `README.md` Roadmap, `website/index.html` feature list, `openspec/ideas.md`.
- `VERSION` in all eight scripts, `plugin.json` and `marketplace.json`.
- The dashboard is not changed. It receives the new field but ignores it, as it does duplicates.
