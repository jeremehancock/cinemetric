## Context

Plex transcodes (converts a file on the fly) when a device can't play it as it is. Converting the
picture is the expensive kind: it loads the server's CPU or GPU and is what usually causes
buffering. Converting only the sound is cheap. A handful of causes account for most transcodes on
common devices:

- **Image-based subtitles** (PGS from Blu-rays, VobSub from DVDs). They are pictures, not text, and
  most apps can't overlay them, so Plex draws them into the video. That converts the whole picture,
  but only while subtitles are on.
- **TrueHD and DTS audio.** Many TVs, streaming sticks and phones can't decode them, so Plex
  converts the sound. The picture is untouched.
- **Bitrate above the server's remote limit.** Remote viewers get a smaller converted copy.

`server-health` already explains transcodes that are happening now. This skill looks ahead at the
files, and back at Tautulli's history, to answer "why does this keep happening?"

The `ideas.md` note flagged cost as "the big catch": subtitle tracks aren't in the library listing,
so it seemed to need one request per title. The probe below showed that isn't so.

Decided with the user on 2026-10-06: a separate skill (not part of `server-health`), a dashboard
section, and transcode history grouped by both device and person, so whoever runs it can see who is
likely to have trouble.

## Goals / Non-Goals

**Goals:**
- Per library, count and list the files likely to transcode, and why, using only the few universal
  causes.
- Check every movie and episode, not a sample, in about a minute on a large server (71 seconds for 21,000 titles).
- With Tautulli, show which devices and people transcode most, how often compared with their plays,
  and why (subtitles drawn in, video, audio), plus the titles transcoded most.
- Be plain about what "likely" means: it depends on the device, its settings and whether subtitles
  are on.

**Non-Goals:**
- A per-device database of what each TV or app supports. Clients change too often to keep one right.
- Video codec and HDR causes (HEVC, AV1, Dolby Vision on older devices). They are real, but which
  devices can't play them varies too much to say "likely" honestly. Could be a later option.
- Suggesting fixes (converting files, removing tracks, optimized versions). The report gives facts;
  SKILL.md may explain what a cause means, never tell the user to change their files.
- What's transcoding right now. That's `server-health`.
- Music libraries. Music almost never transcodes for these reasons.
- Snapshots or "new since last time". Can be added later.

## Decisions

**What the probe found (owner's real server, 2026-10-06).** Only shapes, counts and timings printed.
- Libraries: two movie libraries (one empty), one TV library, one music library. 1,970 movies and
  19,010 episodes.
- The library listing has `audioCodec`, `audioProfile` and `bitrate` on every media version, but no
  `Stream` entries, so subtitle tracks really aren't there.
- `/library/metadata/<id>,<id>,...` accepts many rating keys at once and returns full stream details
  for each: 200 titles came back in 0.4 to 0.6 seconds. At 100 per request a full check is about 210
  requests, about a minute (see the confirmation results below), so no sampling or one-library-at-a-time limit is needed.
- Audio codec values seen: `dca` (DTS, 808 files), `dca-ma` (DTS-HD MA, 428), `truehd` (106), plus
  `eac3`, `ac3`, `aac` and others. About 54% of movies (1,065 of 1,970) have DTS or TrueHD as their main track.
- Subtitle codecs in a sample of 200 movies: `srt`, `pgs` (241 tracks), `vobsub` (75), `ass`,
  `mov_text`, `eia_608`. Separate subtitle files appear with a `key`.
- `WanPerStreamMaxUploadRate` is 0 (no remote limit), so on this server the bitrate check only runs
  with `--max-bitrate`.
- Tautulli: 21,301 plays in total; in the latest 5,000, 136 transcodes, 6 direct streams (`copy`),
  the rest direct play; 5 platforms, 24 players, 8 apps. `get_history` rows carry
  `transcode_decision`, `player`, `product`, `platform`, `friendly_name` and `location` (`wan` or
  `lan`), but not why. `get_stream_data` for one play gives `stream_video_decision`,
  `stream_audio_decision` and `stream_subtitle_decision`, which do say why.

**What the confirmation step found (owner's real server, 2026-10-06).** Counts and timings only.
- A full run read 1,970 movie details in 20 requests (8 seconds) and 19,011 episode details in 191
  requests (53 seconds): about 71 seconds in all. Every key asked for came back; every file had
  stream details. No separate subtitle files on this server.
- Every file has an audio track marked selected. Plex lists DTS-HD MA as `dca-ma` on the media
  version but as `dca` with profile `ma` on the stream, so the stream codec is the one used.
- Movies: 690 files have image-based subtitles. 666 are flagged (584 have no text subtitles at all,
  only 6 are flagged by the default mark alone, 17 have a forced image track) and 24 have a text
  alternative. 973 have DTS as the main track (210 with a common alternative), 99 TrueHD (67 with
  one). 1,767 are above 8 Mbps.
- TV: 1,283 episodes flagged for image-based subtitles, 46 with a text alternative, 277 with DTS.
- Tautulli, last 90 days: 419 movie and episode plays (plus 688 music plays, which are left out), 32
  transcodes on 9 devices by 6 people. All 32 had stream data. Subtitle decisions seen: `burn`,
  `transcode` and empty. `transcode` means a text subtitle was converted to another text format,
  which doesn't touch the picture, so only `burn` counts as the `subtitles` reason, as planned.
  `get_history`'s `media_type` filter works.

**Batching detail requests.** Rating keys are sent 100 at a time on `/library/metadata/{ids}`. 100
keeps the URL short (about 700 characters) while needing only about 210 requests for 21,000 titles.
The allowlist pattern only accepts 1 to 100 numeric keys, so a mistake can't turn it into a broader
request. A title missing from a batch's answer (deleted between the two requests) is counted in
`details_missing` and checked for audio and bitrate from the listing.

**When image-based subtitles count.** Only subtitles that are on cause the transcode, and the script
can't know who turns them on. Counting every file with any PGS track would flag nearly every Blu-ray
rip, most of which also have an SRT track people actually use. So a file is flagged when an
image-based track is likely to be the one shown: it's forced (shown automatically), marked default,
or the only subtitle option in its language. Files where a text track exists in the same language are
counted separately (`image_subtitles_with_text`) so the user still sees the number. Alternative
considered: flag every image-based track. Simpler, but far noisier and less true.

**Audio by main track.** Plex plays the selected or default audio track and doesn't switch to a
different track by itself, so the main track decides. A file that also carries AC3, E-AC3 or AAC gets
`common_alternative: true`; SKILL.md can say switching the audio track in the player avoids the
conversion. `dca`, `dca-ma` and `dts` all count as DTS. Audio-only transcodes are cheap, which is why
listing puts picture-converting causes first.

**Bitrate limit.** The server's remote limit is the only bitrate rule the server itself enforces, so
it's the default. Many servers (including the owner's) have none, and remote viewers' apps often set
their own quality. `--max-bitrate` lets the user ask "what's over 8 Mbps?" without the script
pretending to know each app's setting. No limit means the check is skipped and the report says so,
rather than picking an arbitrary number.

**Movies by title, TV by show.** A movie library lists movies with their flagged files (each version
separately, since a 4K TrueHD copy and a 1080p AC3 copy behave differently). A TV library lists
shows with counts per cause, because listing up to 19,000 episodes one by one isn't readable, and
whole seasons usually come from the same source anyway.

**Sorting.** Titles with a picture-converting cause (`image_subtitles`, `over_bitrate_limit`) come
first. On a library where over half the movies have DTS, sorting by plain count would bury the
expensive cases. Then movies go by how many different causes they have, then by the size of their
flagged files, and shows by how many episodes are flagged. The first plan sorted movies by number of
flagged files too, but running it on the owner's server showed that nearly every movie has one file,
so the list fell back to alphabetical order (2026-10-06). Size is a reasonable stand-in for how much
a conversion costs, since bigger files usually mean higher bitrates.

**Titles transcoded most.** Only titles transcoded at least twice are listed. On the owner's server
every transcoded title in 90 days had one transcode, so the list was ten ties that said nothing about
the titles.

**History: devices and people.** Tautulli's `get_history` is read for movie and episode plays in the
last `--days` days (default 90, matching how far back is still about current devices), using `after`
and paging like `watch-activity`, with `grouping=1` so a play paused and resumed later counts once
(as `watch-activity` and `unwatched` do), capped at 20,000 plays. A device is the player name, app and
platform together ("Living Room", "Plex for Roku", "Roku"); `machine_id` would separate two devices
with the same name, but it's an identifier the report shouldn't carry. People are grouped by display
name, as in `watch-activity`. Each group shows plays, transcodes and the share, because "14 of 20" is
more telling than "14".

**Why each transcode happened.** `get_stream_data` is one request per play, but transcodes are rare
(about 3% of plays on the owner's server), so reading the 200 most recent is cheap and covers months
of history on most servers. `subtitles` (subtitle decision `burn`) takes priority over `video`, since
drawing subtitles in is what forced the video conversion. Plays beyond 200 count as `not_checked`
rather than being guessed at.

**Tautulli is optional.** Plex's own history (`/status/sessions/history/all`) has no transcode
decision, so there's no Plex fallback for this part; the report says so. A Tautulli failure doesn't
fail the report: the file checks are the main result.

**Private fields.** Only the fields named in the spec are copied out of Tautulli rows; IP address,
machine id, user id and thumbnails are dropped. Device names can contain people's names ("Sam's
iPhone"), so the dashboard hides them along with the people list when names are hidden.

**Dashboard runs `playback_check.py --limit 0`.** The section shows counts per cause, the bitrate
limit, and the top 5 devices and people, not file lists. It costs about a minute per refresh on a
large server, running side by side with the other reports. Not in "Needs a look", doesn't change
the overall status, not in the snapshot.

**Shared helpers copied.** Per the conventions, `load_config`, `validate_url`, `PlexClient`,
`TautulliClient` and `clean` are copied from `unwatched.py`, which uses both Plex and Tautulli.
`tests/helpers.py`' `SCRIPTS` list gets the new script.

## Risks / Trade-offs

- [Devices differ] → An Nvidia Shield plays TrueHD and PGS fine; a cheap streaming stick may not.
  The report says "likely" and carries a `limits` note; the Tautulli part shows what really happens
  on the user's own devices, which is the stronger evidence.
- [The image subtitle rule misses some cases] → A viewer who deliberately picks a PGS track when an
  SRT exists still transcodes. Accepted, to avoid flagging most of a Blu-ray library.
- [Many DTS files] → On libraries like the owner's, most movies get `dts_audio`. Sorting puts the
  expensive causes first, and SKILL.md explains that audio conversion is light.
- [About a minute per run, and on each dashboard refresh] → Plex answers the batched requests quickly;
  the confirmation step times a full run. `--library` narrows it when asked about one library.
- [Stream data for old plays] → Tautulli may lack stream data for plays imported from before it was
  installed (`pre_tautulli`). Those count as `unknown`.

## Migration Plan

Additive: a new skill and script, a new dashboard section. Rollback is removing the skill folder,
the dashboard source and section, and the doc edits.

## Open Questions

- Is 100 titles per detail request safe on every Plex version? Checked on the owner's server only.
  The batch size is one constant, so it's easy to lower if a user reports a problem.
- Should video codec and HDR causes become an opt-in later? Left out here (see Non-Goals).
