## Why

The report scripts clean every piece of text that comes from Plex or Tautulli before printing it:
they remove control characters (invisible characters such as line breaks or terminal escape codes) and
cut it to 120 characters. The setup script doesn't. It prints server names straight from the user's
Plex account, and those include servers other people have shared with the user, so someone else
chooses that text. A very long name, or one with hidden characters or instruction-like text, reaches
Claude's output unfiltered. The `security` spec currently limits this rule to report scripts; this
change makes it apply to setup too.

## What Changes

- Setup cleans the three pieces of outside text it prints, the moment it receives them:
  - server names from the Plex account's server list (`finish`, and the "could not reach" error in
    `select`);
  - the name a server reports when `select` tests it;
  - Tautulli's version string (`tautulli-auto`, `tautulli`, the form, and `tautulli-wait`).
- Setup gets its own copy of the shared `clean` helper, the same one the report scripts use.
- Version bump to 0.3.2.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `security`: "Server text is treated as data" applies to every script, not just report scripts.

## Impact

- `plugins/cinemetric/skills/setup/scripts/setup.py`: add `clean` and `MAX_TITLE_LENGTH`; clean the
  values in `cmd_finish`, `test_server` and `test_tautulli`.
- No change to what users see unless a name or version contains control characters or is longer than
  120 characters.
- `VERSION` in all five scripts, `plugin.json` and `marketplace.json`.
