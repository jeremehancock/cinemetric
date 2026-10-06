## MODIFIED Requirements

### Requirement: Built from the other report scripts
The dashboard SHALL get its data by running `library_report.py` (with `--snapshot-items`),
`server_health.py` (with `--stuck-wait 0 --snapshot-items`; the dashboard doesn't show the stuck task
check and shouldn't wait for it), `watch_activity.py` (with `--days 30 --top 8 --recent 10`),
`users_and_shares.py` (with `--snapshot-items`) and `unwatched.py` (with `--limit 10`) side by side,
so it has exactly their read-only behavior. It SHALL never contact Plex, plex.tv or Tautulli itself.
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

#### Scenario: Saving the snapshot
- **WHEN** the dashboard is built and the library, server health and sharing reports succeed
- **THEN** `changes.py save` receives those three reports, today's snapshot is saved, and the build
  output has `snapshot_saved` with today's date

### Requirement: Build output
The page SHALL be written to `dashboard.html` in the data folder (or `--output PATH`), replacing it in
one step, whatever destination was chosen: for an online-only dashboard this file is what gets
published. The script SHALL print `output`, `server`, `sections_missing`, `names_hidden`,
`destination` (`local`, `online`, `both`, or `null` if never chosen), `online_page` (the saved link,
or `null`), `ask` (containing `destination` when none is saved), `old_schedule_removed` and
`snapshot_saved` (the date saved, or `null`).

#### Scenario: First run
- **WHEN** the dashboard is built and no destination has been saved
- **THEN** the page is written, `destination` is `null` and `ask` contains `destination`

#### Scenario: Later run
- **WHEN** the dashboard is built after `both` was saved and an online page link was saved
- **THEN** `destination` is `both`, `online_page` is the saved link and `ask` is empty

## ADDED Requirements

### Requirement: Changes section
The page SHALL have a "Since <date>" section near the top, built from the `since_snapshot` sections
of the library, server health and sharing reports (the snapshot date shown is the oldest of the
three). It SHALL show:
- library totals (titles added and removed, episodes added and removed, files that became unavailable
  or are available again, and the size change), then up to 5 named titles added and 5 that became
  unavailable per library, with new, removed and renamed libraries named;
- each server change (version, update, remote access) as one line;
- sharing changes: people added and removed, invites accepted, library and download changes. When
  names are hidden, these SHALL be shown as counts only, with no person's name.

When every `since_snapshot` is `null`, the section SHALL be titled "What changed" and say that the
first snapshot was saved and changes will show from the next day's build (or, if no snapshot could be
saved, that there is no earlier snapshot to compare with yet). When a report failed, its part SHALL be
left out; when the library, server health and sharing reports all failed, the section SHALL be left
out. When nothing changed, the section SHALL say so in one line.

#### Scenario: Names hidden
- **WHEN** the dashboard is built with names hidden and a friend was added since the snapshot
- **THEN** the section says one person was added and the friend's name is not on the page

#### Scenario: First build
- **WHEN** the dashboard is built for the first time
- **THEN** the section says the first snapshot was saved and changes will show from the next day

#### Scenario: A title name with HTML in it
- **WHEN** a title added since the snapshot is named `<b>Test</b>`
- **THEN** it appears HTML-escaped on the page
