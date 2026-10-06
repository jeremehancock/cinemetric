## Context

`library-report` already downloads every track (`type=10`) and every album (`type=9`) in a music
library, and counts artists (`type=8`) without downloading them. For music it reports file counts,
storage, an audio codec tally (`media.audio_codec`), recently added albums, and albums with no
`thumb` as `missing_poster`.

A check against a real server on 2026-10-06 (one music library: 251 artists, 499 albums, 6,529
tracks) showed each track's `Media` entry in the listing has `audioCodec`, `container`, `bitrate`
(kbps) and `audioChannels`, and each track has `parentRatingKey`, `parentTitle` and
`grandparentTitle`. It does not have bit depth or sample rate; those live on the audio stream, which
only appears on a track's own detail page. That library was 5,674 FLAC and 855 MP3 tracks, with 2
albums mixing both.

## Goals / Non-Goals

**Goals:**
- Show how much of a music library is lossless vs lossy, by tracks, storage and albums.
- Point out albums that are all lossy or a mix, as facts.
- Count artists with no photo, alongside the existing albums with no cover.
- No new Plex paths and no per-track requests.

**Non-Goals:**
- Hi-res detection (24-bit, 96 kHz and so on). It needs a request per track; could come later with
  snapshots caching the results.
- Suggesting files to re-rip, replace or convert (ground rule: facts, not advice).
- Music duplicates. Different masters and editions of the same album make this a separate problem.
- Dashboard changes.

## Decisions

**Classify by `audioCodec`, not `container`.** An `.m4a` file can hold AAC (lossy) or ALAC
(lossless), so the container can't tell them apart; the codec can. The codec lists are written out
in the spec so the behavior is testable. Anything not on either list goes to `other` rather than
being guessed, so a new or odd codec shows up instead of being miscounted.

**A track is lossless if any copy is.** Tracks rarely have two copies, but when they do (for
example an MP3 and a FLAC of the same track), the question people ask is "do I have this in
lossless?", so the best copy wins. Copies Plex can't find or that are optimized versions are
skipped, reusing the existing `copies()` rules.

**Albums grouped by `parentRatingKey` from the tracks**, not from the album listing. The album
listing has no codec information, so the grouping has to come from tracks anyway. Labels use the
tracks' `grandparentTitle - parentTitle`, matching the existing "Artist - Album" label. Albums whose
tracks are only `other` are left out of the album groups so they don't inflate either side.

**Bitrate buckets: under 192, 192 to 255, 256 and up.** These match common rips: 128 kbps is the
old default, 192 is a middle ground, and 256 (iTunes AAC) and 320 (high MP3) are generally
considered close to transparent. Lossless files are not bucketed; their bitrate mostly reflects
how the music compresses, not quality.

**Lossy album examples ordered by lowest average bitrate.** That puts the weakest-sounding albums
first, which is the most useful order for someone looking through the list. Mixed albums are
ordered by how many lossy tracks they have.

**A separate `--music-examples` option** rather than reusing `--upgrade-examples`. Music has no
`upgrades` section, and the skill would otherwise have to explain that one option controls two
unrelated lists.

**Artists are downloaded instead of only counted.** Replacing `client.count(sid, TYPE_ARTIST)` with
`client.get_all(sid, TYPE_ARTIST)` costs one request per 500 artists (the count was already one
request), on a path already allowed. The artist count then comes from the list length, as albums and
tracks already do. Artist photo is `thumb`, the same field albums use.

**The SKILL.md wording changes for music housekeeping**, not the field name. Renaming
`missing_poster_count` for music would break the shared housekeeping shape; instead SKILL.md tells
Claude to call these "albums without cover art".

## Risks / Trade-offs

- [Plex may report a codec name not in the lists, e.g. a different spelling for WAV] → It lands in
  `other` and is visible in `media.audio_codec`, so it's noticed and can be added; nothing is
  silently miscounted.
- [Lossy albums list could be long on an MP3-heavy library] → Capped by `--music-examples`
  (default 15); counts are always complete.
- [A "lossless" file could be an upconverted MP3] → Can't be detected from metadata. SKILL.md should
  describe these as the file format, not as a guarantee of quality.
- [Downloading artists on huge libraries] → Artist lists are small compared to tracks, which are
  already downloaded in full.
