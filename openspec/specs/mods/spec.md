# mods Specification

## Purpose
How Cinemetric's mods ship and are switched: small Claude Code add-ons that live in the `cinemetric`
plugin beside the skills, each with its own on/off switch, a `/cinemetric-mods` command to see and
change them, and the rules that keep the skills working on Claude Code versions without mods.
## Requirements
### Requirement: Mods ship inside the cinemetric plugin
Mods SHALL live in `plugins/cinemetric/hooks/`, next to `skills/`, as one hooks module named under
`modules` in `hooks/hooks.json`. Each mod SHALL be in its own file, which the module's starting file
(`register.ts`) imports and turns on. Installing `cinemetric` SHALL install every skill and every mod.
There SHALL be no separate plugin or install command for mods.

#### Scenario: Installing Cinemetric
- **WHEN** a user runs the two install commands from the README
- **THEN** they get every skill and every mod, with each mod on or off according to its default

### Requirement: An on/off switch for each mod
Each mod SHALL have its own on/off setting, declared in `plugin.json` under `userConfig`, so it shows
up as a switch in Claude Code's config menu (opened with `/config`). A mod that is switched off SHALL add no hooks and do
nothing. Changing a switch SHALL take effect without restarting Claude Code. The read-only guard's
switch SHALL default to on. Every other mod's switch SHALL default to off.

#### Scenario: Default settings
- **WHEN** a user installs Cinemetric and changes no settings
- **THEN** the read-only guard is on and every other mod is off

#### Scenario: Turning a mod off
- **WHEN** a user switches the read-only guard off in the config menu
- **THEN** from then on no command is checked by the guard, with no restart needed

#### Scenario: Turning a mod on
- **WHEN** a user switches on a mod that was off
- **THEN** it starts working in that session, with no restart needed

### Requirement: Mods never get in the way of the skills
Every skill SHALL work the same whether mods are on, off, or not supported by the user's version of
Claude Code. A mod SHALL NOT change what a skill's script does or what it prints.

#### Scenario: An older Claude Code
- **WHEN** a user's Claude Code is 2.1.75 or newer but older than 2.1.260
- **THEN** the skills still install and work, and the mods simply don't run

#### Scenario: All mods off
- **WHEN** every mod is switched off
- **THEN** Cinemetric behaves exactly as it did before mods existed

### Requirement: A command for switching mods
The plugin SHALL add a `/cinemetric-mods` slash command that the user types themselves:
- `/cinemetric-mods` on its own SHALL list every mod with a one-line description and whether it is on
  or off;
- `/cinemetric-mods <mod> on` and `/cinemetric-mods <mod> off` SHALL switch that mod, using the same
  setting as the config menu, and confirm the new state;
- an unknown mod name or word SHALL get a short message listing the mod names and the right form.

The command SHALL be available even when every mod is switched off, so a user can always turn one
back on. Mod names SHALL be short words (the guard's is `guard`).

#### Scenario: Listing the mods
- **WHEN** the user types `/cinemetric-mods`
- **THEN** they see each mod, what it does, and whether it is on or off

#### Scenario: Switching the guard off
- **WHEN** the user types `/cinemetric-mods guard off`
- **THEN** the guard switches off right away, the config menu shows it off, and the command confirms it

#### Scenario: A typo
- **WHEN** the user types `/cinemetric-mods gaurd off`
- **THEN** nothing changes and they see the list of mod names and how to use the command

#### Scenario: Everything off
- **WHEN** every mod is off and the user types `/cinemetric-mods guard on`
- **THEN** the guard switches back on

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

### Requirement: Works on Claude Code versions without mods
Cinemetric SHALL load, and every skill SHALL work, on Claude Code 2.1.75 or newer. Mods SHALL need
Claude Code 2.1.260 or newer. `hooks/hooks.json` SHALL carry both a `hooks` section in the older
settings-hook format and the `modules` line, so versions that don't know about mods still accept the
file. The README SHALL state both version numbers.

#### Scenario: Plugin checker on an older version
- **WHEN** `claude plugin validate plugins/cinemetric` runs on Claude Code 2.1.75, 2.1.200 or 2.1.260
- **THEN** validation passes

### Requirement: Telling the user when mods can't run
When a session starts on a Claude Code that can't run mods, Cinemetric SHALL show the user a short
notice saying that mods (such as the read-only guard) need Claude Code 2.1.260 or newer, that every
skill still works, and that `claude update` gets the mods. The notice SHALL come from a settings
hook (`SessionStart`) running `hooks/mods_notice.py`, a Python 3.8+ standard-library script.

The mods SHALL tell the script they are running: on newer versions the hooks module sets the
environment variable `CINEMETRIC_MODS_ACTIVE` just before the `SessionStart` settings hooks run. When
that variable is set, the script SHALL show nothing.

The notice SHALL be shown only when a session starts fresh (not on resume, `/clear` or compaction),
and at most once a day. The script SHALL remember the day it last showed the notice in
`mods-notice.json` in Cinemetric's data folder (the same folder the dashboard and snapshots use). It
SHALL also give Claude one line of context saying the mods aren't running and why, so Claude can
answer questions about them. Any problem in the script (an unreadable file, odd input) SHALL end it
quietly without a notice and without an error.

#### Scenario: Current Claude Code
- **WHEN** a session starts on Claude Code 2.1.260 or newer
- **THEN** no notice is shown

#### Scenario: Older Claude Code, first session of the day
- **WHEN** a session starts fresh on Claude Code 2.1.200 and no notice was shown today
- **THEN** the user sees the notice once, and the day is saved

#### Scenario: Older Claude Code, later the same day
- **WHEN** another session starts on the same day
- **THEN** no notice is shown

#### Scenario: Resuming a session
- **WHEN** a session is resumed, cleared or compacted on an older Claude Code
- **THEN** no notice is shown

