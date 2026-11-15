## MODIFIED Requirements

### Requirement: Shows how to set up
The site SHALL include a setup guide covering: requirements (Claude Code, Python 3.10+, network access to
the Plex server), the two install commands, connecting with Sign in with Plex, optionally adding
Tautulli, the manual-setup fallback, and how to revoke access. It SHALL say that Cinemetric works
best in Claude Code in a terminal. Each command SHALL have a button that copies it. The guide SHALL link to the README for full details.

#### Scenario: Copying an install command
- **WHEN** a visitor clicks the copy button next to `/plugin marketplace add jeremehancock/cinemetric`
- **THEN** that exact command is placed on their clipboard and the button briefly confirms it was copied

#### Scenario: Wanting more detail
- **WHEN** a visitor needs more than the short setup steps
- **THEN** the setup section links to the README on GitHub

#### Scenario: Choosing where to run it
- **WHEN** a visitor reads the setup section
- **THEN** they learn that Cinemetric works best in Claude Code in a terminal
