# read-only-guard Specification

## Purpose
The read-only guard: a mod, on by default, that checks the commands Claude writes on its own and
stops the ones that would change the user's Plex server, Tautulli or plex.tv, and that keeps Claude
from switching itself off. It is a safety net on top of the scripts' own read-only rules in the
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
The guard SHALL check every `Bash` tool call (the command text) and every `WebFetch` tool call (the
address) before it runs, for writes to the user's servers. It SHALL also check `Bash`, `Write` and
`Edit` calls that would switch it off through a Claude Code settings file, as the `mods` spec
describes. It SHALL NOT change a call it
lets through. Other tools SHALL NOT be checked.

#### Scenario: An unrelated command
- **WHEN** Claude runs `git status` or `ls`
- **THEN** the command runs unchanged

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
  through `curl -X`, `curl --request`, `wget --method`, PowerShell's `-Method`, or Python's
  `method="POST"`, `requests.post(`, `requests.put(`, `requests.patch(` or `requests.delete(`;
- it sends a request body: `curl` with `-d`, `--data` (any form), `--json`, `-F`, `--form`, `-T` or
  `--upload-file`, or `wget` with `--post-data`, `--post-file`, `--body-data` or `--body-file`;
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
`PLEX_URL` and `TAUTULLI_URL` environment variables. It SHALL
use only the two addresses from that file and SHALL NOT keep, show, log or pass on the Plex token or
Tautulli API key stored beside them.

#### Scenario: Reading settings
- **WHEN** the guard loads the settings file
- **THEN** it keeps only the hosts and ports of `plex_url` and `tautulli_url`

### Requirement: If the guard itself fails
If the guard hits an unexpected error while checking a call, it SHALL let that call run and show a
short notice that the guard couldn't check it. It SHALL NOT block every command because of its own
error.

#### Scenario: A bug in the guard
- **WHEN** checking a command throws an error
- **THEN** the command runs, and the user sees a notice that the Cinemetric read-only guard couldn't check it

### Requirement: Honest about its limits
The guard SHALL be described everywhere (README, website, SECURITY.md) as a safety net that catches
common ways of writing to the server, not as a guarantee. Those descriptions SHALL say it can't see
inside programs Claude writes to a file and runs later.

#### Scenario: Reading the README
- **WHEN** a user reads about the guard
- **THEN** they learn what it catches and that it is a safety net, not a guarantee

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

