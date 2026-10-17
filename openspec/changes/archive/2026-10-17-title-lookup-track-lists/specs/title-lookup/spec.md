## MODIFIED Requirements

### Requirement: Files
For a movie or episode, `files` SHALL list each media version separately with `library`,
`resolution`, `video_codec`, `hdr` (true when Plex reports an HDR or Dolby Vision color profile),
`bit_depth`, `audio_codec`, `audio_channels`, `container`, `bitrate_kbps`, `size_bytes`, `path` and
`available` (false when the media version has a `deletedAt` value). `total_size_bytes` SHALL add up
the available files.

Each available file whose details were read from `/library/metadata/{ids}` SHALL also have
`audio_tracks` and `subtitle_tracks`: the audio streams (`streamType` 2) and subtitle streams
(`streamType` 3) of all of that version's parts, in the order Plex lists them, at most 50 of each.
`audio_track_count` and `subtitle_track_count` SHALL give how many there are in all, including any
past the first 50. Each audio track SHALL have:
- `language`: the stream's `languageTag`, else its `languageCode`, else `null`;
- `name`: the stream's `title`, else `null`;
- `codec`: the stream's `codec` in lower case, else `null`;
- `channels`: the stream's `channels` as a whole number, else `null`;
- `default`: true when the stream's `default` is set;
- `selected`: true when the stream's `selected` is set.

Each subtitle track SHALL have `language`, `name`, `codec`, `default` and `selected` as for audio, and:
- `forced`: true when the stream's `forced` is set;
- `hearing_impaired`: true when the stream's `hearingImpaired` is set;
- `external`: true when the stream has a `key`, meaning Plex serves it from a separate subtitle file
  rather than from inside the video file.

Every text value in a track SHALL be cleaned as described in "Server text is treated as data" in the
security spec. No other stream field SHALL be printed. A file that isn't available, and a file whose
details weren't returned, SHALL have neither list nor count. A show's report SHALL NOT list tracks.
Listing the tracks SHALL NOT change `playback_causes`, `image_subtitle_languages` or `audio`.

#### Scenario: A 4K and a 1080p version
- **WHEN** a movie has a 4K HEVC version and a 1080p H.264 version
- **THEN** `files` has two entries with their own resolution, codecs, size and path

#### Scenario: A file Plex can't find
- **WHEN** a media version has a `deletedAt` value
- **THEN** its entry has `available` false, its size is left out of `total_size_bytes`, and it has no
  `audio_tracks` or `subtitle_tracks`

#### Scenario: Two audio tracks
- **WHEN** a file has a Japanese 5.1 AAC track marked default and an English 2.0 AC3 track named
  "English Dub", in that order
- **THEN** `audio_tracks` lists the Japanese track first with `default` true and `channels` 6, then
  the English track with `name` "English Dub" and `default` false, and `audio_track_count` is 2

#### Scenario: Forced, SDH and a separate file
- **WHEN** a file has an embedded English SRT track marked forced, and Plex also lists an English SRT
  subtitle with a `key` and `hearingImpaired` set
- **THEN** `subtitle_tracks` has the first with `forced` true and `external` false, and the second
  with `hearing_impaired` true and `external` true

#### Scenario: Many subtitle tracks
- **WHEN** a file has 63 subtitle tracks
- **THEN** `subtitle_tracks` lists the first 50 and `subtitle_track_count` is 63

#### Scenario: A track name with control characters
- **WHEN** an audio track's `title` contains a newline and is 300 characters long
- **THEN** its `name` has the newline replaced with a space and is cut to 120 characters

#### Scenario: A whole show
- **WHEN** the title is a show
- **THEN** the report has no `audio_tracks` or `subtitle_tracks`, only `playback_summary`

#### Scenario: Same playback answer as before
- **WHEN** a file with TrueHD and AC3 audio and an English PGS track is looked up
- **THEN** `playback_causes`, `image_subtitle_languages` and `audio` are the same as without the
  track lists, and the same as `playback-check` reports for that file
