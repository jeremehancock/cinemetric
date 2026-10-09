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
