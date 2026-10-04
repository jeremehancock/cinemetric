## Context

`watch_activity.py`'s `load_config` calls `read_config_file()` first, every time. That function
refuses a file owned by another user or readable by others, and fails on a file that isn't valid
JSON. Only afterwards does `load_config` let the environment variables win.

The other report scripts do it the other way round: if `PLEX_URL` and `PLEX_TOKEN` are both set, they
skip the file entirely, and `verify_tls` stays on.

`watch-activity` differs from them in one way: it can also use Tautulli, whose settings may live only
in the file.

## Goals / Non-Goals

**Goals:**
- With both Plex environment variables set, `watch-activity` handles Plex exactly like the other
  report scripts.
- A config file problem never stops a report that doesn't need the file.
- When the file is needed only for Tautulli and can't be used, the user still gets a Plex report and
  is told why Tautulli was skipped.

**Non-Goals:**
- Loosening the file's safety check. An unsafe file is still never read.
- Changing the other scripts, or adding new environment variables (for example for `verify_tls`).

## Decisions

**Read the file only when the environment leaves a gap.** `load_config` checks the environment first:
- Plex comes from the environment when `PLEX_URL` and `PLEX_TOKEN` are both set, with `verify_tls` on
  (as in the other scripts).
- Tautulli comes from the environment when `TAUTULLI_URL` and `TAUTULLI_API_KEY` are both set.
- Only if one of them is still missing is the file read.

**A file problem is fatal only if Plex needs the file.** If Plex is set up from the environment and
reading the file fails, `load_config` doesn't raise. It leaves Tautulli unset and records the error
message as `tautulli_problem`. Then:
- `build_report` with `--source auto` falls back to Plex, with `fallback_reason` "Tautulli settings
  couldn't be read: <reason>".
- `--source tautulli` stops with that same reason.
- `check` reports `tautulli: {ok: false, error: <reason>}`.

If Plex isn't fully set up from the environment, the file problem stops the script as it does today.

*Alternative considered: skip the file only when all four environment variables are set.* Simpler, but
a user with only the Plex variables set would still be blocked by a file problem, which is the bug.

*Alternative considered: ignore file problems silently.* That hides a permissions problem the user
should fix, and leaves them wondering why Tautulli isn't used.

## Risks / Trade-offs

- [Someone relies on `verify_tls: false` in the file while setting Plex through the environment] →
  `library-report` and `server-health` already ignore it in that case, so they'd see the same error
  there. Mention the change in the commit message.
- [The file's error message includes its path] → It already does today, and the path isn't secret.
  The messages come from `read_config_file`, which never includes the file's contents.
