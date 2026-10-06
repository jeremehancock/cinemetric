## MODIFIED Requirements

### Requirement: Tests check the specs
Tests SHALL check behavior that the specs in `openspec/specs/` require, and SHALL NOT check details
the specs leave open. At least the following SHALL be covered:
- `library-report`: duplicates within and across libraries, media breakdown (resolution buckets,
  10-bit), housekeeping, report totals, the snapshot area, and `since_snapshot` (titles, episodes,
  unavailable files, new, removed and renamed libraries).
- `security`: address checks, path and command allowlists, refusing redirects, hiding credentials in
  error messages, and cleaning server text, for every script that has these; and skipping bad
  snapshot files and cleaning snapshot text, for every script that reads snapshots.
- `server-health`: the "things worth a look" flags, partial results when one part fails, the
  snapshot area and `since_snapshot`.
- `watch-activity`: choosing a source and the report built from each source.
- `dashboard`: HTML escaping of every value from a report, handling a report source that failed,
  saving a snapshot through the changes script, and the changes section (including names hidden).
- `setup`: Tautulli address cleaning and private file permissions.
- `users-and-shares`: the plex.tv address rules, the owner-only error, dropping emails and access
  tokens, the people and libraries in the report, the "things worth a look" flags, the snapshot area
  (only the allowed details) and `since_snapshot`.
- `unwatched`: choosing a source, which plays count (finished only, every account), which titles are
  listed (cutoff, show added dates), sizes, and the report totals.
- `what-to-watch`: watched status for movies and shows, each filter, merging the same title across
  libraries, sorting and the limit, and continue watching.
- `changes`: choosing which snapshot to compare with (earlier day, `--since`, missing area, other
  server), saving and merging the same day, pruning after 90 days, `save` without network, `list`,
  `forget`, file permissions, and a report that fails.

#### Scenario: A shared helper is fixed in one script only
- **WHEN** a fix to `validate_url`, `clean` or the snapshot reading helper is applied to one script
  but not the others
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

#### Scenario: A started show counts as unwatched
- **WHEN** a change to `what_to_watch.py` lets a show with some episodes watched match `--unwatched`
- **THEN** a test fails

#### Scenario: A snapshot copies more about people than allowed
- **WHEN** a change to `users_and_shares.py` puts a last played date or email into the sharing
  snapshot area
- **THEN** a test fails
