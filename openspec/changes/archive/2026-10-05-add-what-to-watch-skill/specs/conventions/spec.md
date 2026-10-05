## MODIFIED Requirements

### Requirement: Connection check
The `library-report`, `server-health`, `watch-activity`, `users-and-shares`, `unwatched` and
`what-to-watch` scripts SHALL accept `--check`, which only tests the configured connections and prints
a short JSON result instead of building a report.

#### Scenario: Testing the connection
- **WHEN** a report script is run with `--check`
- **THEN** it contacts the server once to confirm the address and token work, and prints the server
  name and version
