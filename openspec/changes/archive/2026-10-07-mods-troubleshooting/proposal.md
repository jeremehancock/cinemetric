## Why

A user on a current Claude Code (2.1.284, in the desktop app's Code tab) found `/cinemetric-mods`
"not installed". The mods hadn't loaded at all, so the read-only guard was off too. The cause wasn't
the version: Claude Code is still rolling out the feature mods are built on, and a session can start
with it switched off. Claude Code's debug log names the fix, setting
`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, and adding it to the `env` section of `~/.claude/settings.json`
brought the mods back in every session.

Cinemetric's startup notice blamed the version and told the user to run `claude update`, which
couldn't help. Nothing in the README or on the website covered this case.

In the same app, `/cinemetric-now` replied "Now Playing is open" but no panel appeared, because that
version of the app can't draw plugin panels. The mod still checked Plex every 30 seconds for a panel
nobody could see.

`/cinemetric-mods status on` there replied "Couldn't switch status on from here. Use /config
instead." and hid Claude Code's reason, so there was no way to tell why.

The library status line, switched on in the shared settings, didn't show in the desktop app either,
though it showed in a terminal: that version of the app doesn't draw the row above the prompt.

Cinemetric also works best in Claude Code in a terminal, and nothing said so.

## What Changes

- The startup notice (`hooks/mods_notice.py`) says the mods aren't running and gives both fixes:
  `claude update` for an older Claude Code, and the `env` setting for a current one. Claude's line of
  context says the same.
- The README's "Claude Code version" paragraph becomes "Mods not running?", with both fixes. The
  README says, near the top and in a new "Where to use it" section, that Cinemetric works best in
  Claude Code in your favorite terminal.
- The website says the same in the setup section and the Mods section, more briefly, and links to the
  README for the fix.
- `/cinemetric-now` checks whether the panel was actually drawn. If not, it closes it, checks
  nothing, and says the app can't show the panel and to try a terminal.
- When `/cinemetric-mods` can't change a setting, the reply gives Claude Code's reason and says to
  type the same command in a terminal (or use `/config`).
- Version 0.25.1.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `mods`: "A command for switching mods" covers a session that can't change settings; "Works on Claude Code versions without mods" asks the README to explain both fixes and
  recommend the terminal; "Telling the user when mods can't run" changes what the notice says.
- `website`: "Shows how to set up" and "Shows the mods" say Cinemetric works best in a terminal and
  point to the README when mods don't show up.
- `now-playing-pane`: "The command is always there" covers an app that can't draw the panel.

## Impact

- `plugins/cinemetric/hooks/command.ts` and its tests.
- `plugins/cinemetric/hooks/now-playing.tsx`, `now-playing-rules.ts` and their tests.
- `plugins/cinemetric/hooks/mods_notice.py`, `tests/test_mods_notice.py`, `README.md`,
  `website/index.html`, version numbers. No other change to the mods.
