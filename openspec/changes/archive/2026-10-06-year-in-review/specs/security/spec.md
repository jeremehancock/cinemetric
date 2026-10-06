## MODIFIED Requirements

### Requirement: Only known destinations
Report scripts SHALL contact only the configured Plex server and, if set up, the configured Tautulli
address. Two scripts SHALL additionally contact plex.tv, and only at the addresses listed in their
`PLEX_TV_RULES`:
- The setup script: Plex's sign-in service (`POST` and `GET` on `https://plex.tv/api/v2/pins`, `GET`
  on `https://clients.plex.tv/api/v2/resources`), plus `GET /` on the addresses Plex lists for the
  chosen server, to test them.
- The users-and-shares script: `GET` only, on `https://plex.tv/api/users`,
  `https://plex.tv/api/servers/<machine id>/shared_servers` and
  `https://plex.tv/api/invites/requested`, because who a server is shared with is only stored on
  plex.tv.

The dashboard and changes scripts SHALL contact nothing themselves; they only run other Cinemetric
scripts. There SHALL be no analytics, update checks or other third-party services. Pages Cinemetric
creates SHALL NOT make any network requests when opened.

#### Scenario: Building a report
- **WHEN** `library-report`, `server-health`, `watch-activity`, `unwatched` or `dashboard` runs
- **THEN** the only network requests go to the configured Plex and Tautulli addresses

#### Scenario: Finding something to watch
- **WHEN** `what_to_watch.py` runs
- **THEN** the only network requests go to the configured Plex server

#### Scenario: Looking for episode gaps
- **WHEN** `episode_gaps.py` runs
- **THEN** the only network requests go to the configured Plex server

#### Scenario: Checking what's likely to transcode
- **WHEN** `playback_check.py` runs
- **THEN** the only network requests go to the configured Plex server and, if set up, the configured
  Tautulli address

#### Scenario: Building a year in review
- **WHEN** `year_in_review.py` runs
- **THEN** the only network requests go to the configured Plex server and, if set up, the configured
  Tautulli address

#### Scenario: Listing users and shares
- **WHEN** `users_and_shares.py` runs
- **THEN** the only network requests go to the configured Plex server, the configured Tautulli address
  (if set up) and the three plex.tv addresses, all with `GET`

#### Scenario: Opening the dashboard
- **WHEN** the user opens the dashboard page in a browser
- **THEN** the browser makes no network requests

#### Scenario: Opening a recap page
- **WHEN** the user opens a year-in-review page in a browser
- **THEN** the browser makes no network requests

#### Scenario: Saving, listing or forgetting snapshots
- **WHEN** `changes.py save`, `changes.py list`, `changes.py forget` or `changes.py trends` runs
- **THEN** no network connection is opened

### Requirement: Private files
Cinemetric's config folder, data folder and snapshots folders SHALL be created readable only by the
user (`700`), and every file holding settings or report data (config, in-progress sign-in, Tautulli
form status, dashboard page, dashboard state, year-in-review pages, year-in-review state and
snapshots) SHALL be created readable only by the user (`600`) from the start, with no moment where looser permissions apply. On
Linux and macOS, a config file owned by another user or accessible to other users SHALL be refused,
with the `chmod 600` command that fixes it. The in-progress sign-in file SHALL be deleted once a
server is selected or setup is cancelled.

#### Scenario: Config readable by others
- **WHEN** a script finds `config.json` with group or other permissions
- **THEN** it refuses to read it and prints `chmod 600 <path>` as the fix

#### Scenario: A new snapshot
- **WHEN** `changes.py` saves the first snapshot for a server
- **THEN** the `snapshots` folder and the server's folder are `700` and the file is `600`

#### Scenario: A new recap page
- **WHEN** `year_in_review.py` writes a recap page
- **THEN** the file is `600` and the data folder is `700`

## ADDED Requirements

### Requirement: Recap pages go online only by choice
A year-in-review page SHALL be published to claude.ai only when the user has chosen `online` or
`both` for recaps, and only as a private page (visible to the user alone until they choose to share
it). The year-in-review script SHALL never publish anything itself; it only saves the user's choice
and each recap's link. The published page is the same file as the local one, so it keeps the same
rules: no scripts, no outside requests, every server value HTML-escaped, and no person's name in a
whole-server recap.

#### Scenario: Local only
- **WHEN** the saved recap destination is `local`
- **THEN** the recap is not published, and no saved online page is updated

#### Scenario: Never chosen
- **WHEN** no recap destination has been saved
- **THEN** nothing is published until the user chooses `online` or `both`

#### Scenario: A whole-server recap online
- **WHEN** the destination is `both` and a whole-server recap is built
- **THEN** neither the local file nor the online page contains any person's name
