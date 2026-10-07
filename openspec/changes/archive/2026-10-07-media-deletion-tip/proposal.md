## Why

Plex's "Allow media deletion" setting (Settings, Library) is the one real lock against an app deleting
media files: when it's off, Plex refuses to delete them for anyone, Claude included. SECURITY.md and
the website already recommend switching it off, but nothing in the plugin tells a user whether their
own server has it on. Most people never read SECURITY.md, and Plex usually has the setting on, so the
tip should reach them in the reports they actually run, not only in the server health check.

## What Changes

- Every Cinemetric script that reads from Plex (`setup`, `library-report`, `server-health`,
  `watch-activity`, `users-and-shares`, `unwatched`, `what-to-watch`, `episode-gaps`,
  `playback-check`, `year-in-review`) reads Plex's `/:/prefs` at most once per run, keeps only
  `allowMediaDeletion`, and adds a top-level `media_deletion_allowed` field: `true`, `false` or `null`
  when it can't be read. Reading it never stops or fails a report.
- `/:/prefs` is added to the allowed Plex paths of the scripts that don't already have it. It stays
  out of `--check` and server-health's `--now-playing` mode.
- `changes` and `dashboard` take the value from the reports they already run. The dashboard shows it
  as a quiet tip at the end of its Server card, without changing the overall status.
- Every `SKILL.md` tells Claude: when `media_deletion_allowed` is `true`, end the reply with one short,
  friendly line saying that Plex lets apps delete media files and that switching off "Allow media
  deletion" (Settings, Library) stops that. Mention it at most once per conversation, and never as a
  problem or in the headline.
- `server-health`'s "settings are facts, not advice" rule gets a narrow exception for this one tip.
- No change to the read-only guard, SECURITY.md or the website wording about the setting.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `conventions`: a new shared rule for reading the setting and for how every `SKILL.md` mentions it.
- `setup`, `library-report`, `server-health`, `watch-activity`, `users-and-shares`, `unwatched`,
  `what-to-watch`, `episode-gaps`, `playback-check`, `year-in-review`: `/:/prefs` added to (or kept
  in) the paths each script may request, read only for this setting.
- `playback-check`: `/:/prefs` is now requested even when `--max-bitrate` is given, still at most once.
- `changes`, `dashboard`: carry the value through from the reports they run; the dashboard shows it.

## Impact

- Ten scripts gain a copied helper, `media_deletion_allowed(client)`, plus an `ALLOWED_PATHS` entry
  where it's missing. `changes.py` and `dashboard.py` read the field from their child reports.
- Twelve `SKILL.md` files get the same short instruction.
- Tests: a sample `/:/prefs` answer for each script's fixtures, and tests that only the one setting
  is kept and that a refused request leaves the field `null`.
- One more Plex request per report run (small: the settings list).
- Version bump across every script, `plugin.json` and `marketplace.json`.
