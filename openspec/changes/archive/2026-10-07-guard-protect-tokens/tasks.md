## 1. Groundwork

- [x] 1.1 Confirm against the engine's types and a quick test that a `tool.call` hook with no tool matcher, registered before the per-tool hooks, wraps them (sees input first, final result last), and that returning a copied `{ result }` after `next(e)` passes the tool's output schema for `Bash`, `Read` and an MCP tool; if not, switch to the fallback in design.md Decision 3 and note it there
- [x] 1.2 In `guard-rules.ts`, replace `hostsFromSettings` with `readSettings` returning `{ hosts, secrets }` (`plex_token`, `tautulli_api_key`, dropping values under 8 characters); update `guard.ts`'s cached loader to keep both, and add `PLEX_TOKEN` from the environment

## 2. Hiding and refusing secrets

- [x] 2.1 Add `findSecret(text, secrets)` and `hideSecrets(value, secrets)` to `guard-rules.ts`: longest secret first, labels `[Plex token hidden by Cinemetric]` and `[Tautulli API key hidden by Cinemetric]`, a new value built only where something changed, the original returned when nothing matched
- [x] 2.2 Add the outermost `tool.call` hook in `guard.ts`: with no secrets pass straight through; refuse when the stringified input holds a secret, unless it's a `Bash` or `WebFetch` call aimed at the user's servers (writes there are left to the write check); otherwise `await next(e)`, quick-check the stringified result and `context`, and hide on a hit
- [x] 2.3 Add the failure handling for the new hook: an error before the call lets it run with the existing toast; an error while hiding returns the result unchanged with a "couldn't check a tool's output" toast; neither toast contains a secret
- [x] 2.4 Add the settings-file rule: a `Read` hook refusing Cinemetric's settings file, and in the `Bash` hook a check (before the server checks) that refuses commands naming the file unless every program is `ls` or `stat`, using `commandsIn`
- [x] 2.5 Add the two refusal messages from design.md Decision 8 to `guard-rules.ts`, each ending with how the user can switch the guard off

## 3. Tests

- [x] 3.1 Add cases to `plugins/cinemetric/tests/guard.test.ts` for every scenario in `specs/read-only-guard/spec.md`: token from the file, from `PLEX_TOKEN`, both; new token after the file changes; nothing set up; `env` output hidden; roundabout read hidden; log file via Read hidden; ordinary output untouched (same object); Read and `cat` of the settings file refused; `ls -l` and `setup.py status` allowed; `gh issue create`, Write and an MCP call with the token refused; read-only `curl` to the server with the token allowed; Tautulli `apikey=` to the user's Tautulli allowed; refusals and toasts never contain the secret; short placeholder values ignored; errors while checking and while hiding
- [x] 3.2 Run `claude plugin validate plugins/cinemetric`, type-check with `tsc -p plugins/cinemetric` (not installed on this machine, so skipped), and run `claude plugin test plugins/cinemetric`; confirm all pass
- [x] 3.3 Try it by hand in a Claude Code session: ask Claude to show the settings file (refused), run `env` with `PLEX_TOKEN` set (hidden), paste a fake token and ask Claude to put it in a file (refused), and run a skill (unchanged output)

## 4. Descriptions and docs

- [x] 4.1 Update the guard's description in `hooks/mods.ts` and its `userConfig` description in `plugin.json` to mention keeping the token out of Claude's sight
- [x] 4.2 Update the README Mods table and the guard caution: token protection, and the limits (programs run later, a token the user pastes themselves)
- [x] 4.3 Update the "read-only guard" section of `SECURITY.md`, including that the guard now holds the token in memory only to recognise it
- [x] 4.4 Update `website/index.html`: the guard's card and the "Look, don't touch" intro, keeping card lengths similar; update `tests/test_mods.py` if it checks that wording

## 5. Release

- [x] 5.1 Bump the version in every script's `VERSION`, `plugin.json` and `marketplace.json` (0.23.2 to 0.24.0)
- [x] 5.2 Run `python3 -m unittest discover -s tests -v` and confirm everything passes
