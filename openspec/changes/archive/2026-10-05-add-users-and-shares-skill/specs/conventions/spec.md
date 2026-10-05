## MODIFIED Requirements

### Requirement: Connection check
The `library-report`, `server-health`, `watch-activity` and `users-and-shares` scripts SHALL accept
`--check`, which only tests the configured connections and prints a short JSON result instead of
building a report.

#### Scenario: Testing the connection
- **WHEN** a report script is run with `--check`
- **THEN** it contacts the server once to confirm the address and token work, and prints the server
  name and version

### Requirement: One version number
Every script's `VERSION` constant, `plugins/cinemetric/.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json` SHALL carry the same version. A release bumps all of them together.

#### Scenario: Releasing a new version
- **WHEN** the version is bumped
- **THEN** every script under `plugins/cinemetric/skills/`, `plugin.json` and `marketplace.json`
  show the new version
