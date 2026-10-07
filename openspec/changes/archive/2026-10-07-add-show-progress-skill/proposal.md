## Why

People watch TV a series at a time, but no skill follows a person through a series. `watch-activity`
counts plays and lists single episodes someone left unfinished, `unwatched` finds shows nobody has
touched at all, and `title-lookup` counts episodes finished for one show. None of them can say "Sam is
caught up on Severance, Alex is four episodes behind, and Jo stopped The Bear in March". That's useful
to the server owner (which shows are actually followed, which ones people gave up on, which new
episodes are waiting for someone) and to the people watching ("where was I?"). It also covers the
roadmap item "`unwatched`: shows people stopped watching partway through", which fits better here.

## What Changes

- A new read-only skill in the Watching group, `show-progress`, with one script,
  `show_progress.py`. For each TV show someone has finished at least one episode of, it reports each
  person's place in the show:
  - **How far along:** the furthest episode they finished (by season and episode order, so
    rewatching season 1 doesn't move them back), how many episodes they finished, how many episodes
    on the server come after that point, and the next episode to watch.
  - **Status:** `caught_up` (nothing on the server after their furthest episode), `new_episodes`
    (they had watched everything on the server, and new episodes were added since their last play),
    `in_progress` (partway through, played recently) or `stopped` (partway through, nothing played
    from the show in `--stopped-months` months, 3 by default).
  - **Recently added:** shows that got new episodes in the last `--new-days` days (30 by default),
    and which of the people following each show have or haven't finished them.
- Starting partway in (for example jumping straight to season 3) doesn't count earlier episodes as
  left to watch. Specials (season 0) are left out of positions and counts.
- Uses Tautulli's history when it's set up, otherwise Plex's own history, with the same `--source`
  rules as `watch-activity`. Plex's history only records finished episodes, so the report says so and
  can't tell a half-watched episode from an unplayed one.
- Names people, like `watch-activity`, since it's the server owner's own report. `--user NAME`
  narrows the report to one person (same matching rules as `watch-activity`), and `--show NAME`
  narrows it to one show.
- **Facts only:** it never suggests removing a show nobody follows.
- Options: `--show NAME`, `--user NAME`, `--library NAME` (repeatable), `--stopped-months N`,
  `--new-days N`, `--top N`, `--source auto|tautulli|plex`, `--check`.
- README: new row in the Skills table and an example question; the `unwatched` "stopped partway
  through" roadmap item is removed (this skill covers it) and the rest of that line stays. A short
  note is added to `openspec/ideas.md` saying the same. Website: the new skill in the Watching group
  with a terminal demo panel (fifteen skills).
- Version bump to 0.29.0.

## Capabilities

### New Capabilities

- `show-progress`: what the script requests from Plex and Tautulli, how history and the episode
  list are read, how each person's place in a show and their status are worked out (rewatches,
  starting partway in, specials, episodes Plex can't find), recently added episodes, narrowing to one
  person or show, owner-only history, and the options.

### Modified Capabilities

- `conventions`: "Connection check" and "Media deletion setting" add the new script.
- `security`: "Only known destinations" gets a scenario saying `show_progress.py` contacts only the
  configured Plex server and, if set up, Tautulli.
- `testing`: "Tests check the specs" adds `show-progress` coverage and a scenario for a rewatch that
  makes someone look behind.
- `website`: "Shows every skill" adds `show-progress` (fifteen skills).

## Impact

- New: `plugins/cinemetric/skills/show-progress/SKILL.md` and
  `plugins/cinemetric/skills/show-progress/scripts/show_progress.py` (with copies of the shared
  helpers `load_config`, `validate_url`, `PlexClient`, `TautulliClient`, `clean` and
  `media_deletion_allowed`, and of `watch-activity`'s source choice and person matching).
- New: `tests/test_show_progress.py` and made-up fixtures in `tests/fixtures/show-progress/`. The
  cross-script security and media deletion tests gain the new script.
- Changed: `README.md`, `openspec/ideas.md`, `website/index.html`.
- `VERSION` in every script, `plugin.json` and `marketplace.json`.
- No new kinds of requests: the Plex paths (`/`, `/library/sections`, `/library/sections/{id}/all`,
  `/status/sessions/history/all`, `/accounts`, `/:/prefs`) and Tautulli commands
  (`get_tautulli_info`, `get_history`, `get_users`) are all already used read-only by other skills.
  No new destinations.
