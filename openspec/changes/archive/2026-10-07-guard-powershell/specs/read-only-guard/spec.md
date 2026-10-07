## MODIFIED Requirements

### Requirement: Which tool calls are checked
The guard SHALL check every `Bash` and `PowerShell` tool call (the command text) and every `WebFetch`
tool call (the address) before it runs, for writes to the user's servers. It SHALL also check `Bash`,
`PowerShell`, `Write` and `Edit` calls that would switch it off through a Claude Code settings file,
as the `mods` spec describes. It SHALL check `Read`, `Bash` and `PowerShell` calls that would read
Cinemetric's settings file, and every tool call's input and result for the Plex token and Tautulli API
key, as described under "Blocking reads of the settings file", "Refusing to pass the secrets on" and
"Hiding the secrets in what Claude sees". Apart from hiding those secrets in a result, it SHALL NOT
change a call it lets through.

A `PowerShell` command SHALL get the same checks as a `Bash` command, except that the rule in
"Commands that only handle text" SHALL NOT apply to it, since the guard reads commands by Bash's
rules and not PowerShell's.

#### Scenario: An unrelated command
- **WHEN** Claude runs `git status` or `ls`
- **THEN** the command runs unchanged

#### Scenario: A delete from PowerShell
- **WHEN** Claude runs the PowerShell command
  `Invoke-RestMethod -Method Delete -Uri "http://192.168.1.20:32400/library/metadata/123"`
- **THEN** the command is blocked and does not run

#### Scenario: A read from PowerShell
- **WHEN** Claude runs the PowerShell command `Invoke-RestMethod "http://192.168.1.20:32400/identity"`
- **THEN** the command runs unchanged

#### Scenario: A commit message in PowerShell that mentions a write
- **WHEN** Claude runs the PowerShell command `git commit -m "Blocks curl -X DELETE to :32400"`
- **THEN** the command is blocked, because PowerShell commands aren't let through as text-only

### Requirement: What counts as a write
A call aimed at the user's servers SHALL count as a write when any of these is true:
- it names an HTTP method other than `GET` or `HEAD` (`POST`, `PUT`, `PATCH`, `DELETE`), for example
  through `curl -X`, `curl --request`, `wget --method`, PowerShell's `-Method`, Python's
  `method="POST"`, `requests.post(`, `requests.put(`, `requests.patch(` or `requests.delete(`, or
  .NET's `PostAsync(`, `PutAsync(`, `PatchAsync(` or `DeleteAsync(`;
- it sends a request body: `curl` with `-d`, `--data` (any form), `--json`, `-F`, `--form`, `-T` or
  `--upload-file`, `wget` with `--post-data`, `--post-file`, `--body-data` or `--body-file`, or .NET's
  `UploadString(`, `UploadData(`, `UploadFile(` or `UploadValues(` (and their `Async` forms), which
  send with `POST` unless told otherwise;
- it is a Tautulli API call whose `cmd=` value is not a read command. Read commands are those starting
  with `get_`, plus `arnold`, `status`, `search`, `docs` and `docs_md`;
- it requests a Plex path that changes things even with `GET`: a path containing `/refresh`,
  `/:/scrobble`, `/:/unscrobble`, `/:/progress`, `/:/timeline` or `/status/sessions/terminate`. Paths
  that Plex changes with other methods (`/:/rate`, `/emptyTrash`, `/library/optimize`,
  `/library/clean/`, `/actions/`) SHALL count too, in case the server also accepts them through
  `GET`.

Anything else aimed at the user's servers SHALL be let through, so read-only checks and Cinemetric's
own scripts keep working.

#### Scenario: A delete with curl
- **WHEN** Claude runs `curl -X DELETE "http://192.168.1.20:32400/library/metadata/123?X-Plex-Token=..."`
- **THEN** the command is blocked and does not run

#### Scenario: A read-only check with curl
- **WHEN** Claude runs `curl -s "http://192.168.1.20:32400/identity"`
- **THEN** the command runs unchanged

#### Scenario: A library scan through a GET
- **WHEN** Claude runs `curl "http://192.168.1.20:32400/library/sections/1/refresh?X-Plex-Token=..."`
- **THEN** the command is blocked, because that address starts a library scan

#### Scenario: Stopping someone's stream through a GET
- **WHEN** Claude runs `curl "http://192.168.1.20:32400/status/sessions/terminate?sessionId=abc&reason=x"`
- **THEN** the command is blocked, because that address stops a stream

#### Scenario: A delete through .NET
- **WHEN** Claude runs `$c.DeleteAsync("http://192.168.1.20:32400/library/metadata/1")`
- **THEN** the command is blocked

#### Scenario: An upload through .NET
- **WHEN** Claude runs `(New-Object Net.WebClient).UploadString("http://192.168.1.20:32400/:/prefs", "x=1")`
- **THEN** the command is blocked, because it sends data to the server

#### Scenario: A Tautulli command that changes something
- **WHEN** Claude runs a command calling Tautulli with `cmd=delete_history`
- **THEN** the command is blocked

#### Scenario: A Tautulli read
- **WHEN** Claude runs a command calling Tautulli with `cmd=get_activity`
- **THEN** the command runs unchanged

#### Scenario: Running a Cinemetric script
- **WHEN** Claude runs `python3 .../library-report/scripts/library_report.py`
- **THEN** the command runs unchanged, since the script's own allowlist already keeps it read-only

### Requirement: Blocking reads of the settings file
The guard SHALL refuse a call that reads Cinemetric's settings file directly:
- a `Read` tool call whose file is the settings file;
- a `Bash` command that names the settings file, unless every program the command runs is `ls` or
  `stat`, which only show the file's details. Commands the guard can't read (see "Commands that only
  handle text") SHALL count as running other programs;
- a `PowerShell` command that names the settings file, whatever it runs.

A command names the settings file when its text contains `.config/cinemetric/config.json`,
`XDG_CONFIG_HOME/cinemetric/config.json` or `XDG_CONFIG_HOME}/cinemetric/config.json` (with either
kind of slash), or the file's full path on this computer.

The refusal SHALL name the Cinemetric read-only guard, say the file holds the user's Plex token and
Tautulli API key, and say that `setup.py status` reports what is set up without showing them.

#### Scenario: Reading the settings with the Read tool
- **WHEN** Claude uses the Read tool on `~/.config/cinemetric/config.json`
- **THEN** the call is refused and Claude is pointed to `setup.py status`

#### Scenario: Printing the settings from the shell
- **WHEN** Claude runs `cat ~/.config/cinemetric/config.json`
- **THEN** the command is refused

#### Scenario: Printing the settings from PowerShell
- **WHEN** Claude runs the PowerShell command
  `Get-Content $env:USERPROFILE\.config\cinemetric\config.json`
- **THEN** the command is refused

#### Scenario: Checking the file's permissions
- **WHEN** Claude runs `ls -l ~/.config/cinemetric/config.json`
- **THEN** the command runs unchanged

#### Scenario: Checking what is set up
- **WHEN** Claude runs `python3 .../setup/scripts/setup.py status`
- **THEN** the command runs unchanged

### Requirement: Refusing to pass the secrets on
The guard SHALL refuse any tool call whose input contains a protected value, before it runs. The one
exception SHALL be a `Bash` or `PowerShell` command, or a `WebFetch` address, that counts as aimed at
the user's servers (see "What counts as aimed at the user's servers"), since sending the token to the
user's own server is how it is meant to be used. Such a call SHALL still be checked for writes as
usual, so a write is refused with the message that names the write. The refusal SHALL name the
Cinemetric read-only guard, say the call contains the user's Plex token or Tautulli API key, and
SHALL NOT repeat the value.

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

#### Scenario: A read from PowerShell with the token
- **WHEN** Claude runs the PowerShell command
  `Invoke-RestMethod "http://192.168.1.20:32400/identity?X-Plex-Token=<the token>"`
- **THEN** the command runs

#### Scenario: Writing the token to a file from PowerShell
- **WHEN** Claude runs the PowerShell command `Set-Content notes.txt "<the token>"`
- **THEN** the command is refused
