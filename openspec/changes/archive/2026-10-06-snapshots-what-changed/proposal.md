## Why

Every Cinemetric report describes the server as it is right now, so the user can't easily see what
changed since last time: which titles arrived or disappeared, which files went missing, who was given
or lost access, or whether Plex updated itself. "Snapshots and what changed" is the next item on the
README Roadmap, and `openspec/ideas.md` already allows saving small summaries on the user's computer.

## What Changes

- **New `changes` skill.** Its script runs `library_report.py`, `server_health.py` and
  `users_and_shares.py` (the same way the dashboard does, so it never contacts Plex itself), saves a
  snapshot, and reports what changed since the most recent snapshot from an earlier day:
  - titles added and removed per library (movies, shows, albums), and episodes added or removed per
    show,
  - files that became unavailable, and ones that came back,
  - libraries added, removed or renamed, and item count and size changes,
  - Plex version changes, update availability and remote access changes,
  - people added or removed, invites accepted, and changes to someone's libraries or download access.
  `--since DAYS` compares against an older snapshot (for "what changed this week").
  `list` shows which snapshots exist. `forget` deletes every saved snapshot.
- **Snapshots** are small private JSON files in the data folder, one per server per day (a later run
  the same day updates that day's file). Snapshots older than 90 days are deleted when a new one is
  saved. Each file carries a format number; a file that is unreadable, too large or from an unknown
  format is skipped, never trusted. Snapshots hold titles and the details about people the reports
  already show, and nothing more (no emails, account ids or play history).
- **Each report owns its part.** `library_report.py`, `server_health.py` and `users_and_shares.py`
  each:
  - read the newest earlier-day snapshot for this server (they never write one) and add a
    `since_snapshot` section for their own area, so plain report runs show what changed too;
  - accept `--since DAYS` to compare against an older snapshot;
  - accept `--snapshot-items`, which adds a `snapshot` block (their part of a new snapshot) to the
    JSON. Normal runs don't print it.

  So the comparison for each area lives in exactly one script. The changes script only gathers the
  three `since_snapshot` sections and saves the three `snapshot` blocks.
- **The dashboard** runs its reports with `--snapshot-items`, hands the results to the changes script
  to save (`changes.py save`, which reads from stdin and contacts nothing), and shows a
  "Since <date>" section built from the reports' `since_snapshot` sections. Nothing is fetched twice.
- Facts only: nothing suggests deleting, re-adding or unsharing anything.
- **Defaults to confirm before implementing:** snapshots are always on (no opt-in step); one per day
  is kept for 90 days.
- Weekly digest: **not** in this change (scheduled runs had limits before; see ideas.md).
- README Roadmap: the snapshots item becomes a weekly digest item. `openspec/ideas.md`: the snapshots
  note shrinks to the digest part. Website: a `changes` feature with a demo panel. SECURITY.md
  mentions snapshot files.
- Version bump to 0.18.0.

## Capabilities

### New Capabilities

- `changes`: the new skill's script: what it runs, the snapshot file format, where snapshots are
  stored and how they're pruned, the report it prints, `--since`, `list`, `forget`, and the
  no-network `save` mode the dashboard uses.

### Modified Capabilities

- `library-report`: `--snapshot-items`, `--since`, and `since_snapshot` (titles, episodes,
  unavailable files, library counts and sizes).
- `server-health`: `--snapshot-items`, `--since`, and `since_snapshot` (version, update, remote
  access).
- `users-and-shares`: `--snapshot-items`, `--since`, and `since_snapshot` (people and their access).
- `dashboard`: runs its reports with `--snapshot-items`, saves a snapshot through the changes script,
  and shows a "Since <date>" section.
- `conventions`: the data folder holds snapshots as well as dashboard files; the snapshot helper joins
  the list of copied helpers that must be kept in step.
- `security`: snapshot files and their folder are private; snapshots read from disk are treated as
  data (size limit, format check, text cleaned again); the changes script contacts nothing itself.
- `testing`: tests must cover snapshots (saving, pruning, choosing, bad files) and each report's
  `since_snapshot`.
- `website`: shows the `changes` skill.

## Impact

- New: `plugins/cinemetric/skills/changes/SKILL.md` and `scripts/changes.py`.
- Changed scripts and `SKILL.md`s: `library-report`, `server-health`, `users-and-shares`, `dashboard`.
- A small "find and read a snapshot" helper is copied into the three report scripts and the changes
  script (per the "Self-contained scripts" rule) and must be kept in step.
- New files on the user's computer: `<data folder>/snapshots/<server id>/<YYYY-MM-DD>.json`.
- Tests: new `tests/test_changes.py`; additions to the library-report, server-health,
  users-and-shares and dashboard tests.
- README, `openspec/ideas.md`, `website/index.html`, SECURITY.md.
- Version in all scripts, `plugin.json` and `marketplace.json`.
- No new network destinations, Plex paths or Tautulli commands.
