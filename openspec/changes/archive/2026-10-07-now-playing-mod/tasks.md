## 1. Script: now playing only

- [x] 1.1 Add `--now-playing` to `server_health.py`: request only `/status/sessions`, print
  `cinemetric_version`, `checked_at` and `live_activity`, read no snapshots, exit with `error:` on failure
- [x] 1.2 Add tests in `tests/test_server_health.py`: only `/status/sessions` is requested, the output
  shape, nothing playing, and an unreachable server
- [x] 1.3 Mention `--now-playing` in the server-health `SKILL.md` options only if Claude needs it there
  (it's for the mod, so most likely a one-line "used by the Now Playing mod, not by this skill")

## 2. Mod: switch, command and state

- [x] 2.1 Add the `now_playing_pane` boolean to `plugin.json` `userConfig` (title "Now Playing",
  default false, a plain description saying it checks the server only while its panel is open)
- [x] 2.2 Add the `now` entry to `MODS` in `hooks/mods.ts` (`isUserOnlyOff: false`)
- [x] 2.3 Keep the panel's results in module variables (no `$.state` contract needed, see design.md)
- [x] 2.4 Register `/cinemetric-now` in the existing `session.start` hook alongside `/cinemetric-mods`,
  on or off, and close a Now Playing panel left open by a reload there

## 3. Mod: panel and checks

- [x] 3.1 Write `hooks/now-playing-rules.ts`: parse the script's output, build the summary line and
  stream rows, cut long titles with `…`, the `and <n> more` line, and the error wording
- [x] 3.2 Write `hooks/now-playing.tsx`: the `command.run` hook (off reply, or open the panel), the
  `Pane` `ui.render` hook, the `ui.close` hook, and the 30-second timer with skip-if-running and a
  20-second timeout per check, running `python3` then `python`
- [x] 3.3 Wire it into `register.ts` behind the `now_playing_pane` switch
- [x] 3.4 Make sure no stream details reach Claude: the command reply is fixed text, and nothing is
  added as context or a notice

## 4. Tests for the mod

- [x] 4.1 `tests/now-playing.test.tsx`: off reply and nothing run; on opens the panel; one check on
  open and one per 30 seconds; no overlapping checks; checks stop on close and when switched off
- [x] 4.2 Tests for the rules file: summary and row text (direct play, direct stream, transcode with
  video/audio, paused, Live TV), cut titles, `and <n> more`, each error message, last good result kept
- [x] 4.3 Update `tests/command.test.ts` and `tests/test_mods.py` for the new mod and command
- [x] 4.4 Run `claude plugin validate plugins/cinemetric`, `tsc -p plugins/cinemetric`,
  `claude plugin test plugins/cinemetric` and the Python test suite

## 5. Docs, website and version

- [x] 5.1 README: add `now` to the Mods table (off by default, `/cinemetric-now`, checks only while
  open, shows people's names) and re-read every "background" line so none reads as a promise about mods
- [x] 5.2 SECURITY.md: one line that Now Playing runs the read-only server-health script while its
  panel is open, and that what it shows is never sent to Claude
- [x] 5.3 Website: add the Now Playing card to the Mods section, per the website delta spec
- [x] 5.4 Update the plugin description in `plugin.json` and `marketplace.json` to mention Now Playing
- [x] 5.5 Bump the version (every script's `VERSION`, `plugin.json`, `marketplace.json`) to 0.25.0

## 6. Try it for real

- [x] 6.1 Load the plugin with hot reloading, switch `now` on and off, open and close the panel, and
  check it against a real stream (direct play and a transcode) in the terminal
