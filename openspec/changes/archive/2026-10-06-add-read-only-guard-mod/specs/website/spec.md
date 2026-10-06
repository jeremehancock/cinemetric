## ADDED Requirements

### Requirement: Shows the mods
The site SHALL have a Mods section placed right after the dashboard section and before the privacy
section. It SHALL say plainly that mods come with Cinemetric (no extra install) and that they work
only in Claude Code (the terminal and the desktop app's Code tab). For each mod it SHALL say what the
mod does in plain words, its short name (for example `guard` or `status`), and whether it starts on
or off. The
"Shows every skill" count and headings SHALL stay about skills only.

#### Scenario: A visitor reaches the mods
- **WHEN** a visitor scrolls past the dashboard section
- **THEN** they see the Mods section, the read-only guard described in it as on by default, the
  library status line described as off by default, and a note that mods work only in Claude Code

#### Scenario: Wondering how to get them
- **WHEN** a visitor reads the Mods section
- **THEN** they learn the mods come with the normal install, with nothing extra to run

#### Scenario: Without JavaScript
- **WHEN** a visitor opens the page with JavaScript turned off
- **THEN** the Mods section, including how to switch mods, is still visible and readable

### Requirement: The setup guide points to the mods
The setup guide SHALL keep its four steps and SHALL mention the mods in a collapsible "Mods
(optional)" extra beside the other optional extras, not as a step. It SHALL say the mods come with
Cinemetric, that the read-only guard is already on and other mods start off, give `/cinemetric-mods`
with a copy button, state that mods need Claude Code 2.1.260 or newer, and link to the Mods section.

#### Scenario: Reading the setup guide
- **WHEN** a visitor opens "Mods (optional)" under the setup steps
- **THEN** they see that nothing more needs installing, the `/cinemetric-mods` command, and a link to
  the Mods section, and the guide still says it takes four steps

### Requirement: Explains how to switch mods on and off
The Mods section SHALL explain both ways to switch a mod:
- typing `/cinemetric-mods` to see every mod and whether it's on, and
  `/cinemetric-mods <name> on` or `off` to switch one, shown with the status line as the example
  (`/cinemetric-mods status on`);
- the config menu, opened with `/config`, where each mod has a switch.

Each command shown SHALL have a copy button, using the same copy behavior as the setup guide. The
section SHALL say that only the user can switch the guard off, and why in one sentence (so Claude
can't turn off its own safety net). It SHALL NOT describe a way to ask Claude to switch mods until
the plugin has one.

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

### Requirement: The privacy section mentions the guard
The "Look, don't touch" section's intro SHALL mention that the read-only guard, on by default, can also stop
Claude from running its own commands that would change the server. The cards SHALL stay as they were,
so they keep similar lengths. The wording SHALL call it an extra
safety net and SHALL NOT claim it catches everything.

#### Scenario: Reading the privacy section
- **WHEN** a visitor reads "Look, don't touch"
- **THEN** they see a short mention of the guard that links to the Mods section
