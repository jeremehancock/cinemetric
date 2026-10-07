## MODIFIED Requirements

### Requirement: A command for switching mods
The plugin SHALL add a `/cinemetric-mods` slash command that the user types themselves:
- `/cinemetric-mods` on its own SHALL list every mod with a one-line description and whether it is on
  or off;
- `/cinemetric-mods <mod> on` and `/cinemetric-mods <mod> off` SHALL switch that mod, using the same
  setting as the config menu, and confirm the new state;
- an unknown mod name or word SHALL get a short message listing the mod names and the right form;
- when Claude Code can't change the setting from this session (as in some sessions the desktop app
  starts), the reply SHALL say the switch didn't happen, give Claude Code's reason, and say to type the
  same command in Claude Code in a terminal or use `/config`.

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

#### Scenario: A session that can't change settings
- **WHEN** the user types `/cinemetric-mods status on` in a session where Claude Code can't change the
  setting
- **THEN** nothing changes, and the reply gives the reason and says to switch it in a terminal

### Requirement: Works on Claude Code versions without mods
Cinemetric SHALL load, and every skill SHALL work, on Claude Code 2.1.75 or newer. Mods SHALL need
Claude Code 2.1.260 or newer. `hooks/hooks.json` SHALL carry both a `hooks` section in the older
settings-hook format and the `modules` line, so versions that don't know about mods still accept the
file. The README SHALL state both version numbers.

The README SHALL also say what to do when the mods aren't running: run `claude update` on a Claude
Code older than 2.1.260, and on a newer one add `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` set to `"1"` to the
`env` section of `~/.claude/settings.json` and start a new session, since Claude Code may start a
session with the feature mods use switched off. It SHALL say that Cinemetric works best in Claude
Code in a terminal, and that some versions of the desktop app can't show the library status line or
the Now Playing panel, or switch mods with `/cinemetric-mods`.

#### Scenario: Plugin checker on an older version
- **WHEN** `claude plugin validate plugins/cinemetric` runs on Claude Code 2.1.75, 2.1.200 or 2.1.260
- **THEN** validation passes

#### Scenario: Mods missing on a current Claude Code
- **WHEN** a user on Claude Code 2.1.260 or newer finds `/cinemetric-mods` isn't installed
- **THEN** the README tells them which setting to add and to start a new session

### Requirement: Telling the user when mods can't run
When a session starts and the mods aren't running, Cinemetric SHALL show the user a short notice
saying that the mods (such as the read-only guard) aren't running in this session; that they need
Claude Code 2.1.260 or newer and `claude update` gets it; that on a version already that new, adding
`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` set to `"1"` to the `env` section of `~/.claude/settings.json` and
starting a new session switches them on; and that every skill still works. The notice SHALL come
from a settings hook (`SessionStart`) running `hooks/mods_notice.py`, a Python 3.8+ standard-library
script.

The mods SHALL tell the script they are running: on newer versions the hooks module sets the
environment variable `CINEMETRIC_MODS_ACTIVE` just before the `SessionStart` settings hooks run. When
that variable is set, the script SHALL show nothing.

The notice SHALL be shown only when a session starts fresh (not on resume, `/clear` or compaction),
and at most once a day. The script SHALL remember the day it last showed the notice in
`mods-notice.json` in Cinemetric's data folder (the same folder the dashboard and snapshots use). It
SHALL also give Claude one line of context saying the mods aren't running and both likely reasons,
so Claude can answer questions about them. Any problem in the script (an unreadable file, odd input)
SHALL end it quietly without a notice and without an error.

#### Scenario: Current Claude Code
- **WHEN** a session starts on Claude Code 2.1.260 or newer and the mods load
- **THEN** no notice is shown

#### Scenario: Older Claude Code, first session of the day
- **WHEN** a session starts fresh on Claude Code 2.1.200 and no notice was shown today
- **THEN** the user sees the notice once, naming both fixes, and the day is saved

#### Scenario: Current Claude Code with the mods switched off
- **WHEN** a session starts fresh on Claude Code 2.1.260 or newer, the session started with the
  feature mods use switched off, and no notice was shown today
- **THEN** the user sees the same notice, which tells them which setting to add

#### Scenario: Older Claude Code, later the same day
- **WHEN** another session starts on the same day
- **THEN** no notice is shown

#### Scenario: Resuming a session
- **WHEN** a session is resumed, cleared or compacted on an older Claude Code
- **THEN** no notice is shown
