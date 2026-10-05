## MODIFIED Requirements

### Requirement: Built from the other report scripts
The dashboard SHALL get its data by running `library_report.py`, `server_health.py` (with
`--stuck-wait 0`, since the dashboard doesn't show the stuck task check and shouldn't wait for it) and
`watch_activity.py` (with `--days 30 --top 8 --recent 10`) side by side, so it has exactly their
read-only behavior. It SHALL never contact Plex or Tautulli itself. A report that fails or runs longer
than 30 minutes SHALL leave its section out, with the reason shown on the page and in
`sections_missing`. If all three fail, the dashboard SHALL fail with the first error.

#### Scenario: Watch activity fails
- **WHEN** the watch-activity script exits with an error
- **THEN** the page is still written, the watch section shows the reason, and `sections_missing` has
  a `watch` entry

#### Scenario: A Plex task is running while the dashboard builds
- **WHEN** the dashboard is built while Plex is scanning a library
- **THEN** `server_health.py` is run with `--stuck-wait 0` and the build doesn't wait for a second
  task check
