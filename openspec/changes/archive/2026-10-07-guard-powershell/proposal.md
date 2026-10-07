## Why

On Windows, Claude Code can run commands through a `PowerShell` tool instead of `Bash`. The read-only
guard only checks `Bash` and `WebFetch`, so a PowerShell command such as
`Invoke-RestMethod -Method Delete` aimed at the Plex server would run unchecked, and so would one that
prints Cinemetric's settings file or switches the guard off through a settings file. The write rules
already know PowerShell's `-Method`; they just never see PowerShell's commands.

## What Changes

- The guard checks every `PowerShell` tool call the way it checks `Bash`: writes to the user's
  servers, switching the guard off through a Claude Code settings file, and reading Cinemetric's
  settings file.
- Two differences, both on the careful side, because the guard's command reader follows Bash's rules
  and not PowerShell's:
  - No PowerShell command is let through as "text-only". A `git commit` whose message mentions the
    server and a write word is blocked in PowerShell, though not in Bash.
  - A PowerShell command that names the settings file is refused whatever it runs, even if it only
    lists the file.
- The token rule treats a PowerShell command aimed at the user's own server like a `Bash` one: it may
  carry the token there.
- The write rules also catch .NET's request methods, which PowerShell can call directly:
  `HttpClient`'s `PostAsync`, `PutAsync`, `PatchAsync` and `DeleteAsync`, and `WebClient`'s
  `UploadString`, `UploadData`, `UploadFile` and `UploadValues`, which send with `POST`.
- Version bump for `cinemetric` (scripts, `plugin.json`, `marketplace.json`).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `read-only-guard`: checks `PowerShell` calls too, and counts .NET request methods as writes.

## Impact

- `plugins/cinemetric/hooks/guard.ts`: a `PowerShell` hook, and the token rule's exception.
- `plugins/cinemetric/hooks/guard-rules.ts`: the .NET write patterns, and
  `commandNamesCinemetricSettings`, split out of `commandReadsCinemetricSettings`.
- `plugins/cinemetric/tests/guard.test.ts`: PowerShell tests.
- `openspec/specs/read-only-guard/spec.md`: the changed requirements.
- Version numbers in every script, `plugin.json` and `marketplace.json`.
- README, SECURITY.md and the website describe the guard as checking Claude's commands, which stays
  accurate.
