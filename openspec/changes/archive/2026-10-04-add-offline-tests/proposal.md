## Why

Cinemetric has about 3,200 lines of Python across five scripts and no automated tests. Every change is
checked by hand against one real Plex server, so mistakes in counting, duplicate detection or the
safety checks can slip through when that server doesn't happen to contain the case that broke. A
small offline test suite gives a quick, repeatable check before each change, without needing a Plex
server at all.

## What Changes

- Add a `tests/` folder at the repository root with tests for all five scripts, written with Python's
  built-in `unittest` module. Nothing is installed.
- Tests never contact Plex, plex.tv or Tautulli. Most tests call the scripts' functions directly with
  small, hand-written sample items. Tests that cover a whole report swap the script's network layer
  for a fake one that answers from saved sample responses kept in `tests/fixtures/`.
- Tests never read or write the user's real Cinemetric settings or dashboard files. Each test points
  the settings and data folders at a temporary folder.
- A safety net in the test setup makes any accidental real network connection fail the test.
- Coverage starts with the parts most likely to break quietly:
  - `library-report`: duplicate detection (within and across libraries), resolution buckets, 10-bit
    detection, unmatched items, housekeeping and totals.
  - Security rules shared by every script: address checks, the path and command allowlists, refusing
    redirects, hiding tokens in error messages, and cleaning server text.
  - `server-health`, `watch-activity` and `dashboard`: their summarising and flagging functions, and
    the dashboard's HTML escaping.
  - `setup`: address cleaning and the private-file helpers.
- No change to what any script does for users. Script code changes only if a function can't be
  tested without one, and any such change keeps behavior the same.
- Not included: tests against a live server, and running the tests automatically on GitHub. Both can
  be added later.

## Capabilities

### New Capabilities
- `testing`: how the project's automated tests are organized and run, and the rules they follow
  (offline only, standard library only, never touch the user's real settings).

### Modified Capabilities
<!-- None. The scripts' required behavior doesn't change; the tests check the existing specs. -->

## Impact

- New files: `tests/` (test modules, a small shared helper, sample responses in `tests/fixtures/`).
- Scripts under `plugins/cinemetric/skills/*/scripts/` are imported by the tests but not changed,
  unless a small change is needed to make a function testable.
- The `tests/` folder sits outside `plugins/`, so it is not part of what users install.
- No version bump: nothing users see changes.
- No new dependencies.
