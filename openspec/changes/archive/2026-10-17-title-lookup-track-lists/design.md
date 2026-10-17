## Context

`title_lookup.py` reads each movie's or episode's details from `/library/metadata/{ids}`, which
includes every stream (video, audio and subtitle track) of every part of every media version. Today
`check_file` uses them only to find the playback causes, and `describe_file` prints the results:
`image_subtitle_languages` and the main audio track's codec when it's TrueHD or DTS. Everything else
about the tracks is dropped.

The request came from a separate skill that checks audio and subtitle languages on the user's media.
It wanted to confirm, the way Plex sees it, that a default-audio fix took effect and that Plex picked
up a subtitle file Bazarr added next to a video. That skill reads the files itself; Cinemetric stays
Plex-API-only, and this change fits inside that.

## Goals / Non-Goals

**Goals:**
- For one movie or episode, list every audio and subtitle track Plex knows, with the details someone
  checking languages needs: language, name, codec, channels (audio), default, selected, forced,
  hearing impaired and separate file (subtitles).
- No new Plex requests, no change to the playback answer, no change to any shared helper.

**Non-Goals:**
- Track lists for every episode of a show. A show report would get very long, and the
  `subtitles-and-languages` skill already covers library-wide language questions.
- The separate subtitle file's name. Checked on a real server (2026-10-17): Plex's stream details
  don't carry it, only a `key` and a display title ending in "External". `external` says only that
  it's a separate file.
- Judging tracks (wrong language, wrong default, missing forced subtitles). The script states what
  Plex reports; `subtitles-and-languages` does the checking it's designed for.
- Track position inside the file (`index`), bitrate, sample rate and other stream fields. Not asked
  for, and each extra field is more output for Claude to read.

## Decisions

**A new function, not a change to `check_file`.** `check_file` holds the playback rules shared with
`playback-check`, and the conventions spec says every copy of a shared helper must stay the same. A
separate `list_tracks(media)` in `title_lookup.py` only reads the streams, so the shared copies don't
move and the existing "Playback rules drift apart" test keeps guarding them. `describe_file` calls it
only when the file is available and its details were read (the `have_streams` flag it already gets),
so files whose details were missing get no lists instead of empty ones that would wrongly suggest the
file has no tracks.

**Both `default` and `selected`.** They answer different questions. `default` is the flag written in
the file, which is what a fix to the file changes. `selected` is the track Plex will use for the
account Cinemetric signed in with, which can differ when that account once picked another track by
hand. Showing both explains the common "I fixed the default but Plex still plays the dub" case.
Alternative considered: only `default`; rejected because the mismatch is exactly what's useful to see.

**`external` from the stream's `key`.** Plex gives a separate subtitle file its own download address
(`key`, like `/library/streams/123`) because it serves the file on its own; tracks inside the video
file don't have one. The address itself isn't printed: it's of no use to the reader. This is marked
for checking on a real server in the tasks, with an embedded and a separate subtitle on the same title.

**`hearingImpaired` missing means false.** Older Plex versions may not send the field. Reporting
`false` rather than `null` keeps the field simple; the track `name` often says "SDH" anyway, and the
SKILL.md tells Claude not to treat `false` as proof. Alternative considered: `null` when missing,
which is more exact but makes every reader handle three values for a flag that's rarely set.

**Language as a code, like the rest of the script.** `languageTag` (such as `en` or `pt-BR`) first,
then `languageCode` (such as `eng`), the same choice `check_file` makes, so `image_subtitle_languages`
and the new lists use the same codes. Claude turns codes into names, as it already does.

**50 tracks per kind.** Most files have under ten tracks; some disc remuxes have 30 or more subtitle
tracks. 50 keeps a pathological file from flooding the report while the counts still say how many
there are.

## Risks / Trade-offs

- [Plex's stream fields differ from what's assumed here (`key` for separate files,
  `hearingImpaired`, `channels`)] → The first task checks them on a real server before any code is
  written, and the spec is corrected if they differ.
- [Longer output for files with many tracks] → The 50-track cap, and only for one movie or episode.
- [Track names written by whoever made the file] → Cleaned like every other server text, and
  SKILL.md already tells Claude to treat server values as data.
