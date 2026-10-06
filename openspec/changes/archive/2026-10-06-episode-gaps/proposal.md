## Why

"Am I missing any episodes?" is a common question for anyone who keeps TV shows on Plex, and no
Cinemetric skill answers it. Plex shows how many episodes a season has on disk, but not that S02E03 is
missing between E02 and E04. This is the `tv-completeness` idea from the Roadmap and
`openspec/ideas.md`, renamed `episode-gaps` so the name says what it can honestly find.

## What Changes

- A new read-only skill, `episode-gaps`, with one script, `episode_gaps.py`. For each TV library it
  reads every episode once and lists, per show:
  - **gaps inside a season**: episode numbers missing between the lowest and highest episode on the
    server (E01, E02 and E04 are there, so E03 is probably missing);
  - **seasons that start late**: the first episode on the server is, say, E05, so E01 to E04 are
    probably missing (unless the show numbers its episodes straight on from the previous season);
  - **missing seasons**: seasons 1 and 3 are there but season 2 isn't;
  - **episodes Plex can't find**: the episode is listed in Plex but its file is gone, so it is
    effectively missing too.
- **Only what's on the server.** The script never asks an online service how many episodes a season
  should have. So it can't see episodes missing after the last one on the server, or whole seasons
  missing after the last season. The report and `SKILL.md` say this plainly every time.
- **No false gaps from the usual suspects.** Specials (season 0) are never checked for gaps. A file
  that holds several episodes (`S01E01-E02`) fills every number it covers. Shows numbered straight
  on across seasons (season 2 starting at E13) aren't reported as starting late. Episodes with no
  season or episode number are counted, not guessed at.
- **Facts, not advice.** The report lists numbers. It never suggests downloading, replacing or
  deleting anything.
- Options: `--library NAME` (repeatable), `--show TEXT` (shows whose title contains the text),
  `--limit N` (shows listed per library), `--check`.
- **Dashboard:** a new Episode gaps section built from the `episode-gaps` report: the totals, each TV
  library's counts, the shows with the most gaps, and the note about what can't be seen. Like the
  Unwatched section, it doesn't change the page's overall status.
- **`library-report` is unchanged** apart from one `SKILL.md` line pointing to `episode-gaps` when
  someone asks about missing episodes.
- README: new row in the Skills table; `tv-completeness` comes out of the Roadmap and
  `openspec/ideas.md`. Website: a new skill with a demo panel.
- Version bump to 0.19.0.

## Capabilities

### New Capabilities

- `episode-gaps`: what the script requests, which libraries and episodes are checked, how gaps, late
  starts, missing seasons and unavailable episodes are found, what isn't reported (specials,
  multi-episode files, numbering that carries on across seasons), what the report contains, and
  options.

### Modified Capabilities

- `dashboard`: "Built from the other report scripts" adds `episode_gaps.py`; a new "Episode gaps
  section" requirement.
- `conventions`: "Connection check" adds the new script.
- `security`: "Only known destinations" gets a scenario saying `episode-gaps` contacts only the
  configured Plex server.
- `testing`: "Tests check the specs" adds `episode-gaps` coverage and a false-gap scenario.
- `website`: "Shows every skill" adds `episode-gaps` (ten skills).

## Impact

- New: `plugins/cinemetric/skills/episode-gaps/SKILL.md` and
  `plugins/cinemetric/skills/episode-gaps/scripts/episode_gaps.py` (with copies of the shared helpers:
  `load_config`, `validate_url`, `PlexClient` and `clean`).
- New: `tests/test_episode_gaps.py` and made-up fixtures in `tests/fixtures/episode-gaps/`. The
  cross-script security tests gain the new script.
- Changed: `dashboard.py`, the dashboard `SKILL.md` and dashboard tests; the `library-report`
  `SKILL.md` (one pointer line, no script change).
- `README.md`, `openspec/ideas.md`, `website/index.html` (and the dashboard screenshot, retaken to
  show the new section).
- `VERSION` in all ten scripts, `plugin.json` and `marketplace.json`.
- No new network destinations: only paths other scripts already use on the configured Plex server.
