## MODIFIED Requirements

### Requirement: Shows the mods
The site SHALL have a Mods section placed right after the dashboard section and before the privacy
section. It SHALL say plainly that mods come with Cinemetric (no extra install) and that they work
only in Claude Code (the terminal and the desktop app's Code tab). For each mod it SHALL say what the
mod does in plain words, its short name (for example `guard`, `status` or `now`), and whether it
starts on or off. The Now Playing card SHALL also say that it checks the server only while its panel
is open. The "Shows every skill" count and headings SHALL stay about skills only.

#### Scenario: A visitor reaches the mods
- **WHEN** a visitor scrolls past the dashboard section
- **THEN** they see the Mods section, the read-only guard described in it as on by default, the
  library status line and Now Playing described as off by default, and a note that mods work only in
  Claude Code

#### Scenario: Reading the Now Playing card
- **WHEN** a visitor reads the Now Playing card
- **THEN** they learn it shows who is streaming right now, that it's opened with `/cinemetric-now`,
  and that it checks the server only while it's open

#### Scenario: Wondering how to get them
- **WHEN** a visitor reads the Mods section
- **THEN** they learn the mods come with the normal install, with nothing extra to run

#### Scenario: Without JavaScript
- **WHEN** a visitor opens the page with JavaScript turned off
- **THEN** the Mods section, including how to switch mods, is still visible and readable
