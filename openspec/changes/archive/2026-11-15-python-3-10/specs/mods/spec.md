## MODIFIED Requirements

### Requirement: Telling the user when mods can't run
When a session starts and the mods aren't running, Cinemetric SHALL show the user a short notice
saying that the mods (such as the read-only guard) aren't running in this session; that they need
Claude Code 2.1.260 or newer and `claude update` gets it; that on a version already that new, adding
`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` set to `"1"` to the `env` section of `~/.claude/settings.json` and
starting a new session switches them on; and that every skill still works. The notice SHALL come
from a settings hook (`SessionStart`) running `hooks/mods_notice.py`, a Python 3.10+ standard-library
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
