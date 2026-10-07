## MODIFIED Requirements

### Requirement: Self-contained scripts
Each script SHALL run on its own, without importing code from another skill. Shared helpers (config
loading, address checks, the GET-only Plex client, text cleaning, and finding and reading snapshots)
are copied into each script that needs them. A change to one copy of a shared helper SHALL be made to
every copy.

The list of shared helpers whose copies must match SHALL live in `tools/shared_helpers.py`, together
with each script that is allowed a different copy and the reason. The only difference allowed
between matching copies is the script's own Plex client name (`cinemetric-<skill>`).
`python3 tools/shared_helpers.py copy NAME --from SKILL` SHALL copy one helper from that skill's
script into every other script that has a copy, keeping each script's own client name.

#### Scenario: Fixing a bug in a shared helper
- **WHEN** a bug is fixed in `load_config`, `validate_url`, `PlexClient`, `clean` or the snapshot
  reading helper in one script
- **THEN** the same fix is applied to every script that has a copy of that helper

#### Scenario: Copying a fixed helper
- **WHEN** `PlexClient.get` is fixed in `episode_gaps.py` and the tool copies it with
  `copy PlexClient.get --from episode-gaps`
- **THEN** every other script with a matching copy gets the fix, each still sending its own
  `cinemetric-<skill>` client name, and `server-health` (allowed a different copy) is left alone

#### Scenario: A script needs a different copy
- **WHEN** a script needs its own version of a shared helper
- **THEN** it is added to that helper's entry in `tools/shared_helpers.py` with the reason
