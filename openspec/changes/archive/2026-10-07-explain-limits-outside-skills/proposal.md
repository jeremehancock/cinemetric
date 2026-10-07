## Why

Cinemetric's skills only read, and the read-only guard catches common ways Claude might change the
server on its own. But once Cinemetric is set up, Claude is still a general assistant working on the
user's computer, where the token is saved. If the user asks Claude to delete or fix something after
a report, Claude can still find a way the guard doesn't recognise, and the user can switch the guard
off. The docs say the guard is "a safety net, not a guarantee", but nowhere say plainly where
Cinemetric's promise ends, or what the user can do to protect themselves.

The goal is to be honest about that boundary without alarming people, and without describing ways
around the guard.

## What Changes

- SECURITY.md, under "What the skills do not protect against", gains three points:
  - Cinemetric can't stop Claude changing the server if the user asks it to. Changes the user asks
    Claude for are ordinary Claude Code work, not something Cinemetric controls.
  - Claude Code's own permission prompts are the last check: read commands that mention the server
    before approving them. With commands approved automatically, the guard is the only check left.
  - Two Plex settings that limit the damage: switching off "Allow media deletion" (Settings,
    Library) makes Plex refuse to delete media files for any app, Claude included; and the
    "Backup database every three days" task (Settings, Scheduled Tasks) keeps copies of the library
    details and watch history (not the media files).
- The README's "AI can make mistakes" caution gains one sentence on the same boundary, linking to
  SECURITY.md.
- The website's "AI can make mistakes" notice gains the same sentence. The "Look, don't touch"
  section is left as it is.
- None of the wording lists ways to get around the guard.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `security`: adds a requirement that the user-facing docs say where Cinemetric's promise ends and
  what the user can do about it.
- `website`: the "Matches the project's promises" requirement's caution now also covers changes the
  user asks Claude to make.

## Impact

- Docs: `SECURITY.md`, `README.md`, `website/index.html`.
- Tests: `tests/test_mods.py` or the website test gains a check for the new sentence.
- No code changes, no version bump (nothing in the plugin changes).
