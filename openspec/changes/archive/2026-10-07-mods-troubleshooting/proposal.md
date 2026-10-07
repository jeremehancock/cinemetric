## Why

A user on a current Claude Code (2.1.284, in the desktop app's Code tab) found `/cinemetric-mods`
"not installed". The mods hadn't loaded at all, so the read-only guard was off too. The cause wasn't
the version: Claude Code is still rolling out the feature mods are built on, and a session can start
with it switched off. Claude Code's debug log names the fix, setting
`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, and adding it to the `env` section of `~/.claude/settings.json`
brought the mods back in every session.

Cinemetric's startup notice blamed the version and told the user to run `claude update`, which
couldn't help. Nothing in the README or on the website covered this case.

With the mods running, the desktop app's Code tab still left `/cinemetric-mods` out of its slash
menu and showed "/cinemetric-mods isn't a command here" when it was typed, though the command ran.
That's the desktop app's doing, not something Cinemetric can change, so users should hear about it
and know that Cinemetric works best in Claude Code in a terminal.

## What Changes

- The startup notice (`hooks/mods_notice.py`) says the mods aren't running and gives both fixes:
  `claude update` for an older Claude Code, and the `env` setting for a current one. Claude's line of
  context says the same.
- The README's "Claude Code version" paragraph becomes "Mods not running?", with both fixes and a
  note on the desktop app's Code tab (type mod commands in full; the slash menu leaves them out and
  the app may say the command isn't one, but it still runs). The README says, near the top and in
  Install, that Cinemetric works best in Claude Code in your favorite terminal.
- The website says the same in the setup section and the Mods section, more briefly, and links to the
  README for the fix.
- Version 0.25.1.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `mods`: "Works on Claude Code versions without mods" asks the README to explain both fixes and the
  desktop app's slash menu; "Telling the user when mods can't run" changes what the notice says.
- `website`: "Shows how to set up" and "Shows the mods" say Cinemetric works best in a terminal and
  point to the README when mods don't show up.

## Impact

- `plugins/cinemetric/hooks/mods_notice.py`, `tests/test_mods_notice.py`, `README.md`,
  `website/index.html`, version numbers. No change to the mods themselves.
