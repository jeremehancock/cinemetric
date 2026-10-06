## MODIFIED Requirements

### Requirement: Skill shape
Each skill SHALL live in `plugins/cinemetric/skills/<name>/` as a `SKILL.md` plus one script in
`scripts/`. The script collects the facts and prints them; Claude turns them into the written report
by following `SKILL.md`. The `dashboard` and `year-in-review` skills are the exceptions: their pages
are written by rules in the script, not by Claude.

#### Scenario: Adding a new skill
- **WHEN** a new skill is added
- **THEN** it has a `SKILL.md` and a single script under `scripts/`, and the script prints JSON that
  `SKILL.md` tells Claude how to present

#### Scenario: A recap page
- **WHEN** the year-in-review script runs
- **THEN** it writes the recap page itself by fixed rules and also prints JSON that `SKILL.md` tells
  Claude how to summarize

### Requirement: Connection check
The `library-report`, `server-health`, `watch-activity`, `users-and-shares`, `unwatched`,
`what-to-watch`, `episode-gaps`, `playback-check` and `year-in-review` scripts SHALL accept `--check`,
which only tests the configured connections and prints a short JSON result instead of building a
report.

#### Scenario: Testing the connection
- **WHEN** a report script is run with `--check`
- **THEN** it contacts the server once to confirm the address and token work, and prints the server
  name and version
