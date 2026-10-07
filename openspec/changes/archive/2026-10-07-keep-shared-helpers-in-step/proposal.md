## Why

Shared helpers are copied into every script, and the only thing keeping the copies the same is
remembering to change all of them. They have already drifted: `library-report` and `server-health`
still use an older config loader, address check and Plex client, and `clean` has three versions.
The tests also list scripts by hand, so `changes.py`'s copy of `clean` was never checked, and the
version number sits in 17 files with nothing checking they agree.

## What Changes

- One list of shared helpers, in `tools/shared_helpers.py`, says which copies must match and which
  scripts are allowed a different copy (with the reason). A test fails when copies differ.
- `python3 tools/shared_helpers.py copy NAME --from SKILL` copies a fixed helper into every other
  script, keeping each script's own Plex client name.
- A test checks every script's `VERSION`, `plugin.json` and `marketplace.json` agree.
- The security and media deletion tests find the scripts that have each helper instead of listing
  them by hand, and a test checks `tests/helpers.py` knows every skill script.
- `library-report` and `server-health` move onto the current shared helpers (`read_config_file`,
  `validate_url(url, name)`, `_NoRedirect`, `build_opener`, and for `library-report` `fetch_json`).
  Some of their error and warning messages change wording to match the other scripts (for example
  "rejected the credentials (HTTP 401 Unauthorized)" instead of "Plex rejected the token").
- `clean`'s docstring is the same in every script.
- Version bump to 0.29.1.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `conventions`: "Self-contained scripts" names where the list of shared helpers lives and the tool
  that copies them.
- `testing`: new requirements for checking shared helper copies, the version number, and that the
  tests find every script.

## Impact

- Scripts: `library_report.py`, `server_health.py` (helpers replaced), `changes.py`, `setup.py`
  (`clean` docstring), every script's `VERSION`.
- `library-report/SKILL.md`: the 401 error is now worded "rejected the credentials (401)".
- Tests: `test_security.py`, `test_media_deletion.py`, new `test_shared_helpers.py`.
- Tools: new `tools/shared_helpers.py`, listed in `tools/README.md`.
- No new network destinations, Plex paths or Tautulli commands. Nothing the reports output changes.
