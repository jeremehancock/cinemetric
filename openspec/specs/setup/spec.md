# setup Specification

## Purpose

Connect Cinemetric to a Plex server with "Sign in with Plex", and optionally add Tautulli, without
the token or API key ever passing through the chat. Script: `skills/setup/scripts/setup.py`. Security
rules that apply here (allowed destinations, private files, the local form) are in the `security`
spec.
## Requirements
### Requirement: Sign in with Plex in separate steps
Setup SHALL run as separate commands, because the user approves in their browser in between:
`start` asks plex.tv for a sign-in PIN and returns a `sign_in_url` and `expires_in_minutes`; `finish`
waits up to 60 seconds for approval, then lists the account's servers; `select N` saves server N.
`cancel` deletes the in-progress sign-in and any Tautulli form. Each Cinemetric install SHALL appear
in Plex's Authorized Devices as "Cinemetric", with its own client identifier.

#### Scenario: User hasn't approved yet
- **WHEN** `finish` runs and plex.tv hasn't issued a token within 60 seconds
- **THEN** it returns `step: waiting` and the user can run `finish` again

#### Scenario: Sign-in link expired
- **WHEN** plex.tv answers 404 for the PIN
- **THEN** setup stops with an error saying the sign-in request expired

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

### Requirement: Don't overwrite without asking
`select` SHALL refuse to overwrite an existing config unless `--replace` is given. Switching Plex
servers SHALL keep any saved Tautulli settings.

#### Scenario: Already configured
- **WHEN** `select 1` runs and a config file exists
- **THEN** it stops and says to re-run with `--replace`

### Requirement: Status without secrets
`status` SHALL report whether Cinemetric is configured, the Plex address, whether a token is present,
and the Tautulli address, whether a key is present and whether certificate checking is on. If the
config file is empty or not a JSON object, it SHALL report `damaged: true` instead of failing, so
setup can continue with `--replace`.

#### Scenario: Damaged config
- **WHEN** `config.json` exists but is empty
- **THEN** `status` returns `configured: false, damaged: true` with a message explaining what to do

### Requirement: Adding Tautulli without the chat
Setup SHALL offer three ways to save a Tautulli address and key, each testing the key with
`get_tautulli_info` before saving:
- `tautulli-auto <address>`: fetch the key with `get_apikey`. Works only when Tautulli has no login;
  returns `step: done` with `tautulli_has_no_login: true`, or `step: needs_form` if a login is required.
- `tautulli-form [--url <address>]` then `tautulli-wait`: a one-time form on this computer that the
  user fills in. `tautulli-wait` waits up to 60 seconds and returns `done`, `waiting` (with
  `last_error`) or `expired`.
- `tautulli`: a prompt in the user's own terminal, with the key hidden as it's typed.

`tautulli-remove` SHALL delete every `tautulli_*` setting.

#### Scenario: Tautulli has a login
- **WHEN** `tautulli-auto` gets a 401/403 or a refusal from Tautulli
- **THEN** it returns `step: needs_form` and saves nothing

#### Scenario: Wrong key in the form
- **WHEN** the user submits the form with a key Tautulli rejects
- **THEN** the form shows the error, nothing is saved, and `tautulli-wait` reports it as `last_error`

### Requirement: Skipping a Tautulli certificate check only by choice
When Tautulli's `https` certificate can't be verified, setup SHALL stop and explain the choice
(`tautulli-auto` returns `step: certificate_problem`; the form shows the error). The check SHALL be
skipped only when the user chooses it: `--skip-cert-check` on `tautulli-auto`, a checkbox the form
shows only after a certificate error, or answering yes in the terminal prompt. The choice is saved as
`tautulli_verify_tls: false` for that address and cleared whenever Tautulli is saved again with
checking on.

#### Scenario: Self-signed certificate
- **WHEN** `tautulli-auto https://nas:8181` hits a certificate that can't be verified
- **THEN** it returns `step: certificate_problem` and saves nothing

