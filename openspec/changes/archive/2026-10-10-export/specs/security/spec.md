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
scripts. The export script SHALL contact only the configured Plex server itself, and SHALL run the
other scripts it uses with options that keep them to the Plex server (`playback_check.py` with
`--days 0`). There SHALL be no analytics, update checks or other third-party services. Pages Cinemetric
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

#### Scenario: Looking up one title
- **WHEN** `title_lookup.py` runs
- **THEN** the only network requests go to the configured Plex server and, if set up, the configured
  Tautulli address

#### Scenario: Checking subtitles and languages
- **WHEN** `subtitles_and_languages.py` runs
- **THEN** the only network requests go to the configured Plex server, even when Tautulli is set up

#### Scenario: Following people through shows
- **WHEN** `show_progress.py` runs
- **THEN** the only network requests go to the configured Plex server and, if set up, the configured
  Tautulli address

#### Scenario: Reporting on collections and playlists
- **WHEN** `collections_and_playlists.py` runs
- **THEN** the only network requests go to the configured Plex server, even when Tautulli is set up

#### Scenario: Comparing watching with the shelf
- **WHEN** `watch_mix.py` runs
- **THEN** the only network requests go to the configured Plex server and, if set up, the configured
  Tautulli address

#### Scenario: Exporting a workbook
- **WHEN** `export.py` runs, including the scripts it runs for the other tabs
- **THEN** the only network requests go to the configured Plex server, even when Tautulli is set up

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
form status, dashboard page, dashboard state, year-in-review pages, year-in-review state,
exported workbooks and snapshots) SHALL be created readable only by the user (`600`) from the start, with no moment where looser permissions apply. On
Linux and macOS, a config file owned by another user or accessible to other users SHALL be refused,
with the `chmod 600` command that fixes it. The in-progress sign-in file SHALL be deleted once a
server is selected or setup is cancelled. A folder the user names for an exported workbook SHALL
NOT be created or have its permissions changed; only the file is made private.

#### Scenario: Config readable by others
- **WHEN** a script finds `config.json` with group or other permissions
- **THEN** it refuses to read it and prints `chmod 600 <path>` as the fix

#### Scenario: A new snapshot
- **WHEN** `changes.py` saves the first snapshot for a server
- **THEN** the `snapshots` folder and the server's folder are `700` and the file is `600`

#### Scenario: A new recap page
- **WHEN** `year_in_review.py` writes a recap page
- **THEN** the file is `600` and the data folder is `700`

#### Scenario: An export to a folder the user named
- **WHEN** `export.py` saves to `~/Documents`, which has permissions `755`
- **THEN** the file is `600` and the folder is still `755`

### Requirement: Server text is treated as data
In every script, titles, names, version strings and other text from Plex, plex.tv or Tautulli SHALL
have control characters removed and be cut to 120 characters before they are printed. The dashboard
SHALL HTML-escape every value it puts on the page. The export script SHALL store server text in its
workbook only as plain text, never as a formula, and the workbook SHALL hold no formulas, macros or
links (see "Server text never runs" in the export spec).

#### Scenario: A title with a newline in it
- **WHEN** a media title contains control characters
- **THEN** they are replaced with spaces in the script's output

#### Scenario: A shared server with a crafted name
- **WHEN** setup's `finish` lists a server whose name contains control characters or is longer than
  120 characters
- **THEN** the listed name has the control characters replaced with spaces and is cut to 120
  characters

#### Scenario: A title made to be a spreadsheet formula
- **WHEN** a movie's title on the server is `=1+1` and the library is exported
- **THEN** the workbook cell holds the text `=1+1` and the workbook contains no formula
