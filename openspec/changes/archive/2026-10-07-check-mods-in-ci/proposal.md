## Why

The mods' tests (119 of them, for the read-only guard, the status line and Now Playing) only run when
someone types `claude plugin test plugins/cinemetric`. GitHub runs only the Python tests, so a change
that breaks the guard can still merge with a green check. Separately, the guard and the status line
work out where Cinemetric keeps its settings file and snapshots on their own, in TypeScript, and
nothing checks they still agree with the Python scripts. If the settings location drifted, the guard
would quietly stop protecting the token.

## What Changes

- The GitHub workflow gets a second job that installs a pinned Claude Code version and runs
  `claude plugin test plugins/cinemetric`. It needs no login and no secrets.
- **All tests passed** succeeds only when both the Python tests and the mod tests pass.
- A Python test checks that the hooks find the settings file, the data folder and the snapshot
  folders the same way the scripts do, including the patterns for server folder and snapshot file
  names.
- `tests/README.md` says how to run the mod tests and that GitHub runs them.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `testing`: "Tests run on GitHub" and "One summary check" cover the mod tests; a new requirement
  checks that the hooks and scripts agree on file locations.

## Impact

- `.github/workflows/tests.yml`: new `mods` job, summary job waits for it.
- New `tests/test_hooks_match_scripts.py`.
- `tests/README.md`.
- No change to the plugin itself, so no version bump.
