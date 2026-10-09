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
Cinemetric's config folder, data folder and snapshots folders SHALL be created readable only by the
user (`700`), and every file holding settings or report data (config, in-progress sign-in, Tautulli
form status, dashboard page, dashboard state, year-in-review pages, year-in-review state and
snapshots) SHALL be created readable only by the user (`600`) from the start, with no moment where looser permissions apply. On
Linux and macOS, a config file owned by another user or accessible to other users SHALL be refused,
with the `chmod 600` command that fixes it. The in-progress sign-in file SHALL be deleted once a
server is selected or setup is cancelled.

#### Scenario: Config readable by others
- **WHEN** a script finds `config.json` with group or other permissions
- **THEN** it refuses to read it and prints `chmod 600 <path>` as the fix

#### Scenario: A new snapshot
- **WHEN** `changes.py` saves the first snapshot for a server
- **THEN** the `snapshots` folder and the server's folder are `700` and the file is `600`

#### Scenario: A new recap page
- **WHEN** `year_in_review.py` writes a recap page
- **THEN** the file is `600` and the data folder is `700`

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

### Requirement: Recap pages go online only by choice
A year-in-review page SHALL be published to claude.ai only when the user has chosen `online` or
`both` for recaps, and only as a private page (visible to the user alone until they choose to share
it). The year-in-review script SHALL never publish anything itself; it only saves the user's choice
and each recap's link. The published page is the same file as the local one, so it keeps the same
rules: no scripts, no outside requests, every server value HTML-escaped, and no person's name in a
whole-server recap.

#### Scenario: Local only
- **WHEN** the saved recap destination is `local`
- **THEN** the recap is not published, and no saved online page is updated

#### Scenario: Never chosen
- **WHEN** no recap destination has been saved
- **THEN** nothing is published until the user chooses `online` or `both`

#### Scenario: A whole-server recap online
- **WHEN** the destination is `both` and a whole-server recap is built
- **THEN** neither the local file nor the online page contains any person's name

### Requirement: Honest about what Cinemetric can't control
`SECURITY.md`, under "What the skills do not protect against", SHALL say in plain words:
- that Cinemetric can't stop Claude from changing the user's server if the user asks it to: the
  skills only read and the read-only guard catches common ways Claude might change things on its
  own, but changes the user asks Claude for are ordinary Claude Code work;
- that Claude Code's own permission prompts are the last check, so the user should read commands
  that mention their server before approving them, and that with commands approved automatically the
  guard is the only check left;
- two Plex settings that limit the damage: switching off "Allow media deletion" (Settings, Library),
  which makes Plex refuse to delete media files for any app, and the "Backup database every three
  days" scheduled task, which keeps copies of the library details and watch history but not the
  media files.

The README's "AI can make mistakes" caution SHALL say the same boundary in one sentence, with a link
to `SECURITY.md`. None of this wording SHALL describe ways to get around the guard, and it SHALL stay
factual rather than alarming.

#### Scenario: Reading SECURITY.md
- **WHEN** a user reads "What the skills do not protect against"
- **THEN** they learn that changes they ask Claude for aren't something Cinemetric controls, that
  Claude Code's permission prompts are the last check, and which two Plex settings limit the damage

#### Scenario: Reading the README caution
- **WHEN** a user reads "AI can make mistakes" in the README
- **THEN** they see one sentence on asking Claude to change things, with a link to `SECURITY.md`

#### Scenario: No ways around the guard
- **WHEN** someone reads the new wording
- **THEN** it doesn't describe how a command or program could get past the guard

