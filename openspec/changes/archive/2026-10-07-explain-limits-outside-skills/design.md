## Context

Docs-only change. The current docs say the guard is "a safety net, not a guarantee" and that the
skills are read-only, but don't say plainly what happens when the user asks Claude to change their
server, or what the user can do about it.

## Goals / Non-Goals

**Goals:**
- Say where Cinemetric's promise ends, once, in each place a user reads about safety.
- Give practical steps: read Claude Code's permission prompts, and two Plex settings.

**Non-Goals:**
- New guard rules or skill instructions. The skills already tell Claude never to offer changes.
- Listing ways around the guard.

## Decisions

### Where the wording goes
- **SECURITY.md** carries the full version, since it's where people look for limits.
- **README** and **website** get one sentence each, inside the existing "AI can make mistakes"
  caution. That caution is already the "be careful before you act" spot, so the sentence reads as
  practical advice rather than a new warning. The website's "Look, don't touch" section is left as
  it is: it describes what Cinemetric itself does, which stays true.

*Alternative considered:* a new card in "Look, don't touch". Rejected: it would sit among promises
and read as a warning, and the cards are kept similar lengths.

### Which Plex settings
- **"Allow media deletion"** (Settings, Library): when off, Plex refuses to delete media files for any
  app, so it's a real lock on Plex's side for the most damaging change. It doesn't cover other
  changes, which the wording says.
- **"Backup database every three days"** (Settings, Scheduled Tasks): keeps rotating copies of the
  main database (watch history and library details), not media files.

*Alternative considered:* "Empty trash automatically after every scan". Rejected: it only keeps
Plex's entries for missing files, and doesn't protect files Plex deletes.

### Tone
Short and factual, in the same voice as "safety net, not a lock". No "at your own risk" phrasing;
the MIT license already covers warranty.

## Risks / Trade-offs

- [Plex renames a setting] → The wording names the menu as well, so it's still findable; worth
  checking at each release that touches SECURITY.md.
