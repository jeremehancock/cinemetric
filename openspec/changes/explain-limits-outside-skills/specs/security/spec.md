## ADDED Requirements

### Requirement: Honest about what Cinemetric can't control
`SECURITY.md`, under "What the skills do not protect against", SHALL say in plain words:
- that Cinemetric can't stop Claude from changing the user's server if the user asks it to: the
  skills only read and the read-only guard catches common ways Claude might change things on its
  own, but changes the user asks Claude for are ordinary Claude Code work;
- that Claude Code's own permission prompts are the last check, so the user should read commands
  that mention their server before approving them, and that with commands approved automatically the
  guard is the only check left;
- two Plex settings that limit the damage: switching off "Allow media deletion" (Settings, Library),
  which makes Plex refuse to delete media files for any app, and the "Backup database every three
  days" scheduled task, which keeps copies of the library details and watch history but not the
  media files.

The README's "AI can make mistakes" caution SHALL say the same boundary in one sentence, with a link
to `SECURITY.md`. None of this wording SHALL describe ways to get around the guard, and it SHALL stay
factual rather than alarming.

#### Scenario: Reading SECURITY.md
- **WHEN** a user reads "What the skills do not protect against"
- **THEN** they learn that changes they ask Claude for aren't something Cinemetric controls, that
  Claude Code's permission prompts are the last check, and which two Plex settings limit the damage

#### Scenario: Reading the README caution
- **WHEN** a user reads "AI can make mistakes" in the README
- **THEN** they see one sentence on asking Claude to change things, with a link to `SECURITY.md`

#### Scenario: No ways around the guard
- **WHEN** someone reads the new wording
- **THEN** it doesn't describe how a command or program could get past the guard
