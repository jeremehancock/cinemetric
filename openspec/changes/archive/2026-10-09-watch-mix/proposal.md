## Why

Cinemetric can say what's on the server (`library-report`) and what gets watched (`watch-activity`),
but nothing puts the two side by side. A server owner can't ask "do we actually watch the horror I
keep adding?" or "how much of our watching is 4K?" and get an answer like "Horror is 18% of your
movies but 3% of what's watched." It's the skill planned for the website's **Watching** group, and it
reuses pieces that already exist: library listings, history from Tautulli or Plex, and Plex's own
genre filter.

## What Changes

- A new read-only skill, `watch-mix`, with one script, `watch_mix.py`. For movies and TV separately,
  it compares each group's share of the shelf with its share of watching:
  - **By genre:** each genre's share of titles and of storage, next to its share of plays and of
    watch time. A title can have several genres, so genre shares don't add up to 100%; the report
    says so.
  - **By decade:** the same, by each title's release year (a show's first year).
  - **By quality:** the same, by resolution (4K, 1080p, 720p, SD), using the file on the server now.
  - **Biggest differences:** the groups watched most above and most below their share of the shelf,
    so Claude can lead with lines like the horror example.
- **Watch time:** with Tautulli, the real time played. Without it, Plex only records finished plays,
  so watch time is each finished play times the title's length. The report says which was used.
- **Whole server by default, naming no one.** One person with `--user NAME`, only when asked.
- **Period:** the last 12 months, or `--months N`.
- **Facts only:** no "add more anime" or "remove horror" suggestions.
- Options: `--months N`, `--user NAME`, `--library NAME` (repeatable), `--top N`,
  `--source auto|tautulli|plex`, `--check`.
- README: new row in the Skills table; `watch-mix` comes off the Roadmap and out of
  `openspec/ideas.md`. Website: the new skill in the **Watching** group with a terminal demo panel
  (seventeen skills).
- Version bump to 0.31.0.

## Capabilities

### New Capabilities

- `watch-mix`: what the script requests from Plex and Tautulli, how shelf and watching shares are
  worked out by genre, decade and quality, how plays are matched to titles, how watch time is
  measured with each source, the privacy rules for a whole-server report, the options and the report
  contents.

### Modified Capabilities

- `conventions`: "Connection check" and "Media deletion setting" add the new script.
- `security`: "Only known destinations" gets a scenario saying `watch_mix.py` contacts only the
  configured Plex server and, if set up, Tautulli.
- `testing`: "Tests check the specs" adds `watch-mix` coverage and a scenario for a genre's watching
  share being worked out from the shelf's two-genre listing instead of Plex's genre filter.
- `website`: "Shows every skill" adds `watch-mix` (seventeen skills).

## Impact

- New: `plugins/cinemetric/skills/watch-mix/SKILL.md` and
  `plugins/cinemetric/skills/watch-mix/scripts/watch_mix.py` (with copies of the shared helpers
  `load_config`, `validate_url`, `PlexClient`, `TautulliClient`, `clean` and
  `media_deletion_allowed`).
- New: `tests/test_watch_mix.py` and made-up fixtures in `tests/fixtures/watch-mix/`; the new script
  listed in `tests/helpers.py` so the cross-script checks find it.
- Changed: `README.md`, `openspec/ideas.md`, `website/index.html`.
- `VERSION` in every script, `plugin.json` and `marketplace.json`.
- Plex paths, all `GET` and all already used by other scripts: `/`, `/library/sections`,
  `/library/sections/{id}/all`, `/library/sections/{id}/genre`, `/accounts`,
  `/status/sessions/history/all`, `/:/prefs`. Tautulli commands: `get_tautulli_info`, `get_history`,
  `get_users`. No plex.tv, no new destinations.
