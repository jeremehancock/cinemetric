## Why

README, SECURITY.md, the website and the plugin's setting description all say only the user can
switch the read-only guard off, "never Claude". The code doesn't guarantee that. The guard refuses
the usual routes (`/cinemetric-mods guard off` from Claude, another plugin through the settings menu,
and edits to Claude Code's settings files that mention `read_only_guard`). But it only looks for the
setting's exact name, so an escaped key name, an edit split across two calls, or a small script that
rewrites the settings file would get past it. The guard can't see inside programs, so no amount of
tightening closes that last gap. The security review of PR #38 flagged the wording as stronger than
the check.

## What Changes

- Reword every user-facing promise to match what the code does: the guard is meant to be switched
  off only by the user, and Cinemetric refuses Claude's usual ways of switching it off. Like the
  rest of the guard, this is a safety net, not a lock.
- Places: README's Mods section, SECURITY.md, the website's guard card and "switching mods" text,
  and the setting's description in `plugin.json` (shown in Claude Code's `/config` menu).
- The specs stop requiring the stronger promise and say how it must be described.
- No behavior change. The refusal messages Claude sees ("only the user can switch the guard off")
  stay: they tell Claude the rule, and they're accurate for the routes they refuse.
- Version bump for `cinemetric` (scripts, `plugin.json`, `marketplace.json`), since the text in
  `/config` changes.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `mods`: "Claude can't switch the guard off" gains a rule for how it's described to users: as a
  safety net that refuses Claude's usual ways, never as a promise that Claude can't do it at all.
- `website`: "Explains how to switch mods on and off" says the guard is meant to be switched off
  only by the user, instead of saying only the user can.

## Impact

- `README.md`, `SECURITY.md`, `website/index.html`, `plugins/cinemetric/.claude-plugin/plugin.json`.
- `tests/test_mods.py` (checks the website's wording).
- `openspec/specs/mods/spec.md`, `openspec/specs/website/spec.md`.
- Version numbers in every script, `plugin.json` and `marketplace.json`.
