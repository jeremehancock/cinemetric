## 1. Read current sessions in the script

- [x] 1.1 Add `^/status/sessions$` to `ALLOWED_PATHS` in `watch_activity.py`
- [x] 1.2 Copy `stream_title` (and `as_bool` if missing) from `server_health.py` and add `now_watching(client)` returning `user`, `title`, `type`, `player`, `platform`, `state`, `progress_pct` and `live_tv` for each current session
- [x] 1.3 In `build_report`, after the history report succeeds, read current sessions outside the `OWNER_ONLY` check: no Plex set up, any `ReportError` or an unexpected data shape gives `now_watching: null` and a reason in `now_watching_unavailable` (401/403 worded as "only available to the server owner's account")
- [x] 1.4 Confirm `--check` does not request `/status/sessions`

## 2. Tests

- [x] 2.1 Add a sessions sample (one episode playing, one movie paused) to `tests/fixtures/watch-activity/plex.json` and route `/status/sessions` in the fake Plex server
- [x] 2.2 Add offline tests in `tests/test_watch_activity.py` for each spec scenario: two people watching, nothing playing, Tautulli source reads sessions from Plex, shared server with Tautulli (403), Tautulli only with no Plex, sessions server error with Plex history, and no technical fields in entries
- [x] 2.3 Update any existing test that lists exactly which Plex paths were requested, and check the security allowlist tests still pass
- [x] 2.4 `python3 -m unittest discover -s tests` passes

## 3. Tell Claude about it

- [x] 3.1 watch-activity `SKILL.md`: add "who is watching Plex right now" to the `description` triggers and list `now_watching` / `now_watching_unavailable` in the JSON fields
- [x] 3.2 watch-activity `SKILL.md`: add a short "Watching now" part at the top of the report (who, what, device, playing or paused, progress; one line when nothing is playing; say it's a snapshot of that moment; when unavailable, one plain line with the reason), and point to server-health for transcoding, bandwidth or buffering
- [x] 3.3 server-health `SKILL.md`: reword the `description` so live streams are framed as stream quality (direct play vs transcode, bandwidth) and the triggers say "is anyone transcoding" / "why is Plex buffering" instead of "who is watching Plex right now"

## 4. Docs

- [x] 4.1 README: add who's watching right now to the watch-activity row of the skills table
- [x] 4.2 Website: add who's watching right now to the watch-activity feature list (and an example question) in `website/index.html`

## 5. Verify

- [x] 5.1 Run against the real server (if available): output is valid JSON, existing fields unchanged, and `now_watching` matches what Plex shows as playing
- [x] 5.2 Run `dashboard.py` and confirm the page still builds unchanged
- [x] 5.3 `openspec validate watch-activity-now-watching` passes

## 6. Release

- [x] 6.1 Bump the version to 0.10.0 in all six scripts, `plugin.json` and `marketplace.json`
