## MODIFIED Requirements

### Requirement: What the script requests
The script `skills/users-and-shares/scripts/users_and_shares.py` SHALL request only `/`,
`/library/sections`, `/status/sessions/history/all` and `/:/prefs` from the user's Plex server
(`/:/prefs` SHALL be read only for the media deletion setting (see "Media deletion setting" in the conventions spec)), and only these
plex.tv addresses, each with `GET`:
- `https://plex.tv/api/users` (everyone the owner shares with or has in Plex Home),
- `https://plex.tv/api/servers/<machine id>/shared_servers` (which libraries each person can see on
  this server),
- `https://plex.tv/api/invites/requested` (invites the owner sent that haven't been accepted).

`<machine id>` SHALL come from the `machineIdentifier` that the user's server reports at `/`, and
SHALL contain only letters and digits. These addresses SHALL be listed in the script's
`PLEX_TV_RULES`, and any other plex.tv address SHALL be refused before it is sent. When Tautulli is
set up, the script SHALL run only the Tautulli commands `get_users_table` and `get_history`.

#### Scenario: Building the report
- **WHEN** the script builds a report
- **THEN** every request goes to an allowed path on the configured server, to one of the three
  plex.tv addresses, or to Tautulli's `get_users_table` or `get_history`, and every request is a `GET`

#### Scenario: A strange machine id
- **WHEN** the server's `/` reports a `machineIdentifier` containing `/` or `?`
- **THEN** the script stops with an error and makes no plex.tv request
