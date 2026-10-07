## Why

Cinemetric's scripts never print the Plex token or the Tautulli API key, but Claude can still see them
through its own commands outside the skills. For example, while troubleshooting a skill it might run
`cat ~/.config/cinemetric/config.json` or `printenv`. Once the token is in the conversation it can end
up in a synced transcript, a GitHub issue, a commit or a published page, and a Plex token gives the
same access as the account it belongs to. The guard already watches Claude's commands and already
has protection that stops Claude from switching it off, so it is the natural place to protect the
token too, rather than a new mod that would have to rebuild that protection.

## What Changes

- The guard keeps Claude from seeing the token in two ways:
  - **Blocking the obvious ways in.** Claude's Read tool on Cinemetric's settings file is refused,
    and so is a shell command that names the settings file, unless it only lists or checks the file
    (`ls`, `stat`). The refusal explains why.
  - **Hiding the token in anything Claude sees.** After any tool runs, the guard looks through the
    output for the user's actual Plex token and Tautulli API key and replaces each one with a label
    such as `[Plex token hidden by Cinemetric]` before Claude reads it. This catches the token
    however it got into the output (`env`, a script, a log file, a search).
- The guard also refuses a tool call whose input contains the actual token or API key, unless it is
  a command or web fetch aimed at the user's own Plex server, Tautulli or plex.tv. This covers the
  token reaching Claude another way (for example the user pasting it into the chat) and Claude then
  putting it into a GitHub issue, a file or a published page.
- To recognise the token, the guard now reads the token and API key into memory from the settings
  file and the `PLEX_TOKEN` environment variable. It still never shows, logs, saves or sends them.
  This replaces the current rule that the guard keeps only the two addresses.
- The guard keeps its name ("read-only guard"), short name (`guard`) and setting (`read_only_guard`),
  so nobody's settings change and the protection against Claude switching it off keeps working
  unchanged. Its descriptions widen to say it also keeps the token out of Claude's sight.
- README, SECURITY.md, the website's mod card and the `/cinemetric-mods` description are updated,
  including the honest limits (see design).
- Version bump for `cinemetric` (scripts, `plugin.json`, `marketplace.json`).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `read-only-guard`: adds hiding and blocking of the token and API key; widens which tool calls are
  checked (Read, every tool's output, every tool's input); replaces the "keeps only the addresses"
  safety rule with one that lets the guard hold the secrets in memory only to recognise them;
  updates the "honest about its limits" text.
- `website`: the guard's mod card and the privacy section mention token protection, worded so they
  don't overstate it.

## Impact

- Code: `plugins/cinemetric/hooks/guard.ts` and `guard-rules.ts` (new rules and a new hook on every
  tool's result), `mods.ts` (description, shown by `/cinemetric-mods`), `plugin.json` (`userConfig` description
  shown in `/config`, version).
- Tests: `plugins/cinemetric/tests/guard.test.ts` gains cases for the new rules.
- Docs: `README.md`, `SECURITY.md`, `website/index.html`.
- No change to any skill or script. Scripts already never print the token, so hiding it never
  changes what a skill shows.
- No new network destinations. The guard still makes no network requests.
- Every tool result now passes through a text search. Results are small enough that this should not
  be noticeable, but the design notes how it is kept cheap.
