## MODIFIED Requirements

### Requirement: Private files
Cinemetric's config folder SHALL be created readable only by the user (`700`), and every file holding settings or
report data (config, in-progress sign-in, Tautulli form status, dashboard page and dashboard state)
SHALL be created readable only by the user (`600`) from the start, with no
moment where looser permissions apply. On Linux and macOS, a config file owned by another user or
accessible to other users SHALL be refused, with the `chmod 600` command that fixes it. The
in-progress sign-in file SHALL be deleted once a server is selected or setup is cancelled.

#### Scenario: Config readable by others
- **WHEN** a script finds `config.json` with group or other permissions
- **THEN** it refuses to read it and prints `chmod 600 <path>` as the fix

## ADDED Requirements

### Requirement: Dashboard goes online only by choice
The dashboard SHALL be published to claude.ai only when the user has chosen `online` or `both`, and
only as a private page (visible to the user alone until they choose to share it). Cinemetric's
scripts SHALL never publish anything themselves; they only save the user's choice and the page's
link. The published page is the same file as the local one, so it keeps the same rules: no scripts,
no outside requests, every server value HTML-escaped, and names left out when the user chose to
hide them.

#### Scenario: Local only
- **WHEN** the saved destination is `local`
- **THEN** the dashboard is not published, and no saved online page is updated

#### Scenario: Names hidden
- **WHEN** names are hidden and the destination is `both`
- **THEN** neither the local file nor the online page contains user names
