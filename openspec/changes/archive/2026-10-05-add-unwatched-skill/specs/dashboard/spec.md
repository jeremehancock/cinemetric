## MODIFIED Requirements

### Requirement: Built from the other report scripts
The dashboard SHALL get its data by running `library_report.py`, `server_health.py` (with
`--stuck-wait 0`, since the dashboard doesn't show the stuck task check and shouldn't wait for it),
`watch_activity.py` (with `--days 30 --top 8 --recent 10`), `users_and_shares.py` and `unwatched.py`
(with `--limit 10`) side by side, so it has exactly their read-only behavior. It SHALL never contact
Plex, plex.tv or Tautulli itself. A report that fails or runs longer than 30 minutes SHALL leave its
section out, with the reason shown on the page and in `sections_missing`. If every report fails, the
dashboard SHALL fail with the first error.

#### Scenario: Watch activity fails
- **WHEN** the watch-activity script exits with an error
- **THEN** the page is still written, the watch section shows the reason, and `sections_missing` has
  a `watch` entry

#### Scenario: A Plex task is running while the dashboard builds
- **WHEN** the dashboard is built while Plex is scanning a library
- **THEN** `server_health.py` is run with `--stuck-wait 0` and the build doesn't wait for a second
  task check

#### Scenario: Connected to someone else's server
- **WHEN** `users_and_shares.py` fails with `OWNER_ONLY`
- **THEN** the page is still written with the other sections, the Sharing section explains that only
  the server owner can see who it's shared with (without the `OWNER_ONLY` code), and
  `sections_missing` has a `sharing` entry

#### Scenario: Unwatched report fails
- **WHEN** `unwatched.py` exits with an error
- **THEN** the page is still written with the other sections, the Unwatched section shows the reason,
  and `sections_missing` has an `unwatched` entry

## ADDED Requirements

### Requirement: Unwatched section
The page SHALL have an Unwatched section built from the `unwatched` report, showing:
- one line with the total number of titles, their size and their share of the libraries checked,
  saying they were added more than N months ago with no finished play in that time (N from the
  report's `months`);
- each library checked with its count, size and share;
- the 10 largest listed titles across all libraries, each with its library, size, added date and last
  finished date (or "never finished");
- where the plays came from (Tautulli or Plex's watch history), and a note when `history_capped` is
  true.

The section SHALL state facts only and SHALL NOT suggest deleting anything. Unwatched items SHALL NOT
be added to the server's "Needs a look" list and SHALL NOT change the page's overall status. Hiding
names SHALL NOT change this section, since it contains no person's name. When no title qualifies, the
section SHALL say so in one line.

#### Scenario: Large unwatched movies
- **WHEN** the unwatched report lists 50 movies using 600 GB and the server has no other issues
- **THEN** the Unwatched section shows the total and the 10 largest titles, and the page's overall
  status is still "Healthy"

#### Scenario: Nothing unwatched
- **WHEN** every library in the unwatched report has `unwatched` 0
- **THEN** the Unwatched section says there are no titles that qualify, in one line

#### Scenario: Values are escaped
- **WHEN** a listed title contains `<script>`
- **THEN** it appears as text on the page, not as markup
