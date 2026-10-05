## Why

`watch-activity` only looks backward, so asking it "what's being watched?" never mentions the people
watching right now. That's surprising for a skill called "watch activity". Today the only way to see
current viewers is `server-health`, which presents them as a technical check (transcoding, bandwidth)
rather than as part of what people are watching.

## What Changes

- The watch-activity report gets a `now_watching` section: one entry per current Plex session with
  who, what, which device, whether it's playing or paused, how far along it is, and whether it's Live
  TV. Technical details (direct play vs transcode, bandwidth, source quality) stay in `server-health`.
- It is always read from Plex's `/status/sessions`, whichever source the history comes from. That
  means one new allowed Plex path in `watch_activity.py`.
- Getting current sessions is optional. If it fails (Plex isn't set up, the account isn't the owner's,
  Plex can't be reached), the history report is still produced, `now_watching` is `null` and
  `now_watching_unavailable` says why. It never causes `OWNER_ONLY` or any other error by itself.
- `SKILL.md` for watch-activity shows a short "Watching now" part at the top of the report, and its
  description starts triggering on plain "who's watching Plex right now?" questions.
- `SKILL.md` for server-health keeps its live streams section, but its description is reworded so it
  triggers on the technical side (transcoding, buffering, bandwidth) instead of plain "who's watching".
- The dashboard doesn't change. It already leaves out what's playing now (its page is only updated on
  request) and ignores the new field.
- README and website: the watch-activity feature lists mention who's watching right now.
- Version bump to 0.10.0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `watch-activity`: "Sources used" adds `/status/sessions`; "Report contents" adds `now_watching` and
  `now_watching_unavailable`; a new requirement says what each current session contains and that a
  failure here never stops the report.

## Impact

- `plugins/cinemetric/skills/watch-activity/scripts/watch_activity.py`: new allowed path and a small
  function that reads current sessions (adapted from `server_health.py`'s `stream_title` and
  `live_activity`, since each script is self-contained).
- `plugins/cinemetric/skills/watch-activity/SKILL.md`: description, field list and presentation.
- `plugins/cinemetric/skills/server-health/SKILL.md`: description wording only.
- `tests/test_watch_activity.py` and its fixtures: offline tests for the new scenarios.
- `README.md` skills table and `website/index.html` watch-activity feature list.
- `VERSION` in all six scripts, `plugin.json` and `marketplace.json`.
