## Context

Cinemetric's scripts are already read-only in code: each sends only `GET` requests to an allowlist
of paths (see `openspec/specs/security`). What isn't covered is Claude acting outside those scripts,
for example writing its own `curl` or Python command while troubleshooting. Claude Code mods are
plugins made of function hooks written in TypeScript. A `tool.call` hook runs before each tool call
and can refuse it (`return { deny: "<reason>" }`) or let it continue (`next(e)`). A plugin can hold
skills and a hooks module side by side, and its `userConfig` settings show up as rows in Claude
Code's config menu, so mods can ship inside the existing `cinemetric` plugin.

## Goals / Non-Goals

**Goals:**
- Block the common ways Claude could write to Plex, Tautulli or plex.tv from a shell command or
  web fetch, and tell Claude why.
- Set up `plugins/cinemetric/hooks/` as the home for this and future mods, each with an on/off
  switch.
- Present mods on the existing website and README without disturbing the skill sections.

**Non-Goals:**
- A sandbox. The guard reads command text; it can't see inside a program Claude writes to a file
  and runs later, or a command built up from variables at run time.
- Checking Cinemetric's own scripts (their allowlists already do that).
- Any change to what the skills or their scripts do.
- Other mods (Now Playing panel, status line and so on). They come later as their own changes.

## Decisions

**Mods ship inside `cinemetric`, each with a switch.** One install gets everything, and the website
and README keep a single set of install steps. The alternative, a separate `cinemetric-mods` plugin,
was the first plan; it lets people skip mods entirely, but switches give the same choice with less to
explain. The guard defaults to on because it only ever stops writes the user didn't ask Cinemetric
for. Later mods default to off because they change what the user sees (panels, notices) and should be
opted into.

**One starting file, one file per mod.** Claude Code loads one hooks module per plugin
(`hooks/hooks.json` names it). `register.ts` reads the switches from `options` (the `userConfig`
values) and calls each enabled mod's own setup function, imported from its file (`guard.ts` and later
others). Claude Code reloads the module when a switch changes, so turning a mod on or off needs no
restart.

**A `/cinemetric-mods` command, and Claude can't turn the guard off.** The config menu works, but
typing `/cinemetric-mods guard off` is easier to explain on the website and in the guard's block
message. A slash command is typed by the user, so it counts as the user's choice. A tool Claude can
call to switch mods is left for when a second mod exists, since the guard is the only mod and Claude
must not be able to switch it off: otherwise Claude could hit a block, turn the guard off and retry,
without the user noticing. For the same reason the guard refuses Claude's own edits that would switch it
off through Claude Code's settings files. That check is narrow on purpose: a call is refused only if
it targets a `settings.json` or `settings.local.json` inside a `.claude` folder **and** mentions
`read_only_guard`. Checking for the name alone was considered and dropped: the name is generic enough
that an unrelated project could use it, and it would also have blocked edits to Cinemetric's own
source while developing it. This only matters when the guard is
on; once the user turns it off, there is nothing left to protect.

**Watch `Bash` and `WebFetch` for writes to the servers.** Those are the two tools that can reach a server. `WebFetch`
only sends `GET`, so for it only the "changes things even with GET" paths and Tautulli `cmd=` rule
can match. Checking `Write` and `Edit` (scanning file contents for write requests) was considered and
left out: it would flag harmless files such as docs and tests that mention `POST`, and still wouldn't
catch everything. (`Write` and `Edit` are checked only for the guard's own setting name, as above.)

**Text matching in two steps: "aimed at our servers" and then "is a write".** A command is only
blocked when both are true. That keeps false alarms low: `curl -X POST` to some other website isn't
Cinemetric's business, and a `GET` to the Plex server is fine. The "aimed at" check uses the
configured addresses plus address-free signs (`plex.tv`, `.plex.direct`, `:32400`, `X-Plex-Token`)
so it still works before setup or when Claude uses a different address for the same server.

**Tautulli: allow known reads, block the rest.** Tautulli's write commands are many and varied
(`delete_*`, `terminate_session`, `notify`, `restart`, `update`, `edit_*`, `set_*` and more). Listing
the reads (`get_*` plus a few) is safer than trying to list every write. A false block only means
the user runs that command themselves.

**Plex paths that change things through GET.** Some Plex addresses act on a plain `GET` (for example
`/library/sections/<id>/refresh` starts a scan and `/:/scrobble` marks something watched). The
list in the spec was checked against python-plexapi's source (the most widely used Plex library),
which sends plain `GET`s to `/library/sections/<id>/refresh`, `/:/scrobble`, `/:/unscrobble`,
`/:/progress`, `/:/timeline` and `/status/sessions/terminate`. It was not tried against a live
server, since that would change the server. Addresses Plex changes with `PUT` are listed too, in case
a server also accepts them through `GET`. Section timelines (`/library/sections/<id>/timeline`) are
reads and stay allowed, which is why the rule names `/:/timeline` and not `/timeline`.

**Read the addresses from the environment and the settings file.** The scripts use `PLEX_URL` and
`TAUTULLI_URL` before the file, so the guard checks both sources.  The file is read with `$.fs.read` and its location follows the same rule as
`setup.py` (`XDG_CONFIG_HOME`, otherwise `~/.config/cinemetric/config.json`). The guard parses it,
keeps only the two hosts and ports, and drops the rest straight away, so the token never stays in
the mod's memory. It re-reads the file when its modification time changes (or, if the engine can't
report that cheaply, on each guarded call; the file is tiny).

**If the guard breaks, let commands through.** The example pattern from the mod docs refuses every
call when the guard fails. Here that would stop all of Claude's shell commands because of a bug in
an optional extra, which is worse than the risk it covers. The guard instead lets the call run and
shows a toast (a short pop-up notice) saying it couldn't check the command.

**Tests with `claude plugin test`.** Mods are tested with `*.test.ts` files that call the tool
through the engine and check whether the guard refused it. GitHub's test runner doesn't have the
`claude` command, so these run locally before a release; the Python suite in CI stays as it is.

**A second mod: the library status line.** Shipping one mod made the website's on/off example awkward:
the guard starts on and only the user can switch it off, so it shows the exception, not the rule. A
small second mod that starts off gives a plain example (`/cinemetric-mods status on`). Ideas that need
the mod to talk to Plex itself (a Now Playing panel, a live stream counter, notifications) were left
for a later change, since they need the read-only rules rebuilt in the mod's own code. A `/plex`
command and "play in your video player" were also considered: the first doesn't use anything only a
mod can do, and the second needs a careful answer for keeping the token safe. The status line uses
what only mods can do (it changes Claude Code's screen) and reads only snapshot files already on the
computer. It shows no server text, only numbers, so it needs no cleaning of server text. It updates on
`session.start` and `turn.complete`, re-reading a file only when the newest snapshot changes. It
draws its own dim row above the prompt (a `ui.render` hook on `AbovePrompt`) rather than calling
`$.ui.status`: in a live test, Claude Code showed status entries with a notice icon that made the
line look like a warning.

## Risks / Trade-offs

- [Claude can get around a text check, for example with a script file or an address split across
  variables] → Described honestly as a safety net. Claude has no reason to dodge it, and the refusal
  message tells it the user wants read-only behavior.
- [False blocks, such as a command that mentions `:32400` and `--data` for an unrelated reason] →
  The message names the rule that matched, and the user can run the command themselves.
- [Plex path list may be wrong or incomplete] → Marked "to verify"; checked against a real server
  in the tasks.
- [Claude could still switch the guard off through a route the settings check doesn't recognize,
  for example a script file that edits settings when run later] → Same answer as other text checks:
  it's a safety net, Claude has no reason to dodge it, and the block message says the user wants it
  on.
- [The notice's display on an older version wasn't seen end to end: that needs an old Claude Code
  signed in with a real account] → `SessionStart` notices are a long-standing settings-hook feature;
  check by hand on an older version before release if one is available.
- [Versions older than 2.1.75 still can't load the plugin, because they reject `userConfig`] →
  Accepted: 2.1.75 is from March 2026. The README states the minimum.
- [Mods are new in Claude Code and their API may change] → Fixing a mod is a normal Cinemetric
  release; the switches let users turn off a mod that misbehaves in the meantime.
- [Mod changes now bump the version of every script, even when no script changed] → Accepted; it
  keeps the one-version rule simple.

## Older Claude Code versions

Tested by installing old releases in a throwaway config folder and running `claude plugin
validate` and `claude plugin install` against them:

- Mods (`"modules"` in `hooks/hooks.json`) need **2.1.260** (released 2026-09-03). On 2.1.200 a
  hooks file with only `modules` makes the whole plugin show `failed to load`, skills included.
- `userConfig` in `plugin.json` needs **2.1.75** (2026-03-13); 2.0.77 rejects it.

**Decision: one plugin, a hooks file older versions accept, and a notice.** A hooks file holding both
an old-style `hooks` section and `modules` passes on 2.1.200, 2.1.260 and 2.1.292: older versions
ignore `modules`. The old-style section holds one `SessionStart` settings hook that runs
`mods_notice.py`. Hooks aren't told the Claude Code version, so the notice decides from a handoff
instead: the hooks module hooks `classic.SessionStart` and sets `CINEMETRIC_MODS_ACTIVE` with
`$.env.set` before calling `next`, so the settings hook beneath it inherits the variable. Tested on
2.1.292 with a throwaway plugin under `claude -p --plugin-dir`: the variable arrived. On a version
without mods nothing sets it, so the script shows the notice. Alternatives considered: a separate
mods plugin (an extra install line, and the user preferred one plugin); requiring 2.1.260 outright
(anyone behind would lose every skill with an unclear error); keeping switches out of `userConfig` to
support versions before 2.1.75 (would lose the `/config` switch).

## Migration Plan

Existing users get the guard, switched on, when they update Cinemetric. Nothing else changes for
them. Turning it off is one switch in the config menu.

## Open Questions

- Should the guard also show a status-line note (for example `Plex guard: on`) so the user knows
  it's active? Left out for now to keep the first mod small.
