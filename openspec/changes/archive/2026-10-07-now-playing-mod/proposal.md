## Why

Today the only way to see who is streaming from Plex is to ask Claude for a server health or watch
activity report, which is a full one-off answer. "What's playing right now" changes minute to minute,
and a mod (unlike a skill) can stay on screen and keep itself up to date, so a small live panel fits
it better than a report.

## What Changes

- A new mod, `now` (Now Playing), off by default, with its own switch `now_playing_pane` in
  `plugin.json` and a row in `/cinemetric-mods`.
- A new slash command, `/cinemetric-now`, that opens a Now Playing panel in Claude Code listing each
  current stream: who, what, on which device, paused or playing, how far in, and whether it's direct
  play, direct stream or transcode (and what is being transcoded), with totals at the top.
- While the panel is open it checks again about every 30 seconds. Closing the panel, switching the mod
  off, or the session ending stops the checks. Nothing is checked while the panel is closed.
- The command is always listed, even when the mod is off. When it's off, typing it opens nothing,
  contacts nothing and replies: `Now Playing is off. Type /cinemetric-mods now on to switch it on.`
- `server_health.py` gets a `--now-playing` option that asks Plex only for the current streams and
  prints just that part, so the mod reuses the existing, tested stream code and never handles the
  Plex token itself.
- The panel's contents are drawn for the user only and never sent to Claude.
- README, SECURITY.md and the website: describe the new mod, saying plainly that it checks the
  server only while its panel is open. The existing "nothing runs in the background" lines are about
  snapshots and stay true, but each one is re-read so none of them reads as a promise about mods.
- Version bump (a script changes).

## Capabilities

### New Capabilities
- `now-playing-pane`: the Now Playing mod: its switch, the always-listed command and its reply when
  off, what the panel shows, when it checks the server and when it stops, how errors look, and its
  safety rules.

### Modified Capabilities
- `mods`: "a mod that is switched off SHALL add no hooks" gains an exception: an off mod may keep
  its own slash command listed, as long as that command only replies with how to switch the mod on.
- `server-health`: a new `--now-playing` option that requests only `/status/sessions` and prints
  only the live streams part.
- `website`: the Mods section shows the Now Playing mod, off by default.

## Impact

- New: `plugins/cinemetric/hooks/now-playing.tsx`, `now-playing-rules.ts`, and a test file in
  `plugins/cinemetric/tests/`.
- Changed: `hooks/register.ts`, `hooks/mods.ts`, `.claude-plugin/plugin.json` (new `userConfig`
  switch, description, version), `marketplace.json`, every script's `VERSION`,
  `skills/server-health/scripts/server_health.py` and its tests, `README.md`, `SECURITY.md`,
  `website/index.html`.
- No new dependencies. The mod starts the existing Python script; the script stays standard-library
  only and read-only.
