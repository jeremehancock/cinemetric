## Context

The read-only guard (`plugins/cinemetric/hooks/guard.ts`, rules in `guard-rules.ts`) runs a
`tool.call` hook on `Bash`, `WebFetch`, `Write` and `Edit`. Each hook looks at the call before it runs
and either refuses it (`{ deny }`) or passes it on unchanged (`next(e)`). It reads Cinemetric's
settings file, keeps only the two hosts, and caches them by the file's modification time.

The scripts already keep the token safe: it goes only in request headers and is never printed (see
the `security` spec). The gap is Claude's own commands outside the skills, which can print the
settings file or the environment and so bring the token into the conversation. From there it can end
up in a synced transcript, an issue, a commit or a published page.

The guard runs in every project the user opens with Claude Code, not just Cinemetric's, so any new
rule has to stay quiet in unrelated work.

The plugin API lets a `tool.call` hook `await next(e)` and then return its own `{ result }`, which
replaces what Claude receives (see `ToolCallResult` in the bundled types). That is what makes hiding
the token in output possible.

## Goals / Non-Goals

**Goals:**
- Claude never sees the user's real Plex token or Tautulli API key in a tool's output.
- Claude can't put the token into anything that leaves the user's computer (an issue, a commit, a
  page) or into a file.
- Clear refusals in the common case (reading the settings file) so Claude can explain and move on.
- No change in unrelated projects except when the token actually appears.

**Non-Goals:**
- Hiding the token in the user's own messages. The guard can't reach them.
- Stopping a program that sends the token somewhere without printing it. That is the same limit as
  the guard's "can't see inside programs Claude writes and runs later".
- Protecting secrets other than Cinemetric's (other services' API keys, SSH keys).
- A separate mod or switch.

## Decisions

### 1. Part of the guard, not a new mod
The guard already has the protection that stops Claude switching it off (the `mods` spec's settings
file check and the `config.set` hook). A separate token mod would need its own copy of that, and a
token protection Claude could switch off is of little use. The cost is one switch for two jobs: a user
who turns the guard off because of a false block also loses token protection. The guard is meant to
stay on, so this is accepted.

The guard keeps its name, short name (`guard`) and setting key (`read_only_guard`). Renaming the
setting would orphan existing users' settings and weaken the switch-off check. Renaming the display
name would touch many requirements in the `mods` and `website` specs for little gain. Only the
descriptions widen.

*Alternative considered:* a new `token` mod, on by default and user-only-off. Rejected for the
duplication above.

### 2. Two layers: hide in output, refuse in input, plus clear refusals for the obvious reads
- **Hiding in output** is the real protection. It doesn't depend on recognising commands, so
  `env`, `python3 -c ...`, `jq`, a Grep hit or a log file are all covered the same way.
- **Refusing secrets in input** covers the token reaching Claude by a route the guard can't hide
  (the user pasting it) and then being written somewhere.
- **Refusing reads of the settings file** is mostly for a good message: without it, Claude reads the
  file, sees labels instead of secrets, and may keep trying. With it, Claude is told why and pointed
  to `setup.py status`.

*Alternative considered:* only the refusal rules (no hiding). Rejected: a pattern list can't keep up
with every way to print a file, and the guard couldn't then keep the "it only keeps the addresses"
rule anyway once it needs the token to check inputs.

*Alternative considered:* also refusing `env` and `printenv`. Rejected: the guard runs in every
project and those are common debugging commands. Hiding covers them without getting in the way.

### 3. One outermost hook for every tool
Add one `on('tool.call', hook)` with no tool matcher, registered before the existing per-tool hooks
so it wraps them (it sees the input first and the final result last). It:
1. loads the secrets (cached, see 4); with none, returns `next(e)` straight away;
2. checks the input for a secret (Decision 5) and refuses if needed;
3. `await next(e)`, then searches the result (Decision 6) and returns a copy with labels if anything
   matched, or the original object if not, so core keeps its own messages.

The engine's types confirm the order: "a plugin's registrations nest in order, first outermost".

The settings-file refusal joins the existing `Bash` hook (before the server checks) and adds a `Read`
hook.

### 4. Loading and caching the secrets
Extend the existing settings reader: one read of the file returns hosts and secrets, cached together
by path and modification time as now. `PLEX_TOKEN` is read from the environment each call (cheap).
The secrets live only in a module variable, which a reload throws away. They are never put in
`$.state` or `$.store`, never passed to `$.ui.toast` or logged. Values shorter than 8 characters are
dropped, so a damaged file holding something like `"x"` can't make the guard hide every `x`.

`hostsFromSettings` in `guard-rules.ts` becomes `readSettings`, returning `{ hosts, secrets }`, still a
plain function so it can be tested without Claude Code.

### 5. Finding a secret in a call's input
Turn the input into text with `JSON.stringify(e)` and look for each secret with a plain substring
search. Stringifying covers every tool, including MCP tools with nested inputs, without knowing their
shapes. JSON escaping can't hide a token, because Plex tokens and Tautulli keys are plain letters,
digits, `-` and `_`.

The exception (a `Bash` or `WebFetch` call aimed at the user's servers) reuses `isAimedAtServers`, so
it stays in step with the existing rules. Writes among those calls are left to the existing write
check further in, so they are refused with the message that names the write (for example "uses the
DELETE method") rather than a vaguer one about the token.

The input checked is the tool's own arguments, without the engine's `tool`, `tool_use_id`,
`consent` and `agentId` fields.

If the guard fails after the tool has run, its `.catch` handler's `next(e)` hands back the result
already there without running the tool again (the engine's replay-safe `next`), so failing open
never runs a command twice.

### 6. Hiding a secret in a result
Walk the result value (objects, arrays, strings) and replace every occurrence in every string,
building a new value only along paths that changed. Do the same for each string in `context`. The
answer handed back is a fresh `{ result, context }`, not core's object with `ref`, because core would
use the messages `ref` names verbatim. A tool that reported an error is answered with a `deny`
carrying its error text with the secrets hidden, which Claude reads as an error result the same way. Search
for the API key before the token if one ever contains the other (longest first), so a label is never
cut in half.

This keeps the result's shape, so core's check against the tool's output schema still passes and the
tool's own formatter still works. Replacing inside, rather than refusing the whole result, means
Claude keeps the useful rest of the output (for example the rest of `env`).

For speed, first check `JSON.stringify(result)` for any secret, and only walk the value when there
is a hit. Most results never match, so the cost is one stringify and one or two substring searches.

### 7. Deciding when a Bash command reads the settings file
Match the file name in the command text: `.config/cinemetric/config.json`,
`XDG_CONFIG_HOME/cinemetric/config.json`, `XDG_CONFIG_HOME}/cinemetric/config.json`, or the full path
the guard computed (Windows backslashes accepted too). If it matches, use the existing shell reader
(`commandsIn`): when every program is `ls` or `stat`, let it through; otherwise, or when the reader
can't follow the command, refuse.

Matching on `.config/cinemetric/config.json` rather than `cinemetric/config.json` keeps searches
in Cinemetric's own source for the shorter name from tripping it.

### 8. Messages
- Settings file: "Cinemetric read-only guard blocked this: Cinemetric's settings file holds the
  user's Plex token and Tautulli API key, so Claude doesn't read it. To see what's set up without
  them, run setup.py status." plus how to switch the guard off.
- Secret in input: "Cinemetric read-only guard blocked this: it contains the user's Plex token or
  Tautulli API key, which Cinemetric keeps out of files, messages and pages." plus how to switch the
  guard off. Never the value.
- Labels: `[Plex token hidden by Cinemetric]`, `[Tautulli API key hidden by Cinemetric]`.

### 9. Failures
Before a call runs: same as now (let it run, toast). While hiding a result: return the result
unchanged and toast "couldn't check a tool's output". Failing closed (withholding the result) was
considered, but a bug would then break every tool in every project; the existing guard already
chose failing open with a notice, and this keeps one behaviour.

## Risks / Trade-offs

- [The user pastes their token into the chat] → The guard can't hide that message. It can still
  refuse to pass the token on. Documented in the limits.
- [A program sends the token without printing it] → Out of scope, same as the existing limit.
  Documented.
- [False refusal when working on Cinemetric itself, for example `grep "~/.config/cinemetric/config.json" README.md`]
  → Clear message; such commands are rare and Claude can search for a shorter string. The hiding
  layer means a narrower match is safe.
- [A tool's output is very large (a big log)] → One stringify and a substring search per secret.
  Linear and fast; walk only on a hit.
- [Token shows up encoded (URL-encoded, base64)] → Not hidden. Plex tokens are URL-safe, so the URL
  case is covered; base64 is accepted as out of scope.
- [Hiding changes what a skill prints, against the `mods` spec] → Scripts never print the token, so
  nothing a skill shows ever matches.

## Migration Plan

No data or settings migration. Users get it with the next plugin update, on by default as part of
the guard. Rolling back is reverting the release; there's nothing stored to clean up.

## Open Questions

- Should the Tautulli address's own API key in a URL (`apikey=...`) be allowed to the user's
  Tautulli the same way as the Plex token? Decision 5's exception already covers it, since the call
  is aimed at the user's servers; confirm the tests include it.
