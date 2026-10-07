## MODIFIED Requirements

### Requirement: The command is always there
The plugin SHALL add a `/cinemetric-now` slash command whether the mod is on or off, described as
`Show who's streaming from Plex right now, updated while it's open`.

When the mod is off, the command SHALL open no panel, start no program, contact nothing and reply
exactly: `Now Playing is off. Type /cinemetric-mods now on to switch it on.`

When the mod is on, the command SHALL open the Now Playing panel (or leave it open if it already is)
and reply `Now Playing is open. It checks Plex about every 30 seconds while it's open.` The reply
SHALL NOT contain anything about the streams themselves.

If the app can't draw the panel (Claude Code reports it isn't placed, as in some versions of the
desktop app), the command SHALL close it again, start no checks, and reply: `This app can't show Now
Playing's panel, so it isn't open and Plex isn't being checked. Try /cinemetric-now in Claude Code in
a terminal.`

#### Scenario: Typed while off
- **WHEN** the mod is off and the user types `/cinemetric-now`
- **THEN** no panel opens, the server isn't contacted, and the reply tells them how to switch it on

#### Scenario: Typed while on
- **WHEN** the mod is on and the user types `/cinemetric-now`
- **THEN** the Now Playing panel opens and the reply says it checks about every 30 seconds while open

#### Scenario: Typed again while open
- **WHEN** the panel is already open and the user types `/cinemetric-now` again
- **THEN** there is still one panel, and no extra check starts beyond the regular ones

#### Scenario: An app that can't draw panels
- **WHEN** the mod is on and the user types `/cinemetric-now` in an app that can't draw the panel
- **THEN** no panel stays open, the server isn't contacted, and the reply says to try a terminal
