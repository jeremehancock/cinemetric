## 1. Reading shell commands

- [x] 1.1 Add a shell command reader to `hooks/guard-rules.ts` that returns each command the text runs (as words with quotes removed), including commands in `$(...)`, backticks, `<(...)`, `>(...)` and unquoted here-document bodies, or nothing when it meets syntax it doesn't read
- [x] 1.2 Add `onlyHandlesText(text)`: true when the reader succeeds, every command is a text-only program (with the `git` and `gh` subcommand rules), and the text doesn't mention `/dev/tcp` or `/dev/udp`
- [x] 1.3 Add `shellBlockReason`, which returns undefined when `onlyHandlesText` is true (after the cheaper "aimed at the servers" check) and otherwise works like `blockReason`; use it for `Bash` in `guard.ts`, leaving `WebFetch` on `blockReason`

## 2. Tests

- [x] 2.1 Add tests to `plugins/cinemetric/tests/guard.test.ts` for every scenario in the spec delta: PR body, commit message through a here-document, notes written to a file, grep pipeline (all run); pipe into `sh`, substitution running curl, unquoted here-document running curl, `echo; curl`, `git -c` (all blocked)
- [x] 2.2 Add tests for the reader's fallbacks: an unclosed quote, `${...}`, a subshell, a path to a program, and `/dev/tcp` are all checked as before
- [x] 2.3 Run `claude plugin test plugins/cinemetric` and confirm every test passes, old and new

## 3. Release

- [x] 3.1 Bump the version in every script's `VERSION`, `plugin.json` and `marketplace.json` (0.23.0 to 0.23.1)
- [x] 3.2 Run `python3 -m unittest discover -s tests` and confirm everything passes
- [x] 3.3 Validate the change with `openspec validate guard-text-false-positives`
