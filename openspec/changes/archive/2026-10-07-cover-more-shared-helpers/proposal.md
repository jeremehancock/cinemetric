## Why

The first pass (`keep-shared-helpers-in-step`) checks 36 shared helpers. Comparing every function and
constant that appears in more than one script still found helpers that had drifted (`as_bool`, `day`,
`get_all`, `PersonError`, `when`) and helpers that match today but that nothing protects, including
the HTML pages' Content Security Policy and escaping, and the playback rules `playback-check` and
`title-lookup` share.

## What Changes

- Line up the drifted copies:
  - `as_bool`: every copy accepts `1`, `true` and `yes` in any case, ignoring spaces. Before, the
    copies in `playback-check`, `subtitles-and-languages` and `title-lookup` didn't accept `yes` or
    spaces. Everything the old copies accepted is still accepted.
  - `get_all`: every copy takes the optional extra filters some scripts already use. Without them it
    sends the same request as before.
  - `day`: every copy turns a missing, zero or negative time into no date. `users-and-shares` keeps
    its own copy, because its times are already whole seconds and it has no `as_int`.
  - `PersonError` and `when`: same docstring and comment in every copy.
- Add to the shared helper list, so a test fails if they drift:
  - The HTML pages (`dashboard`, `year-in-review`): `CSP`, `e`, `num`, `nice_step`, `full_page`,
    `write_page`, `save_state`, `saved_destination`, `ONLINE_PAGE_RE`, `DESTINATIONS`.
  - Playback rules (`playback-check`, `title-lookup`): `CAUSES`, `COMMON_AUDIO_CODECS`, `DTS_CODECS`,
    `IMAGE_SUBTITLE_CODECS`, `codec`, `language`, `remote_limit`, `read_once`, `check_file`.
  - Finding titles and history: `normalize`, `key_from`, `MAX_MATCHES`, `PLEX_HISTORY_PAGE_SIZE`,
    `months_before`, `as_float`, `tautulli_person`.
  - Streams and running other scripts: `stream_title`, `HERE`, `SKILLS_DIR`,
    `SCRIPT_TIMEOUT_SECONDS`.
  - The five lined-up helpers above.
- Name, in `tools/shared_helpers.py`, the helpers that share a name but do a different job in each
  script, so they aren't mistaken for drift.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `conventions`: "Self-contained scripts" names the HTML page helpers and playback rules among the
  shared helpers.

## Impact

- Scripts: `playback_check.py`, `subtitles_and_languages.py`, `title_lookup.py` (`as_bool`),
  `playback_check.py`, `show_progress.py`, `subtitles_and_languages.py`, `unwatched.py` (`get_all`),
  and the scripts whose `PersonError` or `when` wording changes.
- `tools/shared_helpers.py`: longer list.
- No change to any report's output for real Plex data. No new network destinations, Plex paths or
  Tautulli commands. Same version (0.29.1), since this lands in the same pull request.
