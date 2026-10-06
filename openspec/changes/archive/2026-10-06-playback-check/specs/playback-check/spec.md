## ADDED Requirements

### Requirement: Sources used
The script `skills/playback-check/scripts/playback_check.py` SHALL request only `/`,
`/library/sections`, `/library/sections/{id}/all`, `/library/metadata/{ids}` and `/:/prefs` from the
user's Plex server, reading library items in pages of 500. `{ids}` SHALL be 1 to 100 numeric rating
keys separated by commas, and any other form SHALL be refused by the path allowlist. From `/:/prefs`
the script SHALL read only `WanPerStreamMaxUploadRate`; no other setting SHALL appear in its output.

When Tautulli is set up, the script SHALL run only the Tautulli commands `get_tautulli_info`,
`get_history` and `get_stream_data`. It SHALL NOT contact plex.tv or any other address.

#### Scenario: Building a report
- **WHEN** the script builds a report with Tautulli set up
- **THEN** every request goes to the configured Plex server (one of the five allowed paths, with
  `GET`) or to the configured Tautulli address (one of the three allowed commands)

#### Scenario: Asking for too many titles at once
- **WHEN** the script tries to request `/library/metadata/` with 101 rating keys
- **THEN** it stops with the blocked request error and nothing is sent

#### Scenario: Tautulli isn't set up
- **WHEN** only Plex is configured
- **THEN** the script makes no Tautulli request and the report is still built

### Requirement: Libraries and files checked
Only movie and TV libraries SHALL be checked; other libraries SHALL be named in `skipped_libraries`
with their type. Movies SHALL be read with the movie listing (`type=1`) and episodes with the episode
listing (`type=4`); in TV libraries each show's title and year SHALL come from the show listing
(`type=2`). Each media version of a title SHALL be checked as a separate file. A media version
with a `deletedAt` value SHALL be counted in `unavailable` and not checked. `--library NAME`
(repeatable, case-insensitive) SHALL limit the libraries checked, and SHALL stop the script with an
error if nothing matches, or if only libraries other than movie and TV libraries match.

Subtitle and audio tracks SHALL be read from the detail listing `/library/metadata/{ids}`, asking for
at most 100 titles per request. A title the detail listing doesn't return SHALL be counted in
`details_missing`; its files SHALL still be checked for audio using the media version's `audioCodec`
and for bitrate, but not for subtitles.

#### Scenario: Music library
- **WHEN** the server has a music library
- **THEN** it is not checked and appears in `skipped_libraries` with type `artist`

#### Scenario: Asking for a music library
- **WHEN** run with `--library Music` and "Music" is a music library
- **THEN** the script stops with an error saying only movie and TV libraries are checked

#### Scenario: Two versions of a movie
- **WHEN** a movie has a 4K version with TrueHD audio and a 1080p version with AC3 audio
- **THEN** the 4K file is flagged for TrueHD audio and the 1080p file is not

#### Scenario: Requests in batches
- **WHEN** a TV library has 250 episodes
- **THEN** their details are read in 3 requests

### Requirement: Image-based subtitles
A subtitle track SHALL be image-based when its codec is `pgs`, `hdmv_pgs_subtitle`, `vobsub`,
`dvd_subtitle`, `dvb_subtitle` or `xsub` (ignoring case), and text-based otherwise. Tracks inside the
file and separate subtitle files SHALL both count. A file SHALL have the cause `image_subtitles` when
it has an image-based track that is forced, or marked default, or that is the only kind of subtitle in
its language (no text-based track with the same language code). Image-based tracks that have a
text-based track in the same language and are neither forced nor default SHALL NOT make the file
flagged, and the file SHALL be counted in `image_subtitles_with_text`. Tracks with no language code
SHALL be treated as one language of their own.

#### Scenario: Only image-based subtitles in English
- **WHEN** a file has an English PGS track and no other English subtitles
- **THEN** it has the cause `image_subtitles` and `image_subtitle_languages` includes `en`

#### Scenario: A text alternative exists
- **WHEN** a file has an English PGS track and an English SRT track, neither forced nor default
- **THEN** it doesn't have the cause `image_subtitles` and is counted in `image_subtitles_with_text`

#### Scenario: A forced image-based track
- **WHEN** a file has a forced English PGS track and an English SRT track
- **THEN** it has the cause `image_subtitles` and is counted in `forced_image_subtitles`

#### Scenario: Text subtitles only
- **WHEN** a file has only SRT and ASS tracks
- **THEN** it doesn't have the cause `image_subtitles`

### Requirement: TrueHD and DTS audio
A file's main audio track SHALL be the audio track marked selected, otherwise the one marked default,
otherwise the first. The file SHALL have the cause `truehd_audio` when the main track's codec is
`truehd`, and `dts_audio` when it is `dca`, `dca-ma` or `dts` (ignoring case). Either cause SHALL
record the track's profile as Plex reports it (for example `ma` or `dolby truehd + dolby atmos`) and
`common_alternative`: whether the file has another audio track with codec `ac3`, `eac3` or `aac`.

#### Scenario: DTS-HD MA with an AC3 track
- **WHEN** a file's default audio track is `dca-ma` and it also has an `ac3` track
- **THEN** it has the cause `dts_audio` with `common_alternative` true

#### Scenario: TrueHD with nothing else
- **WHEN** a file's only audio track is `truehd`
- **THEN** it has the cause `truehd_audio` with `common_alternative` false

#### Scenario: A common main track
- **WHEN** a file's default audio track is `eac3` and it also has a `truehd` track
- **THEN** it has no audio cause

### Requirement: Bitrate above the limit
The bitrate limit SHALL be `--max-bitrate KBPS` when given, otherwise the server's
`WanPerStreamMaxUploadRate` when it is above 0. A file SHALL have the cause `over_bitrate_limit` when
its media version's `bitrate` is above the limit. When there is no limit (the server's value is 0 or
missing and no `--max-bitrate` is given), the check SHALL be skipped, `bitrate_limit` SHALL be `null`
and no file SHALL have this cause. When `--max-bitrate` is given, `/:/prefs` SHALL NOT be requested.
If the server's setting can't be read (for example with an account that isn't the server owner's),
the check SHALL be skipped the same way and `bitrate_limit_problem` SHALL give the reason; the rest of
the report SHALL still be built.

#### Scenario: The setting can't be read
- **WHEN** `/:/prefs` answers with HTTP 401 and no `--max-bitrate` is given
- **THEN** `bitrate_limit` is `null`, `bitrate_limit_problem` explains why, and the script exits 0

#### Scenario: The server has a 12 Mbps remote limit
- **WHEN** `WanPerStreamMaxUploadRate` is 12000 and a file's bitrate is 18000
- **THEN** the file has the cause `over_bitrate_limit` and `bitrate_limit` is
  `{"kbps": 12000, "source": "server"}`

#### Scenario: No limit set
- **WHEN** `WanPerStreamMaxUploadRate` is 0 and no `--max-bitrate` is given
- **THEN** `bitrate_limit` is `null` and no file has the cause `over_bitrate_limit`

#### Scenario: A limit chosen by the user
- **WHEN** the server has no limit and the script is run with `--max-bitrate 8000`
- **THEN** files above 8000 kbps have the cause `over_bitrate_limit` and `bitrate_limit` is
  `{"kbps": 8000, "source": "option"}`

### Requirement: Transcodes by device and person
When Tautulli is set up and `--days` is above 0, the script SHALL read Tautulli's history of movie and
episode plays started in the last `--days` days (default 90), at most 20,000 plays, and set
`history_capped` when there were more. Each play's `transcode_decision` SHALL count as `direct play`,
`direct stream` (Tautulli's `copy`) or `transcode`.

Plays SHALL be grouped by device (the player name, app and platform together) and by person (the
person's display name). For each group the report SHALL give `plays`, `direct_play`, `direct_stream`,
`transcodes`, `transcode_share` (percent of plays, whole number), `remote_transcodes` (transcodes
played from outside the home network) and `reasons`.

For the 200 most recent transcoded plays the script SHALL read `get_stream_data` and record why each
was transcoded: `subtitles` when the subtitle decision is `burn`, `video` when the video decision is
`transcode` and subtitles weren't burned in, `audio` when the audio decision is `transcode`. A play can
have more than one reason. Plays with no usable stream data SHALL count as `unknown`, and transcoded
plays beyond the 200 SHALL count as `not_checked`.

The report SHALL NOT contain IP addresses, machine ids, user ids or any other Tautulli field not named
here.

#### Scenario: A device that transcodes often
- **WHEN** a Roku called "Living Room" has 20 plays in the window, 14 of them transcoded, 10 with
  subtitles burned in
- **THEN** its device entry has `plays` 20, `transcodes` 14, `transcode_share` 70 and `reasons`
  with `subtitles` 10

#### Scenario: Direct stream isn't a transcode
- **WHEN** a play's `transcode_decision` is `copy`
- **THEN** it counts as `direct_stream` and not in `transcodes`

#### Scenario: Many transcodes
- **WHEN** there are 260 transcoded plays in the window
- **THEN** `get_stream_data` is requested 200 times and 60 plays count as `not_checked`

#### Scenario: Private fields from Tautulli
- **WHEN** Tautulli's history includes `ip_address`, `machine_id` and `user_id`
- **THEN** none of their values appear in the output

### Requirement: When Tautulli isn't available
Without Tautulli, `playback_history` SHALL be `null` and `playback_history_note` SHALL say that
transcodes by device and person need Tautulli, because Plex's own history doesn't record them. If
Tautulli is set up but fails, the file checks SHALL still be reported, `playback_history` SHALL be
`null`, `playback_history_error` SHALL give the reason, and the script SHALL exit 0. `--days 0` SHALL
skip the history part without contacting Tautulli.

#### Scenario: Tautulli is down
- **WHEN** Tautulli is set up but can't be reached
- **THEN** the report has the library results, `playback_history` is `null`,
  `playback_history_error` explains the problem, and the script exits 0

### Requirement: Report contents
The JSON report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version),
`bitrate_limit` (and `bitrate_limit_problem` when it applies), `limits` (a fixed sentence saying these are likely causes on common devices, not a
promise, that image-based subtitles only matter when subtitles are on, and that the bitrate limit only
affects remote viewers), `libraries`, `skipped_libraries`, `totals` and the history part
(`playback_history`, and `playback_history_note` or `playback_history_error` when it applies).

Each entry in `libraries` SHALL have `name`, `type`, `titles`, `files`, `unavailable`,
`details_missing`, `files_flagged` (files with at least one cause), one count per cause
(`image_subtitles`, `truehd_audio`, `dts_audio`, `over_bitrate_limit`), `forced_image_subtitles`,
`image_subtitles_with_text`, `listed` and `more`. The counts SHALL cover every file checked.

In a movie library `listed` SHALL hold movies with at least one flagged file, each with `title`,
`year` (or `null`) and `files`: the flagged files, each with `resolution`, `size_gb`, `bitrate_kbps`,
`causes`, `image_subtitle_languages` and `audio` (codec, profile and `common_alternative`, or `null`).
In a TV library `listed` SHALL hold shows with at least one flagged episode, each with `title`, `year`
(or `null`), `episodes`, `episodes_flagged` and one count per cause. File paths SHALL NOT appear in the
report.

`listed` SHALL be sorted with titles that have `image_subtitles` or `over_bitrate_limit` (causes that
convert the whole picture) first. After that, movies SHALL be sorted by the number of different causes
across their flagged files (most first), then by the total size of their flagged files (largest
first), and shows by the number of flagged episodes (most first); ties SHALL be sorted by title.
`listed` SHALL hold at most `--limit` entries; `more` SHALL be how many were left out.

`playback_history` SHALL have `days`, `plays`, `direct_play`, `direct_stream`, `transcodes`,
`history_capped`, `reasons` (over all transcodes), `devices` and `people` (each the 10 groups with
the most transcodes, only groups with at least one, then by share, then by name), `devices_total`,
`people_total` (how many groups had any plays) and `titles` (up to 10 titles transcoded at least
twice, most first, each with its transcodes and reasons; empty when no title was transcoded twice).

`totals` SHALL give `titles`, `files`, `files_flagged` and one count per cause over all libraries
checked.

#### Scenario: A clean library
- **WHEN** no file in a library has a cause
- **THEN** the library has `files_flagged` 0 and an empty `listed`, `limits` is still present, and the
  script exits 0

#### Scenario: A show with flagged episodes
- **WHEN** a show has 30 episodes and 12 of them have DTS audio
- **THEN** its listed entry has `episodes` 30, `episodes_flagged` 12 and `dts_audio` 12

#### Scenario: Subtitles sort before audio
- **WHEN** one movie has only DTS audio and another has only image-based subtitles
- **THEN** the movie with image-based subtitles is listed first

#### Scenario: More causes, then bigger files
- **WHEN** three movies have image-based subtitles: a 10 GB one that also has DTS audio, a 12 GB one
  and a 5 GB one
- **THEN** they are listed in that order: the 10 GB one (two causes), then 12 GB, then 5 GB

#### Scenario: Titles transcoded once
- **WHEN** every transcoded title in the window was transcoded only once
- **THEN** `titles` is empty

### Requirement: Options
The script SHALL accept `--library NAME` (repeatable), `--limit N` (titles listed per library,
default 25, limited to 0–500), `--max-bitrate KBPS` (limited to 100–1,000,000), `--days N` (default
90, limited to 0–3650) and `--check`.

#### Scenario: Counts only
- **WHEN** run with `--limit 0`
- **THEN** every library's `listed` is empty and its counts are still filled in

#### Scenario: Out-of-range limit
- **WHEN** run with `--limit 9999`
- **THEN** each library lists at most 500 titles

#### Scenario: Checking the connections
- **WHEN** run with `--check` and Tautulli is set up
- **THEN** the script tests Plex and Tautulli once each and prints whether each works
