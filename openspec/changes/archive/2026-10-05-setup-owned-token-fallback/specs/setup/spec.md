## MODIFIED Requirements

### Requirement: Choosing and testing a server
`finish` SHALL list only resources that provide a server, with each one's name, whether the user owns
it, and how many addresses it has. Relay addresses SHALL be left out. `select N` SHALL try the
server's addresses local first, then `https` first, and save the first one that answers `GET /` with
the token. Each server SHALL be saved with its own access token from plex.tv. The account token SHALL
be used only for a server the user owns that has no access token of its own. A server the user
doesn't own and that has no access token of its own SHALL be left out of the list, so the account
token is never sent to someone else's server.

#### Scenario: No address works
- **WHEN** none of the server's addresses answer from this computer
- **THEN** `select` stops with an error naming the server and how many addresses were tried, and
  nothing is saved

#### Scenario: Owned server without its own token
- **WHEN** plex.tv lists a server the user owns without an `accessToken`
- **THEN** `finish` lists it and saves it with the account token

#### Scenario: Shared server without its own token
- **WHEN** plex.tv lists a server the user doesn't own without an `accessToken`
- **THEN** `finish` leaves it out of the list and never saves the account token for it
