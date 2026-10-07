## 1. Check the setting on a real server

- [x] 1.1 Confirm against the real server that `/:/prefs` returns `allowMediaDeletion` as a bool, what its default is, and that a shared (non-owner) token gets 401 or 403

## 2. Scripts

- [x] 2.1 Write the `media_deletion_allowed(client)` helper in `server_health.py`: one `/:/prefs` answer in, `True`/`False`/`None` out, every other setting discarded; reuse the existing single `/:/prefs` request; add the top-level `media_deletion_allowed` field; leave it out of `--now-playing`
- [x] 2.2 `playback_check.py`: request `/:/prefs` once per run (also with `--max-bitrate`), feed both the bitrate limit and `media_deletion_allowed` from that answer
- [x] 2.3 Copy the helper into `library_report.py`, `episode_gaps.py`, `unwatched.py`, `users_and_shares.py`, `what_to_watch.py`, `watch_activity.py` and `year_in_review.py`; add `^/:/prefs$` to each `ALLOWED_PATHS`; skip it under `--check` and when Plex isn't configured (Tautulli-only runs)
- [x] 2.4 `setup.py`: after `select` saves a server, read the setting from that server with the saved token and add `media_deletion_allowed` to the output; any failure gives `null` and keeps the save
- [x] 2.5 `changes.py`: take `media_deletion_allowed` from the first child report with a non-null value
- [x] 2.6 `dashboard.py`: same rule; show a quiet tip at the end of the Server card when it's `true`, without changing the overall status; include the field in the build output

## 3. Tell Claude about it

- [x] 3.1 Add the same short instruction to all twelve `SKILL.md` files: when `media_deletion_allowed` is `true`, end with one friendly line about switching off "Allow media deletion" (Settings, Library); at most once per conversation; never in a headline, never called a problem; silent for `false` and `null`
- [x] 3.2 `server-health/SKILL.md`: list the field in the JSON overview, place the line under "Worth a look" with one sentence on why it matters, and add the narrow exception to "Settings are facts, not advice"
- [x] 3.3 `setup/SKILL.md`: mention the tip once after a server is connected when the field is `true`

## 4. Tests

- [x] 4.1 Add a sample `/:/prefs` answer (with `allowMediaDeletion` and `PlexOnlineToken`) to the fixtures each script's tests use
- [x] 4.2 For each script: `true`, `false`, missing setting (`null`) and 403 (`null`, exit 0, not in `unavailable`); no other setting's id or value in the output; `/:/prefs` requested at most once; not requested under `--check`
- [x] 4.3 `server-health --now-playing` doesn't request `/:/prefs`; `playback-check --max-bitrate 8000` requests it once and still uses the option's limit
- [x] 4.4 `setup select`: field set on success; 403 keeps the server saved with `null`
- [x] 4.5 `changes` and `dashboard` pick the first non-null value; the dashboard shows the tip only for `true` and the status doesn't change
- [x] 4.6 All tests pass: `python3 -m unittest discover -s tests`
- [x] 4.7 Run each skill against the real server: valid JSON, existing fields unchanged, field matches what Plex shows, no tokens or other settings in the output (all report `false`, matching the server; `--check` and `--now-playing` leave it out; the dashboard shows no tip)

## 5. Docs and release

- [x] 5.1 README: mention in the skills overview or safety notes that reports point out when "Allow media deletion" is on
- [x] 5.2 `openspec validate media-deletion-tip` passes
- [x] 5.3 Bump the version (minor) in every script, `plugin.json` and `marketplace.json`
