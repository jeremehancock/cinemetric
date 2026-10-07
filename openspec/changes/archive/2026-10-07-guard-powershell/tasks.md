## 1. Guard

- [x] 1.1 Add a `PowerShell` hook to `hooks/guard.ts` that refuses switching the guard off, any command naming Cinemetric's settings file, and writes to the servers (through `blockReason`, without the text-only rule)
- [x] 1.2 Let a `PowerShell` command aimed at the user's own servers carry the token, like `Bash`
- [x] 1.3 Split `commandNamesCinemetricSettings` out of `commandReadsCinemetricSettings` in `hooks/guard-rules.ts`
- [x] 1.4 Count .NET's `PostAsync`, `PutAsync`, `PatchAsync`, `DeleteAsync` and `WebClient` upload methods as writes in `writeReason`

## 2. Tests

- [x] 2.1 Add tests to `plugins/cinemetric/tests/guard.test.ts` for every PowerShell scenario in the spec delta, plus an unrelated command, a write elsewhere and the guard switched off
- [x] 2.2 Run `claude plugin test plugins/cinemetric` and confirm every test passes, old and new

## 3. Release

- [x] 3.1 Bump the version in every script's `VERSION`, `plugin.json` and `marketplace.json` (0.26.0 to 0.26.1)
- [x] 3.2 Run `python3 -m unittest discover -s tests` and confirm everything passes
- [x] 3.3 Validate the change with `openspec validate guard-powershell`
