## MODIFIED Requirements

### Requirement: An on/off switch for each mod
Each mod SHALL have its own on/off setting, declared in `plugin.json` under `userConfig`, so it shows
up as a switch in Claude Code's config menu (opened with `/config`). A mod that is switched off SHALL
do nothing and add no hooks, with one exception: a mod that has its own slash command MAY keep that
command listed while off, as long as typing it only replies with how to switch the mod on, and starts
no program, contacts nothing and changes nothing. Changing a switch SHALL take effect without
restarting Claude Code. The read-only guard's switch SHALL default to on. Every other mod's switch
SHALL default to off.

#### Scenario: Default settings
- **WHEN** a user installs Cinemetric and changes no settings
- **THEN** the read-only guard is on and every other mod is off

#### Scenario: Turning a mod off
- **WHEN** a user switches the read-only guard off in the config menu
- **THEN** from then on no command is checked by the guard, with no restart needed

#### Scenario: Turning a mod on
- **WHEN** a user switches on a mod that was off
- **THEN** it starts working in that session, with no restart needed

#### Scenario: A mod's own command while it's off
- **WHEN** Now Playing is off and the user types `/cinemetric-now`
- **THEN** they are told how to switch it on, and nothing else happens
