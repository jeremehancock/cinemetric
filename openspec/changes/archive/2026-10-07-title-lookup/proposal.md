## Why

Questions about one title ("tell me about Dune on my Plex", "is The Office complete, and will it
play on my TV?") are among the most natural things to ask, but today the answer is spread across
five skills: `library-report` knows the files and quality, `playback-check` knows what's likely to
transcode, `watch-activity` and `unwatched` know who watched it, and nothing reports collections.
Each of those reads the whole library to answer a question about one title. A single lookup that
joins them for one movie, show or episode is cheap (a handful of requests) and reuses rules the
project already has.

## What Changes

- A new read-only skill, `title-lookup`, with one script, `title_lookup.py`. Given a title (and
  optionally a year, library, type, or season and episode), it finds the matching movie, show or
  episode on the server and reports everything Cinemetric knows about it:
  - **What it is:** type, title, year, library, when it was added, length, content rating, genres,
    ratings, a short summary, and the collections it's in.
  - **Files:** each media version with resolution, video codec, HDR and 10-bit, audio codec and
    channels, container, bitrate, size, file path, and whether Plex can still find it. The same
    title in another library (for example a Kids Movies copy) is listed too.
  - **Playback:** for each file, the causes `playback-check` already looks for (image-based
    subtitles, TrueHD or DTS audio, bitrate above the remote streaming limit), using the same rules,
    and saying "likely", never "will".
  - **For a show:** seasons with episode counts and sizes, episodes Plex can't find, and the total.
    Gap detection stays in `episode-gaps`; the report points there.
  - **Watching:** who watched it, how many plays, when each person last played it and whether they
    finished, how far they got (with Tautulli), and for a show how many episodes each person has
    finished. Uses Tautulli when it's set up, otherwise Plex's own history. If the history can't be
    read (for example on a server the user doesn't own), the rest of the report is still given.
- **More than one match:** the script lists the matches (up to 20) instead of guessing, and
  `--key` picks one.
- **Facts only:** like every skill, it never suggests deleting, replacing or converting a file.
- Options: the title, `--year`, `--library NAME`, `--type movie|show`, `--season N`, `--episode N`,
  `--key RATING_KEY`, `--source auto|tautulli|plex`, `--max-bitrate KBPS`, `--check`.
- README: new row in the Skills table, and `title-lookup` comes off the Roadmap and out of
  `openspec/ideas.md`. Website: the new skill with a terminal demo panel (thirteen skills).
- Version bump to 0.27.0.

## Capabilities

### New Capabilities

- `title-lookup`: what the script requests from Plex and Tautulli, how a title is found and how
  several matches are handled, what is reported about the title, its files, playback causes, seasons
  and watching, how history problems are handled, and the options.

### Modified Capabilities

- `conventions`: "Connection check" and "Media deletion setting" add the new script.
- `security`: "Only known destinations" gets a scenario saying `title_lookup.py` contacts only the
  configured Plex server and, if set up, Tautulli.
- `testing`: "Tests check the specs" adds `title-lookup` coverage and a scenario for a playback rule
  that drifts from `playback-check`'s.
- `website`: "Shows every skill" adds `title-lookup` (thirteen skills).

## Impact

- New: `plugins/cinemetric/skills/title-lookup/SKILL.md` and
  `plugins/cinemetric/skills/title-lookup/scripts/title_lookup.py` (with copies of the shared
  helpers `load_config`, `validate_url`, `PlexClient`, `TautulliClient`, `clean` and
  `media_deletion_allowed`, and of `playback-check`'s cause rules).
- New: `tests/test_title_lookup.py` and made-up fixtures in `tests/fixtures/title-lookup/`. The
  cross-script security tests gain the new script.
- Changed: `README.md`, `openspec/ideas.md`, `website/index.html`.
- `VERSION` in every script, `plugin.json` and `marketplace.json`.
- Two Plex paths new to this script's list (`/library/metadata/<id>/allLeaves`, and `/accounts`,
  which `watch-activity` already uses), both read-only. No new
  destinations and no new Tautulli commands beyond `get_tautulli_info` and `get_history`.
