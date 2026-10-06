## Why

"Shared libraries nobody has watched in a while" is on the README Roadmap. `users-and-shares`
already says who can see each library and when each person last played *anything*, but not whether
anyone actually uses the libraries they were given. An owner who shares five libraries with a friend
can't tell that the friend only ever watches TV, or that a whole library (say "Fitness" or "Home
Videos") hasn't been touched by anyone it's shared with in months.

The watch history the skills already read says which library each play came from (Plex records
`librarySectionID` on each play; Tautulli can be asked for one library's plays), so this is a
cross-reference of data Cinemetric can already reach, with no new kind of access.

## What Changes

- The script reads the last `--inactive-days` days (default 90) of watch history, from Tautulli
  when it's set up (any play counts, finished or not), otherwise from Plex's own history (finished
  plays only).
- Each library gets `played_by` (the people it's shared with who played something from it in that
  window) and `played_by_count`. Pending people and the owner are not counted.
- A new top-level `library_activity` says which source was used, how many days it covers, and whether
  the whole window was read.
- A new `worth_a_look` kind, `unused_library`, lists libraries shared with at least one person where
  none of them played anything from it in the window. Libraries shared only with people invited
  within the window are left out, since they haven't had the time.
- Facts only: the report and `SKILL.md` never suggest unsharing a library or removing anyone.
- The Tautulli command `get_history` is added to this script's allowed commands. No new Plex or
  plex.tv addresses.
- `SKILL.md`: describes the new fields and flag, triggers on questions like "which shared libraries
  does nobody use?", and explains the Plex "finished plays only" caveat for this view too.
- Dashboard: the Sharing section shows the new flag as one sentence with the library names (library
  names aren't personal, so they're shown even when people's names are hidden).
- README: the `users-and-shares` Roadmap item is removed. `openspec/ideas.md`: the note is removed.
  Website: the users-and-shares feature list mentions which shared libraries get used.
- Version bump to 0.17.0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `users-and-shares`: reads watch history per library (new Tautulli command), adds `played_by` per
  library, `library_activity`, and the `unused_library` worth-a-look item; "Options" now also uses
  `--inactive-days` for the library window.
- `dashboard`: the Sharing section shows the `unused_library` item.

## Impact

- `plugins/cinemetric/skills/users-and-shares/scripts/users_and_shares.py` and its `SKILL.md`
- `plugins/cinemetric/skills/dashboard/scripts/dashboard.py`
- `tests/test_users_and_shares.py`, its fixtures, and `tests/test_dashboard.py`
- README Roadmap, `openspec/ideas.md`, `website/index.html`
- Version in all scripts, `plugin.json` and `marketplace.json`
- A few more requests per run: one paged read of recent Plex history, or with Tautulli one per
  library (one page per 1,000 plays).
