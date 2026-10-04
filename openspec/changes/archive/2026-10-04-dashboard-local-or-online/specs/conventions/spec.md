## MODIFIED Requirements

### Requirement: Output and errors
Scripts SHALL print one JSON document to stdout on success and exit 0. Progress lines and warnings
SHALL go to stderr. On failure a script SHALL print one line starting with `error: ` to stderr and
exit 1; when interrupted with Ctrl-C it SHALL exit 130. Error messages SHALL be safe to show the user.
Errors that a skill needs to recognize SHALL start with a fixed code: `NOT_CONFIGURED`,
`TAUTULLI_NOT_CONFIGURED` or `OWNER_ONLY`.

#### Scenario: Not connected yet
- **WHEN** a report script runs and no Plex address and token are configured
- **THEN** it prints `error: NOT_CONFIGURED: ...` to stderr and exits 1

#### Scenario: Successful run
- **WHEN** a report script finishes normally
- **THEN** stdout contains only the JSON report, and any progress messages went to stderr
