## MODIFIED Requirements

### Requirement: Choosing and testing a server
`finish` SHALL list only resources that provide a server, with each one's name, whether the user owns
it, and how many addresses it has. Relay addresses SHALL be left out. `select N` SHALL try the
server's addresses local first, then `https` first, and save the first one that answers `GET /` with
the token. Each server SHALL be saved with its own access token from plex.tv. The account token SHALL
be used only for a server the user owns that has no access token of its own. A server the user
doesn't own and that has no access token of its own SHALL be left out of the list, so the account
token is never sent to someone else's server. After saving, `select` SHALL read the media deletion
setting from the saved server with the saved token (see "Media deletion setting" in the conventions
spec) and include `media_deletion_allowed` in its output; this SHALL never stop or undo the save.

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

#### Scenario: Media deletion allowed on the chosen server
- **WHEN** `select` saves a server whose `/:/prefs` has `allowMediaDeletion` on
- **THEN** its output has `media_deletion_allowed` `true`

#### Scenario: Settings refused after saving
- **WHEN** `select` saves a server and `/:/prefs` answers 403
- **THEN** the server stays saved and `media_deletion_allowed` is `null`
