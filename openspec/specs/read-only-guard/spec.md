# read-only-guard Specification

## Purpose
The read-only guard: a mod, on by default, that checks the commands Claude writes on its own and
stops the ones that would change the user's Plex server, Tautulli or plex.tv, that keeps the user's
Plex token and Tautulli API key out of what Claude sees and sends, and that keeps Claude from
switching itself off. It is a safety net on top of the scripts' own read-only rules in the
`security` spec, not a replacement for them.
## Requirements
### Requirement: On by default, can be switched off
The guard SHALL be a mod in the `cinemetric` plugin (see the `mods` spec) with its own switch,
`read_only_guard`, defaulting to on. When it is off it SHALL add no hooks. It SHALL use nothing
outside Claude Code: no Python, no other programs, no downloaded packages.

#### Scenario: Fresh install
- **WHEN** a user installs Cinemetric and changes no settings
- **THEN** the guard checks Claude's commands

#### Scenario: Switched off
- **WHEN** the user turns `read_only_guard` off
- **THEN** no command is checked by the guard

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

### Requirement: What counts as aimed at the user's servers
A call SHALL count as aimed at the user's servers when its text contains any of:
- the host and port of the configured Plex address (`plex_url`), compared without regard to case;
- the host and port of the configured Tautulli address (`tautulli_url`), if set up;
- `plex.tv` or any address ending in `.plex.tv` or `.plex.direct`;
- the default Plex port written as `:32400`;
- `X-Plex-Token`.

The last three SHALL apply even when Cinemetric is not set up, so the guard is useful before setup.

#### Scenario: Addressing the server by its configured address
- **WHEN** the settings say `plex_url` is `http://192.168.1.20:32400` and Claude runs a command
  containing `192.168.1.20:32400`
- **THEN** the command counts as aimed at the user's servers

#### Scenario: Not set up yet
- **WHEN** there is no settings file and Claude runs a command containing `X-Plex-Token`
- **THEN** the command still counts as aimed at the user's servers

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

### Requirement: Explaining a block
A blocked call SHALL be refused with a message that names the Cinemetric read-only guard, says the command would
change something on the Plex server, Tautulli or plex.tv, and says which rule matched (for example
"uses the DELETE method" or "starts a library scan"). The message SHALL NOT include the command's
token or API key. The message SHALL say the user can make the change themselves in Plex or Tautulli,
or switch the guard off themselves (in the config menu, or by typing `/cinemetric-mods guard off`)
if they want Claude to make changes.

#### Scenario: Claude sees why
- **WHEN** a command is blocked
- **THEN** Claude receives the refusal message as the tool's result and can explain it to the user

### Requirement: Where the guard gets the addresses
The guard SHALL use the Plex and Tautulli addresses from the `PLEX_URL` and `TAUTULLI_URL`
environment variables when set, and from `plex_url` and `tautulli_url` in Cinemetric's settings
file, at `$XDG_CONFIG_HOME/cinemetric/config.json` when `XDG_CONFIG_HOME` is set and otherwise
`~/.config/cinemetric/config.json` (the home folder being `HOME`, or `USERPROFILE` on Windows). It
SHALL check against all of them, since the scripts use the environment variables first. It
SHALL read the file again when it changes, so connecting a new server takes effect without a
restart. A missing or unreadable file SHALL NOT be an error: the guard then uses only the rules that
don't need an address.

#### Scenario: Switching servers
- **WHEN** the user runs setup and picks a different server during a session
- **THEN** commands aimed at the new address are checked from then on

#### Scenario: Address set in the environment
- **WHEN** `PLEX_URL` is `http://10.0.0.5:32400` and Claude runs a command containing
  `10.0.0.5:32400`
- **THEN** the command counts as aimed at the user's servers

#### Scenario: Damaged settings file
- **WHEN** the settings file isn't valid JSON
- **THEN** the guard carries on using only the address-free rules and does not block unrelated
  commands

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

### Requirement: Commands that only handle text
A `Bash` command SHALL be let through without the checks for writes to the user's servers when the
guard can read the whole command and every program it runs only handles text. Those programs are:
- `echo`, `printf`, `cat`, `tee`, `head`, `tail`, `grep`, `wc`, `ls`, `pwd`, `cd`, `mkdir`, `true`
  and `false`;
- `git` followed directly by one of `add`, `commit`, `status`, `log`, `diff`, `show`, `tag`,
  `branch`, `checkout`, `switch`, `restore`, `stash`, `notes` or `rev-parse`;
- `gh` followed directly by `pr`, `issue` or `release`.

Reading the command SHALL follow the shell's own rules for quotes, backslashes, comments, the
separators `;`, `&`, `&&`, `|`, `||` and new lines, redirections such as `> file` and `2>&1`,
here-documents (`<<EOF`, `<<-EOF`, `<<'EOF'`) and here-strings (`<<<`). Text in quotes, in a
here-document or in a here-string SHALL count as text given to the program, not as a command. A
program run by `$(...)`, backticks, `<(...)` or `>(...)`, including inside double quotes or an
unquoted here-document, SHALL count as a program the command runs. Words such as `NAME=value` before
the program's name and redirections SHALL NOT count as its name.

The guard SHALL check the command's whole text as usual when:
- any program it runs is not on the list above, or is written with a path (`/usr/bin/cat`);
- the command uses something it doesn't read: `${...}`, `$((...))`, a subshell or group written with
  `(` `)` or `{` `}`, or a quote, `$(...)` or here-document that isn't closed;
- the command mentions `/dev/tcp` or `/dev/udp`, which the shell can use to reach a server directly.

This SHALL only ever let through commands that run text-only programs. It SHALL NOT change how
`WebFetch` calls or the guard's own setting are checked.

#### Scenario: Opening a pull request that talks about the server
- **WHEN** Claude runs `gh pr create --title "Guard" --body "Blocks curl -X DELETE to plex.tv and :32400"`
- **THEN** the command runs unchanged

#### Scenario: A commit message written with a here-document
- **WHEN** Claude runs `git commit -m "$(cat <<'EOF' ... EOF)"` where the message mentions
  `curl -X DELETE "http://192.168.1.20:32400/library/metadata/1"`
- **THEN** the command runs unchanged

#### Scenario: Writing notes to a file
- **WHEN** Claude runs `cat > notes.md <<'EOF'` with text that mentions `192.168.1.20:32400` and
  `/refresh`, followed by `EOF`
- **THEN** the command runs unchanged

#### Scenario: Searching code
- **WHEN** Claude runs `grep -rn "X-Plex-Token" src | grep POST`
- **THEN** the command runs unchanged

#### Scenario: Text piped into a shell
- **WHEN** Claude runs `echo 'curl -X DELETE "http://192.168.1.20:32400/library/metadata/1"' | sh`
- **THEN** the command is blocked, because `sh` is not a text-only program

#### Scenario: A request hidden in a command substitution
- **WHEN** Claude runs `echo "$(curl -X DELETE "http://192.168.1.20:32400/library/metadata/1")"`
- **THEN** the command is blocked, because the substitution runs `curl`

#### Scenario: A request inside an unquoted here-document
- **WHEN** Claude runs `cat <<EOF` with a body containing
  `$(curl -X DELETE "http://192.168.1.20:32400/library/metadata/1")`, followed by `EOF`
- **THEN** the command is blocked, because the shell runs that `curl` while filling in the text

#### Scenario: A text program next to a request
- **WHEN** Claude runs `echo start; curl -X DELETE "http://192.168.1.20:32400/library/metadata/1"`
- **THEN** the command is blocked, because `curl` is not a text-only program

#### Scenario: Git told to run something
- **WHEN** Claude runs `git -c alias.x='!curl -X DELETE http://192.168.1.20:32400/x' x`
- **THEN** the command is blocked, because `git` is not followed directly by one of the listed
  commands

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

