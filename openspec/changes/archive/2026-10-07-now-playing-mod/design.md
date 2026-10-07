## Context

Cinemetric already ships two mods in one hooks module (`plugins/cinemetric/hooks/register.ts`): the
read-only guard and the library status line. Each has its own `userConfig` switch, and Claude Code
loads the module again whenever a switch changes, so `register` simply reads the switches and sets up
the mods that are on. The `/cinemetric-mods` command is registered in the status line's
`session.start` hook, because a module gets one `session.start` and the status line needed it first.

`server_health.py` already builds a list of current streams (`live_activity`), with tests, as part of
its full report. The full report also checks updates, tasks and settings, and can wait up to 15
seconds to see whether tasks are moving, so it's far too heavy to run every 30 seconds.

Claude Code's mod API gives us what this needs: `$.ui.open` / `ui.render` on `Pane` for the panel,
`ui.close` to learn the panel closed, `$.clock.every` for the timer (it returns a cancel function),
`$.process.run` (argument list, no shell, with a timeout) to run the script, and `$.plugin.root` to
find it.

## Goals / Non-Goals

**Goals:**
- A live view of current streams that costs nothing while it's closed.
- Reuse the tested stream code, so the panel and the `server-health` report always agree.
- Keep the Plex token out of the mod entirely.
- Follow the existing mods' shape (one file per mod, a `*-rules.ts` for the pure logic, tests).

**Non-Goals:**
- Stopping streams, messaging viewers or anything else that changes the server.
- Alerts or toasts when a stream starts (could come later on top of this).
- Tautulli data in the panel.
- Opening the panel automatically at session start.

## Decisions

### Run the Python script instead of calling Plex from the mod
The mod runs `server_health.py --now-playing` and reads its JSON. The alternative was fetching
`/status/sessions` directly from TypeScript. That would mean the mod reading the settings file and
holding the token, duplicating the address checks, TLS settings and redirect rules from the security
spec, and keeping two copies of the stream-formatting code in sync. Running the script keeps every
one of those rules in one place. The cost is starting Python every 30 seconds, which is small.

### A new `--now-playing` option rather than a new script
The stream code lives in `server_health.py`; a new option that only calls `live_activity()` reuses it
without copying. It skips `/`, snapshots and everything else, so a check is one Plex request.

### Where the command is registered
Claude Code allows a mods module only one `session.start` hook, and it refuses code that hands `$` to
a function in another file. The module's one `session.start` hook is in `status-line.tsx`, so that
hook also registers `/cinemetric-now` (a constant spec from `now-playing-rules.ts`), on or off, which
the mods spec now allows. The `command.run` hook in `now-playing.tsx` is always added too, but when the
mod is off it does nothing except return the "switch it on" text. Everything else (the `ui.render`
and `ui.close` hooks and the timer) is only set up when the switch is on.

### Timer lifetime and reloads
The repeating timer starts when the command opens the panel and is cancelled on `ui.close`. A "check
running" flag skips a turn rather than stacking checks when Plex is slow, and `$.process.run`'s
`timeoutMs: 20000` caps each one.

Any switch change reloads the whole module, and the old module's timer ends with it. Restarting the
checks for a panel that stayed open would need `now-playing.tsx`'s own code to run at
`session.start`, which the two rules above rule out (a drawing hook may not start work either). So the
`session.start` hook in `status-line.tsx` closes a Now Playing panel it finds open
(`$.ui.panes()`, then `$.ui.close`), and the user reopens it with `/cinemetric-now`. Switches change
rarely, so this costs little. That step is wrapped so a failure there can't stop the status line or
the command registration.

### Where the results live
The latest result, the last error and whether a check is running are plain module variables, like
the status line's, and a finished check calls `$.ui.invalidate` to redraw the panel. Since a reload
closes the panel, nothing needs to outlive one, so no `$.state` contract is needed. Nothing lasts past
the session, which matches "keeps nothing between sessions".

### Pure logic in `now-playing-rules.ts`
Parsing the script's output, building the summary line and each row, cutting long titles and the
error wording live in a plain TypeScript file with no `$`, like `status-line-rules.ts`, so most of the
behaviour is tested without a Claude Code session.

## Risks / Trade-offs

- [Python not on `PATH` inside Claude Code] → Try `python3`, then `python`; show the plain "needs
  Python" message in the panel instead of failing.
- [People's names on screen, for example during a screen share] → The mod is off by default and the
  panel only opens when asked; the README says what it shows.
- [Claude could run `/cinemetric-now` itself] → Harmless: it only opens a panel, and the reply never
  contains stream details, so Claude learns nothing from it.
- [The script's error text reaching the panel] → The script already writes only safe messages (it
  scrubs the token), and the mod shows just the first line, cut to 200 characters, as plain text.
- [Panel APIs differ between the terminal and the desktop app] → Use only `Box` and `Text` from
  `$.ui.resolve(e)` and size rows from the panel's width, as the existing status line does.

## Migration Plan

Ships in the next plugin version. The switch defaults to off, so nobody sees a change until they turn
it on. Rolling back is removing the files and the `userConfig` entry; nothing is stored on disk.

## Open Questions

None blocking. A stream-started toast is a natural follow-up once people have used the panel.
