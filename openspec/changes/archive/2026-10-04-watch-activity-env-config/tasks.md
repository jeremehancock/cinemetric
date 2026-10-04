## 1. Read the file only when needed

- [x] 1.1 In `load_config`, take Plex from `PLEX_URL`/`PLEX_TOKEN` (with certificate checking on) and Tautulli from `TAUTULLI_URL`/`TAUTULLI_API_KEY` when each pair is fully set
- [x] 1.2 Read the config file only if Plex or Tautulli is still missing; if Plex came from the environment, catch a file error and record it as `tautulli_problem` instead of raising

## 2. Report the Tautulli problem

- [x] 2.1 `build_report`: with `--source auto`, use "Tautulli settings couldn't be read: <reason>" as `fallback_reason`; with `--source tautulli`, stop with that reason
- [x] 2.2 `check`: show `tautulli: {ok: false, error: <reason>}` and `ok: false` when there's a `tautulli_problem`

## 3. Verify

- [x] 3.1 Plex env vars set + config file readable by others: `watch-activity` builds a Plex report, `fallback_reason` explains, and the file's contents are never read (it's refused by the safety check)
- [x] 3.2 Plex env vars set + empty (damaged) config file: same result
- [x] 3.3 Plex env vars set + `--source tautulli` with an unusable file: stops with the reason; `--check` shows it under Tautulli
- [x] 3.4 No Plex env vars + config file readable by others: still stops with the `chmod 600` error, as before
- [x] 3.5 All four env vars set: Tautulli is used and the file isn't opened

## 4. Release

- [x] 4.1 Bump the version to 0.3.3 in all five scripts, `plugin.json` and `marketplace.json`
