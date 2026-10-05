## MODIFIED Requirements

### Requirement: Read-only toward Plex
Scripts SHALL send only HTTP `GET` requests to the user's Plex server, and only to the paths in that
script's `ALLOWED_PATHS` list. A request to any other path SHALL be refused in code before it is
sent. Requests to plex.tv SHALL be checked the same way against the script's `PLEX_TV_RULES`. The
only non-`GET` request Cinemetric makes is setup's `POST` to plex.tv to start sign-in.

#### Scenario: A path outside the allowlist
- **WHEN** a script tries to request a Plex path that isn't in its `ALLOWED_PATHS`
- **THEN** it stops with `error: Blocked request to a path outside the allowlist: ...` and nothing
  is sent

#### Scenario: A plex.tv address outside the rules
- **WHEN** `users_and_shares.py` tries to request a plex.tv address, or use a method, that isn't in
  its `PLEX_TV_RULES`
- **THEN** it stops with an error and nothing is sent

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

There SHALL be no analytics, update checks or other third-party services. Pages Cinemetric creates
SHALL NOT make any network requests when opened.

#### Scenario: Building a report
- **WHEN** `library-report`, `server-health`, `watch-activity` or `dashboard` runs
- **THEN** the only network requests go to the configured Plex and Tautulli addresses

#### Scenario: Listing users and shares
- **WHEN** `users_and_shares.py` runs
- **THEN** the only network requests go to the configured Plex server, the configured Tautulli address
  (if set up) and the three plex.tv addresses, all with `GET`

#### Scenario: Opening the dashboard
- **WHEN** the user opens the dashboard page in a browser
- **THEN** the browser makes no network requests

## ADDED Requirements

### Requirement: Other people's private details stay private
Scripts SHALL NOT print, log or include in an error message the email address, access token or
account id of anyone the server is shared with. The users-and-shares spec lists exactly which details
about each person are kept.

#### Scenario: plex.tv returns a friend's token
- **WHEN** a plex.tv response lists a friend with their `accessToken` and `email`
- **THEN** neither appears in the script's output, its progress messages or any error
