## ADDED Requirements

### Requirement: Which secrets the guard protects
The guard SHALL protect two secrets: the Plex token and the Tautulli API key. It SHALL take them from
the same places Cinemetric's scripts do: the `PLEX_TOKEN` environment variable, and `plex_token` and
`tautulli_api_key` in Cinemetric's settings file (the file described under "Where the guard gets the
addresses"). It SHALL protect every value it finds, since the environment variable and the file can
differ. It SHALL read the file again when it changes, so a new token from setup is protected without
a restart. A value shorter than 8 characters SHALL be ignored, so the guard never hides or blocks
ordinary short text because of a damaged or placeholder value. With no values found, the guard SHALL
carry on with its other rules.

#### Scenario: Token in the settings file
- **WHEN** the settings file has a `plex_token`
- **THEN** that value is protected

#### Scenario: Token in the environment
- **WHEN** `PLEX_TOKEN` is set and differs from the token in the settings file
- **THEN** both values are protected

#### Scenario: New token after setup
- **WHEN** the user runs setup again during a session and gets a new token
- **THEN** the new token is protected from then on

#### Scenario: Not set up yet
- **WHEN** there is no settings file and no `PLEX_TOKEN`
- **THEN** nothing is hidden and the guard's other rules work as before

### Requirement: Hiding the secrets in what Claude sees
After any tool runs (built-in, MCP or another plugin's), the guard SHALL look through everything the
tool hands back to Claude and replace each protected value with a label naming what was hidden:
`[Plex token hidden by Cinemetric]` or `[Tautulli API key hidden by Cinemetric]`. The rest of the
output SHALL be left exactly as it was. A tool result with no protected value in it SHALL pass
through untouched. The guard SHALL NOT hide text in the user's own messages, which it can't reach.

#### Scenario: Printing the environment
- **WHEN** Claude runs `env` and `PLEX_TOKEN` is set
- **THEN** Claude sees `PLEX_TOKEN=[Plex token hidden by Cinemetric]` and the rest of the output as
  normal

#### Scenario: A roundabout read of the settings file
- **WHEN** Claude runs `python3 -c "print(open('/home/me/.config/cinemetric/config.json').read())"`
- **THEN** Claude sees the file with the token and API key replaced by their labels

#### Scenario: A log file with the token in a URL
- **WHEN** Claude reads a log file with the Read tool and a line contains `X-Plex-Token=<the token>`
- **THEN** Claude sees `X-Plex-Token=[Plex token hidden by Cinemetric]`

#### Scenario: Ordinary output
- **WHEN** Claude runs `git status`
- **THEN** the output reaches Claude unchanged

#### Scenario: A Cinemetric skill
- **WHEN** Claude runs a Cinemetric script
- **THEN** its output reaches Claude unchanged, since the scripts never print the token

### Requirement: Blocking reads of the settings file
The guard SHALL refuse a call that reads Cinemetric's settings file directly:
- a `Read` tool call whose file is the settings file;
- a `Bash` command that names the settings file, unless every program the command runs is `ls` or
  `stat`, which only show the file's details. The command names the settings file when its text
  contains `.config/cinemetric/config.json`, `XDG_CONFIG_HOME/cinemetric/config.json` or `XDG_CONFIG_HOME}/cinemetric/config.json`, or the file's full
  path on this computer. Commands the guard can't read (see "Commands that only handle text") SHALL
  count as running other programs.

The refusal SHALL name the Cinemetric read-only guard, say the file holds the user's Plex token and
Tautulli API key, and say that `setup.py status` reports what is set up without showing them.

#### Scenario: Reading the settings with the Read tool
- **WHEN** Claude uses the Read tool on `~/.config/cinemetric/config.json`
- **THEN** the call is refused and Claude is pointed to `setup.py status`

#### Scenario: Printing the settings from the shell
- **WHEN** Claude runs `cat ~/.config/cinemetric/config.json`
- **THEN** the command is refused

#### Scenario: Checking the file's permissions
- **WHEN** Claude runs `ls -l ~/.config/cinemetric/config.json`
- **THEN** the command runs unchanged

#### Scenario: Checking what is set up
- **WHEN** Claude runs `python3 .../setup/scripts/setup.py status`
- **THEN** the command runs unchanged

### Requirement: Refusing to pass the secrets on
The guard SHALL refuse any tool call whose input contains a protected value, before it runs. The one
exception SHALL be a `Bash` command or `WebFetch` address that counts as aimed at the user's servers
(see "What counts as aimed at the user's servers"), since sending the token to the user's own server
is how it is meant to be used. Such a call SHALL still be checked for writes as usual, so a write is
refused with the message that names the write. The refusal SHALL name the Cinemetric read-only
guard, say the call contains the user's Plex token or Tautulli API key, and SHALL NOT repeat the
value.

#### Scenario: The user pasted their token and Claude files an issue
- **WHEN** Claude runs `gh issue create` with a body containing the token
- **THEN** the command is refused and the issue isn't created

#### Scenario: Writing the token into a file
- **WHEN** Claude uses the Write tool on `notes.md` with text containing the token
- **THEN** the call is refused

#### Scenario: Publishing a page with the token
- **WHEN** Claude calls an MCP tool to publish a page whose content contains the token
- **THEN** the call is refused

#### Scenario: A write to the user's own server with the token
- **WHEN** Claude runs `curl -X DELETE "http://192.168.1.20:32400/library/metadata/1?X-Plex-Token=<the token>"`
- **THEN** the command is refused with the message saying it uses the DELETE method

#### Scenario: A read from the user's own server
- **WHEN** Claude runs `curl -H "X-Plex-Token: <the token>" "http://192.168.1.20:32400/identity"`
- **THEN** the command runs (and anything it prints has the token hidden)

## MODIFIED Requirements

### Requirement: Which tool calls are checked
The guard SHALL check every `Bash` tool call (the command text) and every `WebFetch` tool call (the
address) before it runs, for writes to the user's servers. It SHALL also check `Bash`, `Write` and
`Edit` calls that would switch it off through a Claude Code settings file, as the `mods` spec
describes. It SHALL check `Read` and `Bash` calls that would read Cinemetric's settings file, and
every tool call's input and result for the Plex token and Tautulli API key, as described under
"Blocking reads of the settings file", "Refusing to pass the secrets on" and "Hiding the secrets in
what Claude sees". Apart from hiding those secrets in a result, it SHALL NOT change a call it lets
through.

#### Scenario: An unrelated command
- **WHEN** Claude runs `git status` or `ls`
- **THEN** the command runs unchanged

### Requirement: The guard's own safety rules
The guard SHALL make no network requests. It SHALL read only Cinemetric's settings file and the
`PLEX_URL`, `TAUTULLI_URL` and `PLEX_TOKEN` environment variables. From the settings file it SHALL use
only `plex_url`, `tautulli_url`, `plex_token` and `tautulli_api_key`. It SHALL hold the token and API
key only in its own memory, only to recognise them, and SHALL NOT show, log, save (including in
Claude Code's session or plugin storage) or pass them on, nor put them in any message, notice or
error.

#### Scenario: Reading settings
- **WHEN** the guard loads the settings file
- **THEN** it keeps the hosts and ports of `plex_url` and `tautulli_url` and the two secrets in
  memory, and nothing else from the file

#### Scenario: A refusal never repeats the secret
- **WHEN** a call is refused because it contains the token
- **THEN** the refusal message does not contain the token

### Requirement: If the guard itself fails
If the guard hits an unexpected error while checking a call before it runs, it SHALL let that call
run and show a short notice that the guard couldn't check it. If it hits an unexpected error while
looking through a tool's result for the secrets, it SHALL hand Claude the result unchanged and show a
short notice that the guard couldn't check that output. It SHALL NOT block every command, or hide
every result, because of its own error. Notices SHALL NOT contain the secrets.

#### Scenario: A bug in the guard
- **WHEN** checking a command throws an error
- **THEN** the command runs, and the user sees a notice that the Cinemetric read-only guard couldn't check it

#### Scenario: A bug while hiding
- **WHEN** looking through a tool's result throws an error
- **THEN** Claude gets the result unchanged, and the user sees a notice that the guard couldn't check
  that output

### Requirement: Honest about its limits
The guard SHALL be described everywhere (README, website, SECURITY.md) as a safety net that catches
common ways of writing to the server and of Claude seeing or passing on the token, not as a
guarantee. Those descriptions SHALL say it can't see inside programs Claude writes to a file and runs
later, and SHALL say it can't hide a token the user types or pastes into the chat themselves (it can
only stop Claude passing it on afterwards).

#### Scenario: Reading the README
- **WHEN** a user reads about the guard
- **THEN** they learn what it catches, including token protection, and that it is a safety net, not
  a guarantee
