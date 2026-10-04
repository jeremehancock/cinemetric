## MODIFIED Requirements

### Requirement: Only known destinations
Report scripts SHALL contact only the configured Plex server and, if set up, the configured Tautulli
address. The setup script SHALL additionally contact only Plex's sign-in service (`POST` and `GET` on
`https://plex.tv/api/v2/pins`, `GET` on `https://clients.plex.tv/api/v2/resources`, as listed in
`PLEX_TV_RULES`) and `GET /` on the addresses Plex lists for the chosen server, to test them. There
SHALL be no analytics, update checks or other third-party services. Pages Cinemetric creates SHALL
NOT make any network requests when opened.

#### Scenario: Building a report
- **WHEN** any report script runs
- **THEN** the only network requests go to the configured Plex and Tautulli addresses

#### Scenario: Opening the dashboard
- **WHEN** the user opens the dashboard page in a browser
- **THEN** the browser makes no network requests
