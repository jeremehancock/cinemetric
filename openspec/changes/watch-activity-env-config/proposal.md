## Why

When `PLEX_URL` and `PLEX_TOKEN` are both set, `library-report` and `server-health` never open the
config file. `watch-activity` always opens it first, so a config file that other users can read, or
one that's empty or damaged, makes `watch-activity` fail even though Plex is fully set up through
environment variables. The same setup then works for two skills and fails for the third, with an
error about a file the user isn't relying on.

## What Changes

- When `PLEX_URL` and `PLEX_TOKEN` are both set, `watch-activity` uses them for Plex without reading
  the config file, like the other report scripts.
- The config file is then only needed for Tautulli, and only if `TAUTULLI_URL` and `TAUTULLI_API_KEY`
  aren't both set. If the file can't be used (other users can read it, or it's damaged), Tautulli is
  treated as unavailable, with the reason. `--source auto` falls back to Plex and reports that reason
  in `fallback_reason`; `--source tautulli` fails with it; `--check` shows it under Tautulli.
- The file's safety check is unchanged. An unsafe file is never read; it just no longer blocks a
  report that doesn't need it.
- When the environment doesn't fully set up Plex, nothing changes: the file is read, and any problem
  with it stops the script as today.
- Version bump to 0.3.3.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `conventions`: "Settings location" adds that a script reads the config file only when the
  environment doesn't already provide what it needs.
- `watch-activity`: "Choosing a source" adds that an unusable config file makes Tautulli unavailable
  (with the reason) instead of stopping the report, when Plex comes from the environment.

## Impact

- `plugins/cinemetric/skills/watch-activity/scripts/watch_activity.py`: `load_config`, `build_report`
  and `check`.
- Users who set both Plex environment variables and also have a `verify_tls: false` in the config file
  will now have certificate checking on for Plex in `watch-activity`, matching the other report
  scripts.
- `VERSION` in all five scripts, `plugin.json` and `marketplace.json`.
