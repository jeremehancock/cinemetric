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

#### Scenario: Listing users and shares
- **WHEN** `users_and_shares.py` runs
- **THEN** the only network requests go to the configured Plex server, the configured Tautulli address
  (if set up) and the three plex.tv addresses, all with `GET`

#### Scenario: Opening the dashboard
- **WHEN** the user opens the dashboard page in a browser
- **THEN** the browser makes no network requests

#### Scenario: Saving, listing or forgetting snapshots
- **WHEN** `changes.py save`, `changes.py list` or `changes.py forget` runs
- **THEN** no network connection is opened

### Requirement: Private files
Cinemetric's config folder, data folder and snapshots folders SHALL be created readable only by the
user (`700`), and every file holding settings or report data (config, in-progress sign-in, Tautulli
form status, dashboard page, dashboard state and snapshots) SHALL be created readable only by the user
(`600`) from the start, with no moment where looser permissions apply. On Linux and macOS, a config
file owned by another user or accessible to other users SHALL be refused, with the `chmod 600`
command that fixes it. The in-progress sign-in file SHALL be deleted once a server is selected or
setup is cancelled.

#### Scenario: Config readable by others
- **WHEN** a script finds `config.json` with group or other permissions
- **THEN** it refuses to read it and prints `chmod 600 <path>` as the fix

#### Scenario: A new snapshot
- **WHEN** `changes.py` saves the first snapshot for a server
- **THEN** the `snapshots` folder and the server's folder are `700` and the file is `600`

## ADDED Requirements

### Requirement: Snapshots are read as data
A snapshot file SHALL be treated as untrusted data when read. Scripts SHALL skip, without failing, a
file that is larger than 50 MB, is not valid JSON, is not a JSON object, has a `format` other than 1,
or is not a regular file (for example a symbolic link). Server ids used as folder names SHALL contain
only letters and digits, and file names SHALL match `YYYY-MM-DD.json`; anything else is ignored.
Every text value taken from a snapshot (titles, library names, people's names, versions) SHALL have
control characters removed and be cut to 120 characters before it is printed, and the dashboard
SHALL HTML-escape it.

#### Scenario: A damaged snapshot
- **WHEN** yesterday's snapshot is cut off halfway and so isn't valid JSON
- **THEN** the report skips it, compares with the next older snapshot, and still succeeds

#### Scenario: A snapshot with a crafted title
- **WHEN** a snapshot's title contains a newline and is 500 characters long
- **THEN** a title from it in `since_snapshot` has the newline replaced with a space and is cut to
  120 characters
