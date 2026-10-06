## ADDED Requirements

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
