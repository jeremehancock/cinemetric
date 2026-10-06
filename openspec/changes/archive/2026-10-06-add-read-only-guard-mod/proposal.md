## Why

Cinemetric promises it never changes anything on a Plex server, and its scripts keep that promise in
code: each one only sends `GET` requests to an allowlist of paths. But Claude can also reach the server
without going through a Cinemetric script, for example by writing its own `curl` command while
troubleshooting. Nothing stops one of those commands from sending a write request (such as a `DELETE`)
today. Claude Code now supports mods (plugins made of small hooks that run inside Claude Code), and a
mod can look at each command before it runs and block the ones that would write to Plex or Tautulli.
This is also the first mod, so it sets up how mods ship in general: inside the existing `cinemetric`
plugin, so one install gets every skill and every mod.

## What Changes

- Mods ship inside the existing `cinemetric` plugin, in a new `plugins/cinemetric/hooks/` folder next
  to `skills/`. Installing `cinemetric` gets every skill and every mod; there is no second plugin or
  second install command.
- Each mod has an on/off switch, a plugin setting (`userConfig`) that shows up in Claude Code's config
  menu. The read-only guard is **on** by default. Mods added later are **off** by default.
- A second, small mod ships with it, the **library status line** (`status`), off by default: one
  dim line just above Claude Code's prompt, such as `Plex: 1,970 movies · 417 shows · 59.4 TB · checked
  3 days ago`, read from the newest snapshot on the user's computer. It never contacts the server.
  Being off by default, it is the website's example for switching a mod on.
- A `/cinemetric-mods` command the user types to see which mods are on and switch them
  (`/cinemetric-mods status on`). Only the user can switch the guard off, so Claude can't turn off
  its own safety net. A tool for asking Claude to switch mods is left for a later change.
- The first mod is the **read-only guard**: before Claude runs a shell command or fetches a web
  address, it checks whether the command is aimed at the user's Plex server, Tautulli or plex.tv and
  would write something. If so, the command is blocked and Claude is told why.
- The guard reads the server and Tautulli addresses from Cinemetric's existing settings file. It
  never shows, logs or sends the token or API key, and it makes no network requests of its own.
- The website gets a new "Mods" section after the dashboard section, labeled as extras for Claude
  Code, saying mods come with Cinemetric and how to switch them on or off. The "Look, don't touch"
  section gets a short mention of the guard.
- The README gets a short "Mods" section on the same lines.
- Version bump for `cinemetric` (scripts, `plugin.json`, `marketplace.json`), since the plugin now
  does something new.

## Capabilities

### New Capabilities
- `mods`: how mods ship inside the plugin, their on/off switches and defaults, and the rule that
  mods never get in the way of the skills.
- `library-status-line`: what the status line shows, which snapshot it reads, when it updates, and
  its safety rules.
- `read-only-guard`: what the guard checks, what it blocks and lets through, where it gets the
  server addresses, how it explains a block, and its own safety rules.

### Modified Capabilities
- `website`: adds a Mods section and a mention of the guard in the privacy section, worded so it
  doesn't overstate what the guard catches.

## Impact

- New files: `plugins/cinemetric/hooks/` (the hooks module in TypeScript, one file per mod, and
  tests run with `claude plugin test`).
- Edited: `plugins/cinemetric/.claude-plugin/plugin.json` (settings for the switches, version),
  `.claude-plugin/marketplace.json` (version, description), every script's `VERSION`,
  `website/index.html` (and `styles.css` if needed), `README.md`, `SECURITY.md`.
- No change to what any skill or script does. No new network destinations.
- Older Claude Code versions that don't know about mods must still load the skills; this needs
  checking before release (see design).
- The guard only runs in Claude Code (the terminal and the desktop app's Code tab).
- The guard's tests need the `claude` command, which the GitHub test workflow doesn't have, so
  they run locally. The Python test suite in CI is unchanged apart from any website checks.
