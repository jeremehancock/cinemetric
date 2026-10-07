## MODIFIED Requirements

### Requirement: Claude can't switch the guard off
Only the user SHALL be able to switch the read-only guard off: through the config menu or by typing
`/cinemetric-mods guard off`. Any way the plugin later gives Claude to switch mods SHALL be able to
turn any mod on, and any mod off except the guard. When asked to switch the guard off, it SHALL tell
Claude to ask the user to do it themselves and say how.

While the guard is on, it SHALL also stop Claude from switching it off by editing Claude Code's
settings files. A call SHALL be refused only when both of these are true:
- it targets a Claude Code settings file: a file named `settings.json` or `settings.local.json`
  inside a `.claude` folder (the user's `~/.claude/` or any project's `.claude/`). For `Write` and
  `Edit` this is the file being written; for `Bash` the command text names such a file;
- its text mentions the guard's setting, `read_only_guard`.

Every other call SHALL pass this check untouched, including edits to any project's code (Cinemetric's
own source among them) and edits to Claude Code settings that don't mention the guard.

Anything a user reads (README, SECURITY.md, the website, the setting's description in `/config`)
SHALL describe this as the guard being meant to be switched off only by the user, with Claude's usual
ways of switching it off refused. It SHALL NOT promise that Claude can never switch the guard off,
since the settings-file check only looks for the setting's name and can't see inside a program
Claude writes to change the file.

#### Scenario: Claude asked to turn the guard off
- **WHEN** a later mods tool is asked to switch the guard off
- **THEN** the guard stays on and Claude is told the user must use the config menu or type
  `/cinemetric-mods guard off`

#### Scenario: Editing settings directly
- **WHEN** the guard is on and Claude tries to edit `~/.claude/settings.json` to set
  `read_only_guard` to false
- **THEN** the edit is refused with a message saying only the user can switch the guard off, and how

#### Scenario: Changing settings from the shell
- **WHEN** the guard is on and Claude runs a command that writes `read_only_guard` into
  `.claude/settings.local.json`
- **THEN** the command is refused the same way

#### Scenario: Another project uses the same name
- **WHEN** the guard is on and Claude edits `src/config.py` in an unrelated project, and the file
  contains `read_only_guard`
- **THEN** the edit goes ahead, because the file isn't a Claude Code settings file

#### Scenario: Working on Cinemetric itself
- **WHEN** the guard is on and Claude edits `plugins/cinemetric/hooks/guard.ts`
- **THEN** the edit goes ahead

#### Scenario: Other settings changes
- **WHEN** the guard is on and Claude edits `.claude/settings.json` to add a permission that has
  nothing to do with the guard
- **THEN** the edit goes ahead

#### Scenario: Reading about switching the guard off
- **WHEN** a user reads the README, SECURITY.md, the website or the guard's description in `/config`
- **THEN** they learn the guard is meant to be switched off only by them and that Claude's usual ways
  are refused, and nothing tells them Claude can never switch it off
