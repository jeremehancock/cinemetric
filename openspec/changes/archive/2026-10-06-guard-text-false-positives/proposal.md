## Why

The read-only guard reads a shell command's whole text. If that text mentions the Plex server
(`plex.tv`, `:32400`, the configured address) and also a write word (`DELETE`, `curl -d`,
`/refresh`), the command is blocked, even when nothing in it could send a request. It happened while
opening Cinemetric's own pull request: `gh pr create` with a description that mentioned `plex.tv`,
`:32400` and a `curl -X DELETE` example was refused. The same happens with commit messages, notes
written to a file and docs examples. It mostly bites work on Cinemetric itself, but anyone who asks
Claude to write notes about their Plex server can hit it too.

## What Changes

- The guard lets a shell command through without the server checks when every program the command
  runs only handles text and can't reach a server: writing a commit, opening a pull request or issue
  with `gh`, printing with `echo` or `printf`, copying text into a file with `cat` or `tee`, or
  searching with `grep`. Text inside quotes and here-documents (a block of text fed to a command,
  written `<<'EOF' ... EOF`) is then treated as text, not as a command.
- This includes text built with `$(...)`, such as the usual `git commit -m "$(cat <<'EOF' ... EOF)"`,
  as long as the command inside is also one of those text-only programs.
- Anything the guard can't read with confidence (unusual shell syntax, a pipe into `sh` or `python`,
  a program not on the text-only list, `/dev/tcp`) is checked exactly as today. So the change can
  only remove false alarms; every command blocked today that could really send a request is still
  blocked.
- Version bump for `cinemetric` (scripts, `plugin.json`, `marketplace.json`), since the guard's
  behavior changes for users.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `read-only-guard`: adds a rule that commands which only handle text (commits, pull requests,
  printing, writing files, searching) aren't checked for writes to the servers.

## Impact

- `plugins/cinemetric/hooks/guard-rules.ts`: a small reader for shell commands and the text-only
  rule; `blockReason` uses it.
- `plugins/cinemetric/tests/guard.test.ts`: tests for the false alarms, and for lookalikes that must
  still be blocked.
- `openspec/specs/read-only-guard/spec.md`: the new requirement.
- Version numbers in every script, `plugin.json` and `marketplace.json`.
- README, SECURITY.md and the website already describe the guard as a safety net that checks
  commands which would change the server; their wording stays accurate.
