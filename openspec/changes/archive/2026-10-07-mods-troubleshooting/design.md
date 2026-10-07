## Context

The notice script can't tell why the mods didn't load. It only knows `CINEMETRIC_MODS_ACTIVE` wasn't
set, which happens on an older Claude Code and on a current one where the rollout switch is off.

## Goals / Non-Goals

**Goals:** a notice that is right in both cases; a README answer for "mods not showing up"; telling
people the terminal is the best place to use Cinemetric.

**Non-Goals:** changing any setting for the user.

## Decisions

- **Give both fixes in the notice, version first.** The script has no reliable way to read the Claude
  Code version, so it names both: update if older than 2.1.260, otherwise the `env` setting.
- **Point users at the `env` setting, not a command-line flag.** The desktop app starts Claude Code
  itself, so a flag or shell variable wouldn't reach it. `~/.claude/settings.json` is read by every
  session, wherever it starts. Tested with the desktop app's own copy of Claude Code.
- **"Works best in a terminal", not "doesn't work in the desktop app".** Skills and mods both work in
  the Code tab too.
