## MODIFIED Requirements

### Requirement: Explains how to switch mods on and off
The Mods section SHALL explain both ways to switch a mod:
- typing `/cinemetric-mods` to see every mod and whether it's on, and
  `/cinemetric-mods <name> on` or `off` to switch one, shown with the status line as the example
  (`/cinemetric-mods status on`);
- the config menu, opened with `/config`, where each mod has a switch.

Each command shown SHALL have a copy button, using the same copy behavior as the setup guide. The
section SHALL say that the guard is meant to be switched off only by the user and that Cinemetric
refuses Claude's usual ways of switching it off, and why in one sentence (so Claude can't casually
turn off its own safety net). It SHALL NOT promise that Claude can never switch the guard off. It
SHALL NOT describe a way to ask Claude to switch mods until the plugin has one.

#### Scenario: Turning a mod on
- **WHEN** a visitor wants to know how to turn a mod on
- **THEN** the Mods section shows `/cinemetric-mods status on` with a copy button, and mentions the
  config menu as the other way

#### Scenario: Seeing what's on
- **WHEN** a visitor wants to check which mods are on
- **THEN** the Mods section tells them to type `/cinemetric-mods`

#### Scenario: Copying a mods command
- **WHEN** a visitor clicks the copy button next to `/cinemetric-mods status on`
- **THEN** that exact command is placed on their clipboard and the button briefly confirms it was
  copied

#### Scenario: Reading who can switch the guard off
- **WHEN** a visitor reads the Mods section
- **THEN** it says the guard is meant to be switched off only by them and that Claude's usual ways
  are refused, without saying Claude can never do it
