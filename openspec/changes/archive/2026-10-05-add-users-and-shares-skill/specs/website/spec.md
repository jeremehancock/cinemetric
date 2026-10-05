## MODIFIED Requirements

### Requirement: Shows every skill
The site SHALL describe each of the plugin's skills: `setup`, `library-report`, `server-health`,
`watch-activity`, `users-and-shares` and `dashboard`. For each one it SHALL say what the skill reports
or does and give at least one example of what to ask Claude. Each skill SHALL have a demo panel
showing what the user really gets, and nothing else: for `setup`, `library-report`, `server-health`,
`watch-activity` and `users-and-shares`, a Claude Code terminal conversation that follows that skill's
`SKILL.md` presentation order; for `dashboard`, only a screenshot of the real dashboard page built by
the dashboard script, with no terminal conversation and no tabs. The site SHALL NOT show designed
graphics as if they were a skill's output. Demo data (names, titles, numbers) SHALL be made up, never
real server data.

#### Scenario: A visitor reads the features
- **WHEN** a visitor scrolls through the features section
- **THEN** they see all six skills, each with a description, an example request and a demo panel in
  the skill's real output format

#### Scenario: Dashboard demo
- **WHEN** a visitor reaches the dashboard section, with or without JavaScript
- **THEN** the demo panel shows the dashboard screenshot and its caption, and there is no tab bar or
  terminal conversation
