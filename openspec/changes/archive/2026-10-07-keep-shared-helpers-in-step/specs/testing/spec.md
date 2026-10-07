## ADDED Requirements

### Requirement: Shared helper copies match
A test SHALL check that every copy of each shared helper listed in `tools/shared_helpers.py` matches,
apart from the scripts listed as allowed to differ and each script's own Plex client name. The test
SHALL fail when a listed helper is found in fewer than two scripts, or when a script listed as allowed
to differ doesn't exist or has no copy, so the list can't quietly stop checking anything.

#### Scenario: A shared helper is changed in one script only
- **WHEN** `clean` is changed in `unwatched.py` but not in the other scripts
- **THEN** a test fails, naming `clean` and the scripts whose copy differs

#### Scenario: A shared helper is renamed
- **WHEN** `fetch_json` is renamed in every script but not in `tools/shared_helpers.py`
- **THEN** a test fails

### Requirement: Version numbers are checked
A test SHALL check that every script's `VERSION`, `plugins/cinemetric/.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` give the same version.

#### Scenario: A version bump misses a script
- **WHEN** the version is bumped everywhere except `episode_gaps.py`
- **THEN** a test fails for `episode-gaps`

### Requirement: Tests find every script
Checks that run against every script's copy of a helper (address checks, `looks_local`, `clean`, the
Plex and Tautulli clients, the media deletion helper) SHALL find the scripts that define the helper
rather than list them by hand. A test SHALL check that `tests/helpers.py` lists every skill script on
disk, and each check SHALL fail if it finds none of the scripts known to have its helper.

#### Scenario: A new skill script is added
- **WHEN** a new skill with a script that copies `clean` and `PlexClient` is added and listed in
  `tests/helpers.py`
- **THEN** the cleaning and Plex client checks run against its copies without any other test change

#### Scenario: A new script isn't known to the tests
- **WHEN** a new skill script is added but not listed in `tests/helpers.py`
- **THEN** a test fails
