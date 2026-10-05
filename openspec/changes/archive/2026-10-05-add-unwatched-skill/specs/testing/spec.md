## MODIFIED Requirements

### Requirement: Tests check the specs
Tests SHALL check behavior that the specs in `openspec/specs/` require, and SHALL NOT check details
the specs leave open. At least the following SHALL be covered:
- `library-report`: duplicates within and across libraries, media breakdown (resolution buckets,
  10-bit), housekeeping, and report totals.
- `security`: address checks, path and command allowlists, refusing redirects, hiding credentials in
  error messages, and cleaning server text, for every script that has these.
- `server-health`: the "things worth a look" flags and partial results when one part fails.
- `watch-activity`: choosing a source and the report built from each source.
- `dashboard`: HTML escaping of every value from a report, and handling a report source that failed.
- `setup`: Tautulli address cleaning and private file permissions.
- `users-and-shares`: the plex.tv address rules, the owner-only error, dropping emails and access
  tokens, the people and libraries in the report, and the "things worth a look" flags.
- `unwatched`: choosing a source, which plays count (finished only, every account), which titles are
  listed (cutoff, show added dates), sizes, and the report totals.

#### Scenario: A shared helper is fixed in one script only
- **WHEN** a fix to `validate_url` or `clean` is applied to one script but not the others
- **THEN** a test for one of the other scripts fails, because the same checks run against every
  script's copy

#### Scenario: A change breaks duplicate detection
- **WHEN** a change to `library_report.py` stops two copies of the same movie from being reported as
  duplicates
- **THEN** a test fails

#### Scenario: A change leaks a friend's email
- **WHEN** a change to `users_and_shares.py` lets an email address from a plex.tv fixture into the
  output
- **THEN** a test fails

#### Scenario: A partly watched title counts as played
- **WHEN** a change to `unwatched.py` treats a Tautulli play with `watched_status` 0.5 as finished
- **THEN** a test fails
