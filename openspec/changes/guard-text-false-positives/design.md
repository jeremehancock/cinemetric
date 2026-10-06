## Context

The guard decides in two steps: is the command aimed at the user's servers, and does it look like a
write. Both steps read the command's whole text, so a command that only *mentions* the server and a
write word looks the same as one that sends a request. The case that came up was `gh pr create`
with a description quoting `curl -X DELETE` and `:32400`. Commit messages written with
`git commit -m "$(cat <<'EOF' ... EOF)"`, notes written with `cat > file <<'EOF'`, and `grep` over
Cinemetric's own source hit the same rule.

The guard is a safety net against accidents, not a sandbox: the spec already says it can't see into
programs written to a file and run later. But it must not get easier to slip a real request past it.

## Goals / Non-Goals

**Goals:**
- Let through the common text-only commands: commits, pull requests and issues, `echo`/`printf`,
  writing files with `cat`/`tee` and here-documents, `grep`.
- Never let through a command that runs anything else. Anything unclear falls back to today's check.
- Keep the change inside `guard-rules.ts`, as plain functions that can be tested on their own.

**Non-Goals:**
- A complete shell parser. Unusual syntax simply falls back to today's check.
- Fewer false alarms for commands that do run a network tool or interpreter (for example a
  `python3 -c` that prints a string containing `DELETE` and `:32400`). Those still get the full
  check.
- Changing the `WebFetch` check or the setting checks.

## Decisions

**Skip only when every program is on a short text-only list (an allowlist).** Considered:
1. *Only check commands that run a network tool* (curl, wget, python, ...). This needs a complete
   list of everything that can send a request (interpreters, `sh -c`, `xargs`, `env`, `sudo`,
   `find -exec`, PowerShell, ...). Missing one lets a real write through.
2. *Strip quoted text and here-documents before checking.* The write signal often lives inside quotes
   in a real request too (`curl "http://...:32400/x/refresh"`, `python3 -c "requests.delete(...)"`),
   so stripping quotes would let real writes through.
3. *Pair the write word with the address in the same command part.* Doesn't help the reported case:
   the PR body is one part that contains both.
4. *Allowlist of text-only programs* (chosen). A mistake in the list can only cause a false alarm, never
   a missed write, as long as each listed program can't send requests or run its arguments. Programs
   that can run other commands were left off on purpose: `sed` (its `e` command), `sort`
   (`--compress-program`), `rg` (`--pre`), `find`, `xargs`, `awk`.

**`git` and `gh` only with a listed subcommand right after the name.** `git -c alias.x='!cmd'` and
`git -c core.sshCommand=...` run commands, and `git push`/`fetch`/`clone` talk to servers, so only
local subcommands count and any option before the subcommand falls back. For `gh`, `api` can send
any method, so only `pr`, `issue` and `release` count.

**A small reader for shell commands, returning "couldn't read it" on anything unusual.** It walks the
text once, tracking single and double quotes, backslashes, `#` comments, separators, redirections
(and the word after them, which is a file, not a program), here-documents (body taken from the lines
after the command, up to the closing word) and here-strings. `$(...)`, backticks, `<(...)` and
`>(...)` are read as commands of their own, also inside double quotes; an unquoted here-document's
body is checked for `$(` and backticks the same way. It gives back a list of commands, each a list of
words with quotes removed. When it meets `${`, `$((`, a bare `(`, `)`, `{` or `}` at the start of a
word, or reaches the end inside a quote, substitution or here-document, it returns nothing and the
guard checks the whole text as before.

**Where it plugs in.** A new `shellBlockReason(command, hosts)` is used for `Bash` calls. It first
runs the quick "aimed at the servers" check, so the reader never runs for commands that don't mention
the servers. Then it returns undefined when `onlyHandlesText(command)` is true, and otherwise gives
today's `writeReason` unchanged. `WebFetch` keeps using `blockReason` exactly as before, so web
fetches can't be affected.

**`/dev/tcp` and `/dev/udp` fall back.** Bash can open a network connection through a redirection
such as `> /dev/tcp/host/32400`, so a text-only program can still send a request that way.

## Risks / Trade-offs

- [The reader disagrees with bash on some construct and sees a real command as text] → It only
  accepts a small, well-understood part of shell syntax and gives up on anything else; the tests
  cover the tricky cases (substitution in double quotes, unquoted here-documents, pipes into `sh`,
  separators next to text programs, `git -c`).
- [A text-only program is later found to run commands] → Remove it from the list; the cost is only
  a false alarm.
- [Some false alarms remain, such as `python3 -c 'print("DELETE :32400")'`] → Accepted. Writing the
  text with a listed program, or to a file first, avoids it.
- [Work on the guard's own tests still trips it, e.g. running a test file whose command line has a
  write example] → Unchanged from today; test files are run by name, not with the example inline.

## Migration Plan

Ships in the next plugin version. No settings or data change. Rolling back is reinstalling the
previous version.

## Open Questions

None.
