## MODIFIED Requirements

### Requirement: Built from the other report scripts
The dashboard SHALL get its data by running `library_report.py` (with `--snapshot-items`),
`server_health.py` (with `--stuck-wait 0 --snapshot-items`; the dashboard doesn't show the stuck task
check and shouldn't wait for it), `watch_activity.py` (with `--days 30 --top 8 --recent 10`),
`users_and_shares.py` (with `--snapshot-items`), `unwatched.py` (with `--limit 10`) and
`episode_gaps.py` (with `--limit 10`) side by side, so it has exactly their read-only behavior. It SHALL never contact Plex, plex.tv or Tautulli itself.
A report that fails or runs longer than 30 minutes SHALL leave its section out, with the reason shown
on the page and in `sections_missing`. If every report fails, the dashboard SHALL fail with the first
error.

After the reports finish, the dashboard SHALL pass the library, server health and sharing reports
that succeeded to `changes.py save` on stdin, so a snapshot is saved without fetching anything again.
A failed save SHALL NOT stop the build; the page is still written and `snapshot_saved` is null. The
`snapshot` blocks SHALL NOT be put on the page.

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

#### Scenario: Episode gaps report fails
- **WHEN** `episode_gaps.py` exits with an error
- **THEN** the page is still written with the other sections, the Episode gaps section shows the
  reason, and `sections_missing` has an `episode_gaps` entry

#### Scenario: Saving the snapshot
- **WHEN** the dashboard is built and the library, server health and sharing reports succeed
- **THEN** `changes.py save` receives those three reports, today's snapshot is saved, and the build
  output has `snapshot_saved` with today's date

## ADDED Requirements

### Requirement: Episode gaps section
The page SHALL have an Episode gaps section built from the `episode-gaps` report, showing:
- one line with the number of shows with gaps, missing episodes, unavailable episodes and missing
  seasons across the TV libraries checked;
- each TV library checked with its shows, shows with gaps, missing episodes, unavailable episodes and
  missing seasons;
- the 10 listed shows with the most missing plus unavailable episodes across all libraries, each with
  its library, year, missing seasons, and its missing and unavailable episodes written as season and
  episode numbers with ranges ("S02E03, S02E05 to E07"), at most 5 per show followed by a line saying
  how many more there are;
- the report's `limits` note.

The section SHALL state facts only and SHALL NOT suggest downloading, replacing or deleting anything.
Episode gaps SHALL NOT be added to the server's "Needs a look" list, SHALL NOT change the page's
overall status and SHALL NOT be passed to the snapshot. Hiding names SHALL NOT change this section,
since it contains no person's name. When no show has gaps, the section SHALL say in one line that no
gaps were found between the episodes on the server, and still show the `limits` note. When the server
has no TV library, the section SHALL say so in one line.

#### Scenario: Shows with gaps
- **WHEN** the episode gaps report has 12 shows with gaps and the server has no other issues
- **THEN** the Episode gaps section shows the totals and the 10 shows with the most gaps, and the
  page's overall status is still "Healthy"

#### Scenario: A show with many gaps
- **WHEN** a listed show has 9 separate missing ranges
- **THEN** the section shows its first 5 and a line saying there are 4 more

#### Scenario: No gaps found
- **WHEN** every library in the episode gaps report has `shows_with_gaps` 0
- **THEN** the section says no gaps were found between the episodes on the server, in one line, with
  the `limits` note

#### Scenario: No TV library
- **WHEN** the episode gaps report has no libraries
- **THEN** the section says the server has no TV library, in one line

#### Scenario: Values are escaped
- **WHEN** a listed show title contains `<script>`
- **THEN** it appears as text on the page, not as markup
