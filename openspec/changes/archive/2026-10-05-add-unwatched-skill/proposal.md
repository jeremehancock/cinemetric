## Why

"Where is my storage going, and is anyone actually watching it?" is one of the most common questions a
Plex server owner has, and no Cinemetric skill answers it today. `library-report` knows what's on disk
and `watch-activity` knows what's been played, but nothing joins the two. `unwatched` is first in the
suggested order in `openspec/ideas.md`, now that the server-health and watch-activity additions are
done.

## What Changes

- A new read-only skill, `unwatched`, with one script, `unwatched.py`. For each movie and TV library it
  lists titles that were added more than 6 months ago and have had no finished play by anyone in the
  last 6 months, sorted by size, largest first. Each title shows when it was added, how much space it
  uses, and when it was last finished (or that no finished play was found at all). Per library and
  overall it gives the count, the space used, and what share of the library that is.
- **Only finished plays count.** A title someone started but didn't finish is still listed. This
  matches what Plex's own watch history records, and with Tautulli only plays marked watched count.
- **Who "nobody" means.** Plays come from every account on the server, not just the owner's: from
  Tautulli when it's set up, otherwise from the server's own watch history. The report says which
  source it used, and how far back that history goes, so Claude can say how sure the "nobody" is.
- **Facts, not advice.** The report and `SKILL.md` describe the library ("40 movies added over a year
  ago haven't been finished by anyone; together they use 1.8 TB") and never suggest deleting anything.
- Options: `--months N` (default 6), `--library NAME`, `--limit N` (titles listed per library),
  `--source auto|tautulli|plex`, `--check`.
- **Dashboard:** a new Unwatched section built from the `unwatched` report: per library count and
  space, the overall total, and the largest unwatched titles. It doesn't change the page's overall
  status.
- **`library-report` is not changed** to include the same list. It stays fast and doesn't need
  Tautulli or watch history. Its `SKILL.md` points to `unwatched` when someone asks which titles
  nobody watches, and ends a full report by offering to show unwatched titles.
- README: new row in the Skills table; the `unwatched` idea comes out of the Roadmap and
  `openspec/ideas.md`. Website: a new skill with a demo panel.
- Version bump to 0.13.0.

## Capabilities

### New Capabilities

- `unwatched`: what the script requests, which plays count, how titles are chosen and sized, what the
  report contains, partial results, and options.

### Modified Capabilities

- `dashboard`: "Built from the other report scripts" adds `unwatched.py`; a new "Unwatched section"
  requirement.
- `conventions`: "Connection check" adds the new script.
- `security`: "Only known destinations" adds `unwatched` to the scripts that contact only Plex and
  Tautulli.
- `testing`: "Tests check the specs" adds `unwatched` coverage.
- `website`: "Shows every skill" adds `unwatched` (seven skills).

## Impact

- New: `plugins/cinemetric/skills/unwatched/SKILL.md` and
  `plugins/cinemetric/skills/unwatched/scripts/unwatched.py` (with copies of the shared helpers:
  `load_config`, `validate_url`, `PlexClient`, the Tautulli client and `clean`).
- New: `tests/test_unwatched.py` and made-up fixtures in `tests/fixtures/unwatched/`. The
  cross-script security tests gain the new script. Dashboard tests gain the new section.
- Changed: `dashboard.py` and the dashboard `SKILL.md`; the `library-report` `SKILL.md` (a pointer
  line and a closing offer, no script change).
- `README.md`, `openspec/ideas.md`, `website/index.html` (and the dashboard screenshot, if it's
  retaken).
- `VERSION` in all seven scripts, `plugin.json` and `marketplace.json`.
- No new network destinations. No change to the other report scripts' behavior.
