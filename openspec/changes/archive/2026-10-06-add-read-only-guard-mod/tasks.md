## 1. Plugin scaffolding

- [x] 1.1 Create `plugins/cinemetric/hooks/hooks.json` pointing at `./register.ts`
- [x] 1.2 Add `userConfig` to `plugins/cinemetric/.claude-plugin/plugin.json` with a `read_only_guard` on/off switch, default on, and a plain-English label
- [x] 1.3 Write `hooks/register.ts`: read the switches from `options` and call each enabled mod's setup function from its own file
- [x] 1.4 Check that an older Claude Code without mod support still installs the plugin and runs the skills; if not, settle the fallback in design.md before going further
- [x] 1.5 Make `hooks/hooks.json` carry both an old-style `hooks` section (the `SessionStart` notice) and `modules`, and confirm `claude plugin validate` passes on 2.1.75, 2.1.200, 2.1.260 and the current version
- [x] 1.6 Write `hooks/mods_notice.py` (startup only, once a day, quiet when `CINEMETRIC_MODS_ACTIVE` is set, quiet on any error) and add the `classic.SessionStart` hook that sets the variable
- [x] 1.7 Add Python tests for `mods_notice.py` under `tests/`

## 2. Read-only guard

- [x] 2.1 Verify the list of Plex paths that change things through `GET` against a real server and the Plex API docs; update the spec if it differs
- [x] 2.2 In `hooks/guard.ts`, write the settings loader: find the config file the same way `setup.py` does, keep only the hosts and ports of `plex_url` and `tautulli_url`, re-read when the file changes, treat a missing or damaged file as "no addresses"
- [x] 2.3 Write the "aimed at our servers" check (configured addresses, `plex.tv`, `.plex.direct`, `:32400`, `X-Plex-Token`)
- [x] 2.4 Write the "is a write" check (methods, request bodies, Tautulli `cmd=` allowlist, Plex paths that change things through `GET`)
- [x] 2.5 Add `tool.call` hooks for `Bash` (command text) and `WebFetch` (address) that refuse with the explaining message, and otherwise pass the call on unchanged
- [x] 2.6 Add the failure handling: on an unexpected error, let the call run and show a toast
- [x] 2.7 While the guard is on, refuse Claude's `Write` and `Edit` calls to a `settings.json` or `settings.local.json` inside a `.claude` folder, and `Bash` commands naming such a file, when they mention `read_only_guard`; the message says how the user can switch it off
- [x] 2.8 Run `claude plugin validate plugins/cinemetric` and type-check the module
- [x] 2.9 Also use `PLEX_URL` and `TAUTULLI_URL` from the environment as addresses

## 3. The /cinemetric-mods command

- [x] 3.1 Register `/cinemetric-mods` in `register.ts` so it's there even when every mod is off
- [x] 3.2 With no words: list each mod, its description and whether it's on
- [x] 3.3 With `<mod> on|off`: switch it through the same setting as the config menu and confirm; unknown names or words get the list and the right form

## 4. Tests

- [x] 4.1 Write `*.test.ts` covering every scenario in `specs/read-only-guard/spec.md` (blocked delete, allowed read, library refresh, Tautulli write and read, Cinemetric script, unrelated command, no settings file, damaged settings file, switching servers, guard error, token not in message)
- [x] 4.2 Add tests for the switch and command: guard on by default; no checks when off; `/cinemetric-mods` lists, switches and handles typos; the command still works with every mod off; Claude's edits that switch the guard off through a settings file are refused, while edits to other files containing `read_only_guard` (such as Cinemetric's own source) and unrelated settings edits go ahead
- [x] 4.3 Run `claude plugin test plugins/cinemetric` and confirm all pass
- [x] 4.4 Try it by hand in a Claude Code session: ask Claude to mark something watched with curl and confirm it's blocked with a clear message; type `/cinemetric-mods guard off` and confirm the block goes away without a restart; ask Claude to turn the guard off and confirm it can't

## 5. Website

- [x] 5.1 Add the Mods section after the dashboard section in `website/index.html`: "Claude Code only" label, that mods come with Cinemetric, and the read-only guard described in plain words with its short name and as on by default
- [x] 5.2 Add the "switching mods" part: `/cinemetric-mods` to see what's on, `/cinemetric-mods guard off` as the example with copy buttons (same copy behavior as the setup guide), the `/config` menu as the other way, and one sentence on why only the user can turn the guard off
- [x] 5.3 Add a short mention of the guard to "Look, don't touch", linking to the Mods section, worded as a safety net
- [x] 5.4 Add any styles needed in `website/styles.css`, reusing existing card styles; check it at phone width, without JavaScript, and in the nav if sections are listed there
- [x] 5.5 Add or update Python tests under `tests/` that check the site has the Mods section and the exact `/cinemetric-mods` commands

## 6. Docs

- [x] 6.1 Add a "Mods" section to `README.md`: what comes included, which are on by default, how to switch them (`/cinemetric-mods` and the `/config` menu), that only the user can turn the guard off, what the guard does, that it's a safety net and not a guarantee, and the Claude Code versions needed (2.1.75 for Cinemetric, 2.1.260 for mods)
- [x] 6.2 Add a short note about the guard to `SECURITY.md`
- [x] 6.3 Mention mods in the `marketplace.json` and `plugin.json` descriptions

## 7. Library status line

- [x] 7.1 Add the `library_status_line` switch to `plugin.json` (default off) and the `status` entry to `hooks/mods.ts`
- [x] 7.2 Write `hooks/status-line.ts` (find the newest snapshot, build the line, update on session start and after each turn, clear when switched off) and switch it on in `register.ts`
- [x] 7.3 Write `tests/status-line.test.ts` covering every scenario in `specs/library-status-line/spec.md`, and add a `/cinemetric-mods status on` test
- [x] 7.4 Update the website Mods section: describe the status line, and use `/cinemetric-mods status on` as the example; update `tests/test_mods.py`
- [x] 7.5 Update the README Mods section and the plugin descriptions
- [x] 7.6 Validate, type-check and run every test again

## 8. Release

- [x] 8.1 Bump the version in every script's `VERSION`, `plugin.json` and `marketplace.json` (0.22.0 to 0.23.0)
- [x] 8.2 Run `python3 -m unittest discover -s tests -v` and confirm everything passes
