## Why

Server owners usually find out a film has no subtitles they can read when someone sits down to watch
it: a Japanese film with only Japanese audio and no English subtitles, or a show whose tracks have no
language set, so Plex can't pick the right one. Nothing in Cinemetric answers "what can't my people
understand?" today. `playback-check` already reads every title's audio and subtitle tracks cheaply
(100 titles per request), so the same data can answer this without any new kind of server access.

## What Changes

- A new read-only skill, `subtitles-and-languages`, with one script, `subtitles_and_languages.py`. It
  checks every movie and episode in movie and TV libraries and reports, per library:
  - **Foreign audio with no subtitles:** files with no audio track in the user's language and no
    full (not forced-only) subtitle track in it either. This is the main finding.
  - **No subtitles in your language:** files with no full subtitle track in the user's language at
    all, whatever the audio. Useful for viewers who need subtitles, and answers "which titles are
    missing Spanish subtitles?" when run with `--language es`.
  - **Language not set:** files with an audio or subtitle track that has no language, which stops
    Plex choosing tracks by language.
  - **What's there:** how many files have their main audio in each language, and how many have
    subtitles in each language, so the user sees the shape of the library.
- **The user's language:** `--language CODE` (repeatable, for example `en` or `eng`). Without it,
  each library's own metadata language (for example `en-US`) is used, and the report says so. Plex
  keeps each person's preferred audio and subtitle languages on plex.tv, not on the server (checked
  on a real server: `/:/prefs` has no language setting, only `LanguageInCloud`), and this skill
  doesn't contact plex.tv.
- Shows are grouped like `playback-check`: one entry per show with counts of affected episodes.
- **Facts only:** it never suggests downloading subtitles, remuxing or replacing files.
- Options: `--language CODE` (repeatable), `--library NAME` (repeatable), `--limit N`, `--check`.
- README: new row in the Skills table; `subtitles-and-languages` comes off the Roadmap and out of
  `openspec/ideas.md`. Website: the new skill in the "Your library" group, right after
  `playback-check`, with a terminal demo panel (fourteen skills).
- Version bump to 0.28.0.

## Capabilities

### New Capabilities

- `subtitles-and-languages`: what the script requests from Plex, which libraries and files are
  checked, how a track's language is read and matched, how the user's language is chosen, each
  finding, the language summary, the report contents and the options.

### Modified Capabilities

- `conventions`: "Connection check" and "Media deletion setting" add the new script.
- `security`: "Only known destinations" gets a scenario saying `subtitles_and_languages.py` contacts
  only the configured Plex server.
- `testing`: "Tests check the specs" adds `subtitles-and-languages` coverage, with a scenario for a
  forced-only subtitle track counting as full subtitles.
- `website`: "Shows every skill" adds `subtitles-and-languages` (fourteen skills).

## Impact

- New: `plugins/cinemetric/skills/subtitles-and-languages/SKILL.md` and
  `plugins/cinemetric/skills/subtitles-and-languages/scripts/subtitles_and_languages.py` (with copies
  of the shared helpers `load_config`, `validate_url`, `PlexClient`, `clean` and
  `media_deletion_allowed`, and of `playback-check`'s main audio track rule).
- New: `tests/test_subtitles_and_languages.py` and made-up fixtures in
  `tests/fixtures/subtitles-and-languages/`. The cross-script tests (`test_security.py`,
  `test_media_deletion.py`, `tests/helpers.py`) gain the new script.
- Changed: `README.md`, `openspec/ideas.md`, `website/index.html`.
- `VERSION` in every script, `plugin.json` and `marketplace.json`.
- Plex paths used are a subset of `playback-check`'s (`/`, `/library/sections`,
  `/library/sections/{id}/all`, `/library/metadata/{ids}`, `/:/prefs`), all `GET`. No Tautulli, no
  plex.tv, no new destinations.
