## Why

Every Cinemetric skill answers a question in the chat, but some server owners want the facts in a
spreadsheet they can sort, filter, print or keep: every movie and show, plus the server's details and
the things worth tidying up, all in one place. Plex has no built-in way to save that. It's the skill
planned for the website's **Your server** group, next to `dashboard` and `changes`, the other skills
that save files on the user's computer, and it reuses what already exists: the library listings and
collection lookups other scripts make, and the reports of five existing skills.

## What Changes

- A new read-only skill, `export`, with one script, `export.py`. It saves one Excel workbook
  (`.xlsx`, which Excel, Numbers, LibreOffice and Google Sheets all open) with a tab for each part:
  - **Movies** and **TV Shows:** one tab each, holding every movie library and every TV library. One
    row per movie, and one per show (or one per episode with `--tv episodes`), each tab with only the
    columns that fit it: library, title, year, date added, length, resolution, codecs, container, size, versions,
    whether Plex can't find the file, content rating, watched status for the signed-in Plex account,
    date last watched and collections. Read by the export script itself.
  - **Server:** the server's name, version, platform, update available, remote access, streaming and
    maintenance settings, things worth a look, and each library's size. Nothing that changes moment
    to moment: no streams playing now, and no CPU or memory use. From `server-health` and `library-report`.
  - **Issues:** one row per issue: files Plex can't find, unmatched titles and titles with no poster
    (from the export's own library read, so every one is listed), duplicate copies, the same title in
    more than one library and titles only in SD or 720p (from `library-report`).
  - **Episode gaps:** one row per show and season with missing episodes or seasons. From
    `episode-gaps`.
  - **Playback:** files likely to transcode on common devices and why. From `playback-check`, with
    its history part switched off so no people or devices are in the file.
  - **Subtitles:** titles with audio in another language and no subtitles in the user's language, no
    subtitles at all, or tracks with no language set. From `subtitles-and-languages`.
- **Built like the dashboard:** the other tabs come from running those skills' scripts, so they
  follow exactly the same rules. A tab whose report fails holds a line saying why, and the rest of the
  workbook is still saved. `--skip TAB` leaves tabs out (useful because the playback and subtitle
  checks take longest).
- **Nothing in the file can run:** every value is written as plain text or a number, never as a
  formula, and the file has no macros or links to other files or websites.
- **Where it's saved:** Cinemetric's data folder (the private folder the dashboard uses), or a
  folder or file the user names with `--output`. The file is readable only by the user. A file the
  user named is never replaced unless `--replace` is given.
- **No other people in the file:** no names, devices or viewing history. Watched status comes from
  the signed-in account's own view of the library.
- **The chat gets a summary, not the list:** where the file is, how many rows each tab has, and
  anything that couldn't be read.
- Options: `--library NAME` (repeatable), `--tv shows|episodes`, `--language CODE` (repeatable, for
  the Subtitles tab), `--skip TAB` (repeatable), `--output PATH`, `--replace`, `--check`.
- README: new row in the Skills table; `export` comes off the Roadmap and out of `openspec/ideas.md`.
  Website: the new skill in the **Your server** group with a terminal demo panel (eighteen skills).
- Version bump to 0.32.0.

## Capabilities

### New Capabilities

- `export`: what the script requests from Plex and which scripts it runs, each tab's rows and
  columns, collections, how a failed report is shown, the workbook format and why nothing in it can
  run, where the file is saved and when it may be replaced, the options and the JSON summary.

### Modified Capabilities

- `conventions`: "Skill shape" adds `export` to the scripts that write their file by fixed rules;
  "Connection check" and "Media deletion setting" add the new script; "Settings location" says
  exported workbooks go in the data folder by default.
- `security`: "Only known destinations" says what `export.py` contacts (only the configured Plex
  server, itself and through the scripts it runs, even when Tautulli is set up); "Private files" adds
  exported workbooks and leaves a user-named folder alone; "Server text is treated as data" adds that
  the workbook stores server text only as plain text.
- `testing`: "Tests check the specs" adds `export` coverage and a scenario for a title being written
  as a formula.
- `website`: "Shows every skill" adds `export` (eighteen skills).

## Impact

- New: `plugins/cinemetric/skills/export/SKILL.md` and
  `plugins/cinemetric/skills/export/scripts/export.py` (with copies of the shared helpers
  `load_config`, `validate_url`, `PlexClient`, `clean`, `media_deletion_allowed`, `data_dir` and
  `ensure_private_dir`, and the dashboard's way of running other scripts).
- New: `tests/test_export.py` and made-up fixtures in `tests/fixtures/export/`; the new script listed
  in `tests/helpers.py` so the cross-script checks find it.
- Changed: `README.md`, `openspec/ideas.md`, `website/index.html`.
- `VERSION` in every script, `plugin.json` and `marketplace.json`.
- Plex paths the export script requests itself, all `GET` and all already used by other scripts: `/`,
  `/library/sections`, `/library/sections/{id}/all`, `/library/sections/{id}/collections`,
  `/library/collections/{id}/children`, `/:/prefs`. Scripts it runs: `server_health.py`,
  `library_report.py`, `episode_gaps.py`, `playback_check.py` (with `--days 0`, so no Tautulli
  request) and `subtitles_and_languages.py`. No Tautulli, no plex.tv, no new destinations.
- No changes to the scripts it runs.
