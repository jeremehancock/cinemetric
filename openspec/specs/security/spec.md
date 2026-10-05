# security Specification

## Purpose

The safety rules every Cinemetric script follows, so a user can hand Cinemetric their Plex token
(and optionally a Tautulli API key) without worrying about what it will do with them. This is the
full list; `SECURITY.md` points here.
## Requirements
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

### Requirement: Read-only toward Tautulli
Scripts SHALL run only the Tautulli API commands in that script's `TAUTULLI_COMMANDS` list, and every
one of them SHALL be a command that only reads. The one exception is `get_apikey`, used by setup: if
Tautulli has never had an API key, Tautulli itself creates and saves one in response. If it already
has a key (the usual case), nothing changes.

#### Scenario: A command outside the allowlist
- **WHEN** a script tries to run a Tautulli command that isn't in its `TAUTULLI_COMMANDS`
- **THEN** it stops with `error: Blocked Tautulli command outside the allowlist: ...` and nothing is
  sent

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

### Requirement: No redirects
Scripts SHALL NOT follow HTTP redirects. A redirect SHALL stop the script with an error asking the
user to use the final address, so a credential is never forwarded to a different host.

#### Scenario: The server redirects to https
- **WHEN** Plex answers with a redirect
- **THEN** the script stops with an error explaining that redirects aren't followed and the final
  address should be used

### Requirement: Credentials stay hidden
The Plex token SHALL be sent only in the `X-Plex-Token` header, never in a URL. Neither the Plex
token nor the Tautulli API key SHALL ever be printed, logged or included in an error message.
Tautulli only accepts its key in the URL, so it SHALL be replaced with `[hidden]` in any error text
that could contain it. `setup.py status` SHALL report only whether a token or key is present.

#### Scenario: A network error mentions the URL
- **WHEN** a Tautulli request fails with an error whose text includes the request URL
- **THEN** the API key in that text is replaced with `[hidden]` before it is shown

### Requirement: Credentials never pass through the chat
The user SHALL never be asked to paste a token or key into the chat. The Plex token SHALL go straight
from plex.tv into the config file by "Sign in with Plex". The Tautulli key SHALL be fetched from
Tautulli directly, entered in a one-time form on the user's own computer, or typed into the user's
own terminal with input hidden. The terminal command SHALL refuse to run when it isn't attached to a
real terminal, so Claude can't run it.

#### Scenario: Claude tries the terminal fallback
- **WHEN** `setup.py tautulli` is run without a terminal attached
- **THEN** it refuses and tells the user to run it in their own terminal

### Requirement: Private files
Cinemetric's config folder SHALL be created readable only by the user (`700`), and every file holding settings or
report data (config, in-progress sign-in, Tautulli form status, dashboard page and dashboard state)
SHALL be created readable only by the user (`600`) from the start, with no
moment where looser permissions apply. On Linux and macOS, a config file owned by another user or
accessible to other users SHALL be refused, with the `chmod 600` command that fixes it. The
in-progress sign-in file SHALL be deleted once a server is selected or setup is cancelled.

#### Scenario: Config readable by others
- **WHEN** a script finds `config.json` with group or other permissions
- **THEN** it refuses to read it and prints `chmod 600 <path>` as the fix

### Requirement: Encrypted connections by default
HTTPS certificates SHALL be checked unless the user explicitly turned checking off: `"verify_tls":
false` in the config for Plex, or `tautulli_verify_tls: false` for Tautulli, which is saved only after
the user chose to skip the check during setup. A warning SHALL be printed whenever checking is off,
and whenever plain `http` is used to an address that isn't on the local network.

#### Scenario: Plain http to a public address
- **WHEN** `plex_url` uses `http` and the host isn't a private, loopback or `.local`/`.lan` address
- **THEN** the script prints a warning that the token travels unencrypted, and continues

### Requirement: Address checks
Configured addresses SHALL use `http` or `https`, have a host name, and contain no username,
password, `?` query or `#` fragment. Anything else SHALL be refused.

#### Scenario: Address with a password in it
- **WHEN** `plex_url` is `http://user:pass@host:32400`
- **THEN** the script stops with an error saying the address must not contain a username or password

### Requirement: Local Tautulli form stays local
The one-time Tautulli key form SHALL listen only on `127.0.0.1`, on a random port, at a path containing
a random secret. It SHALL answer only requests whose `Host` is `127.0.0.1:<port>` or
`localhost:<port>` and whose path matches the secret, and shut down after one successful save, when
cancelled, or after 10 minutes.

#### Scenario: A request with another Host name
- **WHEN** a request reaches the form with a `Host` header other than `127.0.0.1` or `localhost`
- **THEN** it gets a 404 and the form is not shown

### Requirement: Server text is treated as data
In every script, titles, names, version strings and other text from Plex, plex.tv or Tautulli SHALL
have control characters removed and be cut to 120 characters before they are printed. The dashboard
SHALL HTML-escape every value it puts on the page.

#### Scenario: A title with a newline in it
- **WHEN** a media title contains control characters
- **THEN** they are replaced with spaces in the script's output

#### Scenario: A shared server with a crafted name
- **WHEN** setup's `finish` lists a server whose name contains control characters or is longer than
  120 characters
- **THEN** the listed name has the control characters replaced with spaces and is cut to 120
  characters

### Requirement: Dashboard goes online only by choice
The dashboard SHALL be published to claude.ai only when the user has chosen `online` or `both`, and
only as a private page (visible to the user alone until they choose to share it). Cinemetric's
scripts SHALL never publish anything themselves; they only save the user's choice and the page's
link. The published page is the same file as the local one, so it keeps the same rules: no scripts,
no outside requests, every server value HTML-escaped, and names left out when the user chose to
hide them.

#### Scenario: Local only
- **WHEN** the saved destination is `local`
- **THEN** the dashboard is not published, and no saved online page is updated

#### Scenario: Names hidden
- **WHEN** names are hidden and the destination is `both`
- **THEN** neither the local file nor the online page contains user names

### Requirement: Other people's private details stay private
Scripts SHALL NOT print, log or include in an error message the email address, access token or
account id of anyone the server is shared with. The users-and-shares spec lists exactly which details
about each person are kept.

#### Scenario: plex.tv returns a friend's token
- **WHEN** a plex.tv response lists a friend with their `accessToken` and `email`
- **THEN** neither appears in the script's output, its progress messages or any error

