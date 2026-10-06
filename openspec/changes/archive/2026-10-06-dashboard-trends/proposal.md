## Why

The dashboard's "Since" section says what changed since one earlier day, but not how things have been
moving over weeks: whether the library is growing steadily, which library is growing fastest, or
whether the number of people with access has crept up. The saved snapshots (one per server per day,
kept 90 days) already hold per-library counts and sizes and the list of people with access for each
day, so charts over time need no new data from Plex. "Trends on the dashboard" is on the README
Roadmap and in `openspec/ideas.md`.

## What Changes

- **New `changes.py trends` mode.** Reads this server's saved snapshots (at most the last 90 days) and
  prints one point per snapshot day: total library size, and per library its size and its counts
  (movies, shows, episodes, albums, tracks, photos); and for sharing, the number of people with
  access (counted the way the Sharing section counts them), split by type (Plex Home, managed,
  friends), and pending invites. Counts only: no titles and no
  people's names. It reads files only and contacts nothing, like `save`, `list` and `forget`.
- **New "Trends" section on the dashboard**, after the "Since" section, built from `changes.py trends`
  after the build saves today's snapshot:
  - **Storage over time:** total library size per snapshot day.
  - **Titles per library:** one small chart per library showing its main count (movies for a movie
    library, episodes for TV, albums for music, photos for photos), with the first and latest value
    and the change.
  - **People with access:** people who can reach the server per snapshot day, with pending invites
    in the tooltip.

  Charts are inline SVG like the existing ones (no scripts, nothing loaded from outside), with a wide
  and a narrow version. Days are spaced by date, so a week with no snapshots shows as a gap in time
  rather than being squeezed out. With fewer than two snapshot days, the section says in one line
  that trends appear once snapshots from two different days exist.
- Facts only, like the rest of the dashboard: trends don't add anything to "Needs a look" or change
  the overall status. They contain no person's name, so hiding names doesn't change them.
- **`changes` skill:** can use `trends` to answer "how has my library grown over the last few
  months?" or "has the number of people I share with changed?".
- README Roadmap: the trends item is removed (finished work is described by the specs).
  `openspec/ideas.md`: the trends note is removed, keeping the weekly digest note.
- Version bump to 0.21.0.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `changes`: adds the `trends` mode (what it reads, what it prints, how it handles missing areas,
  renamed and removed libraries, and bad files).
- `dashboard`: runs `changes.py trends` after saving the snapshot and shows a Trends section.
- `security`: `changes.py trends` opens no network connection.
- `testing`: tests must cover `trends` and the dashboard's Trends section.

## Impact

- `plugins/cinemetric/skills/changes/scripts/changes.py` and its `SKILL.md`.
- `plugins/cinemetric/skills/dashboard/scripts/dashboard.py` and its `SKILL.md`.
- Tests: additions to `tests/test_changes.py` and `tests/test_dashboard.py`.
- README Roadmap, `openspec/ideas.md`.
- Version in all scripts, `plugin.json` and `marketplace.json`.
- No new network destinations, Plex paths or Tautulli commands. No change to the snapshot file format.
- Cost: the dashboard build reads up to 90 snapshot files (about 0.1 MB each on a medium library) in
  addition to what it does today.
