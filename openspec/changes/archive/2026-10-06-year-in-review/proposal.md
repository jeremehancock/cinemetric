## Why

Server owners like looking back on a year of watching: what got played most, how many hours went
into it, and which months were busiest. Cinemetric can already answer pieces of this (`watch-activity`
covers up to 3650 days), but only as a rolling window and a stats report, not as a recap of one
calendar year that someone would want to keep or show to the household. This is the `year-in-review`
idea from the Roadmap and `openspec/ideas.md`.

A recap reads differently from a stats report, and it is more likely to be shared. A list that says
"your top title was X" is harmless when it's about the whole household, and revealing when only one
person watched X. So this change treats other people's viewing with more care than `watch-activity`
does, by design rather than by an optional flag.

## What Changes

- A new read-only skill, `year-in-review`, with one script, `year_in_review.py`, that reads one
  calendar year of watch history and writes a recap page by fixed rules (no AI, no scripts on the
  page, nothing loaded from outside), like the dashboard. The page and a JSON summary cover:
  - **total hours watched** (with Tautulli) and total plays, titles and days with something played;
  - **busiest months**: plays and hours for each month, with the busiest one called out, plus the
    single busiest day;
  - **top titles**: movies, TV shows and music artists, by hours with Tautulli and by plays with
    Plex's own history;
  - what share went to movies, TV and music.
- **Calendar year only.** `--year YYYY` picks the year; the default is the current year, labelled
  "so far" while the year isn't over. No arbitrary date ranges in this version.
- **Three kinds of recap, and care with other people's viewing in each:**
  - **Whole server** (the default): everyone's viewing combined, with **no person's name anywhere**
    on the page or in the JSON, no "most active people" ranking, no per-person breakdown, and no
    individual plays or play times. It says only how many people watched something. **A title
    appears in a top list only when at least two different people played it** (`--min-viewers N`
    changes this, 1 to 10), so the list shows what the household shared rather than what one person
    watched alone. The page says how many titles were left out for this reason.
  - **My year** (`--me`): only the signed-in account's own viewing. Nobody else's plays are read
    into it.
  - **One person's year** (`--user NAME`): only that person's viewing, meant as a recap to give to
    them. Its `SKILL.md` has Claude remind the owner it's that person's own viewing, and say so when
    the saved destination means it's also going online as a private page.
- **Saved and published like the dashboard.** The first time, Claude asks where recaps should go:
  this computer, online as a private claude.ai page, or both. The answer is remembered for every
  recap. Each recap (one per year and kind) has its own local file in Cinemetric's data folder
  (`600`) and its own saved claude.ai link, so running the same recap again updates the same file and
  the same online page in place.
- History comes from Tautulli when it's set up (watch time per play) and from Plex's own history
  otherwise (plays only, so hours are left out and top lists rank by plays). Same source choice,
  owner-only rule and person matching as `watch-activity`.
- Not in this version: favorite genres (needs extra requests per title), a comparison with the
  previous year, and a "most active people" ranking.
- README: new row in the Skills table; `year-in-review` comes out of the Roadmap and
  `openspec/ideas.md`. Website: a new skill with a demo panel (twelve skills).
- Version bump to 0.22.0.

## Capabilities

### New Capabilities

- `year-in-review`: what the script requests from Plex and Tautulli, which year and whose plays are
  counted, how hours, months, days and top titles are worked out, the privacy rules for each kind of
  recap, what the JSON and the page contain, where the page is saved, and options.

### Modified Capabilities

- `conventions`: "Skill shape" names `year-in-review` as a second skill whose page is written by
  rules in the script; "Connection check" adds the new script.
- `security`: "Only known destinations" gets a scenario for `year-in-review`; "Private files" adds
  recap pages and their state file; a new requirement, "Recap pages go online only by choice",
  mirrors the dashboard's rule: published only when the user chose `online` or `both`, only as
  private pages, and never by the script itself.
- `testing`: "Tests check the specs" adds `year-in-review` coverage, including that no name appears
  in a whole-server recap and that titles one person watched alone stay out of its top lists.
- `website`: "Shows every skill" adds `year-in-review` (twelve skills), shown with a screenshot of the
  page like the dashboard.

## Impact

- New: `plugins/cinemetric/skills/year-in-review/SKILL.md` and
  `plugins/cinemetric/skills/year-in-review/scripts/year_in_review.py` (with copies of the shared
  helpers: `load_config`, `validate_url`, `PlexClient`, `TautulliClient`, `clean`, and the person
  matching from `watch_activity.py`).
- New: `tests/test_year_in_review.py` with made-up history. The cross-script security tests gain the
  new script.
- `README.md`, `SECURITY.md` (if it names the dashboard as the only page), `openspec/ideas.md`,
  `website/index.html` and a screenshot of a recap built from made-up data.
- `VERSION` in all twelve scripts, `plugin.json` and `marketplace.json`.
- Plex paths and Tautulli commands are a subset of what `watch-activity` already uses. No new
  destinations, nothing written except the pages and `year-in-review-state.json` (the saved
  destination and each recap's online link).
