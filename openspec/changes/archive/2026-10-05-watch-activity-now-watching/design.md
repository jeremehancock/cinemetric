## Context

`watch_activity.py` builds a history report from Tautulli or Plex. `server_health.py` already reads
current sessions from Plex's `/status/sessions` (in `live_activity`) and turns each one into a stream
entry with user, title, device, progress and a lot of technical detail. Each skill's script is a
single self-contained file using only the standard library, so there is no shared module to import
from. The dashboard runs `watch_activity.py` and deliberately leaves out what's playing now.

## Goals / Non-Goals

**Goals:**
- A watch-activity report that includes who is watching right now, in plain terms.
- The history report keeps working exactly as before in every case where it works today.
- Clear routing: plain "who's watching?" goes to watch-activity, technical stream questions go to
  server-health.

**Non-Goals:**
- Playback method, bandwidth, transcode details or buffering advice in watch-activity.
- Showing current sessions on the dashboard.
- Reading current activity from Tautulli (`get_activity`).

## Decisions

### Always read current sessions from Plex

Plex's `/status/sessions` is used whichever source the history comes from.

- Alternative: use Tautulli's `get_activity` when Tautulli is the source. Rejected because it adds a
  second parsing path for the same facts, and Plex is set up for nearly everyone (it's the first step
  of setup). The rare Tautulli-only setup just gets `now_watching: null` with a reason.

### Copy a trimmed version of the session code instead of sharing it

`stream_title` is copied as is, and a new `now_watching(client)` keeps only the user-facing fields
from `live_activity`.

- Alternative: move session parsing into a shared module. Rejected because every script is
  deliberately standalone (one file, no imports beyond the standard library), and the copied code is
  about 30 lines.

### Optional, never fatal

`now_watching` is read after the history report succeeds, wrapped like server-health's `optional`
helper: any `ReportError` becomes `now_watching: null` plus a reason, with 401/403 reworded as "only
available to the server owner's account". It runs outside the `OWNER_ONLY` check so a refused
sessions request can't be mistaken for refused history. Unexpected data shapes (`AttributeError`,
`KeyError`, `TypeError`, `ValueError`) are caught the same way.

- Alternative: fail the whole report. Rejected: someone asking about last month's viewing shouldn't
  get nothing because a live snapshot failed.

### Field names match server-health

Entries use the same names as server-health's stream entries (`user`, `title`, `type`, `player`,
`platform`, `state`, `progress_pct`, `live_tv`) so the two skills describe the same session the same
way.

### Routing through descriptions

The watch-activity description adds "who is watching Plex right now". The server-health description
changes "who is streaming right now (direct play vs transcode, bandwidth)" to wording about stream
quality, and its trigger list changes "who is watching Plex right now" to "is anyone transcoding" /
"why is Plex buffering". Server-health's report itself is unchanged.

## Risks / Trade-offs

- [Two skills can show the same sessions] → They show different sides (who/what vs how it's being
  delivered), and the descriptions route questions to one or the other.
- [One more request per report] → `/status/sessions` is a single small request; the history paging
  costs far more.
- [The snapshot is from when the script ran, not when the user reads it] → `SKILL.md` says it's a
  snapshot of that moment, as server-health's does.
- [Existing tests' fake servers don't answer `/status/sessions`] → Those tests then get
  `now_watching: null`, which doesn't affect what they check. Tests that list exactly which requests
  were made are updated to include the new path.
