## Why

Every Cinemetric skill so far is a tool for running the server. But the person who runs a Plex server
is usually also someone who watches it, and "what should I watch tonight?" is a question they ask far
more often than "is my server healthy?". A conversational way to pick something from your own library
is fun, shows off what Claude adds on top of the raw data, and makes a good demo for the website.

## What Changes

- A new read-only skill, `what-to-watch`, with one script, `what_to_watch.py`. It reads the movie and
  TV libraries and returns a shortlist of titles that match what was asked for:
  - **Filters:** movie or show, library, genre, length (shortest and longest runtime), decade or year
    range, minimum rating, content rating (such as PG-13), and unwatched only.
  - **Shuffled by default,** so asking twice gives different suggestions. It can also sort by rating,
    newest added or release year.
  - Each title comes with its year, runtime (or episode and season count for shows), genres, ratings,
    content rating, a short summary, and whether it's been watched.
  - The report also says how many titles matched in total and lists the genres the libraries actually
    have, so Claude can turn "something scary" into the right genre name.
- **Continue watching:** `--continue` lists what's in progress and the next episode of shows already
  started, with how far along each one is.
- **Watched means the signed-in account.** Plex keeps watched status per person, and Cinemetric is
  signed in as the server owner, so "unwatched" means unwatched by that account. That's the right
  meaning for picking something for yourself (unlike `unwatched`, which looks at everyone).
  `SKILL.md` explains this if someone else in the household asks.
- **Claude picks, briefly.** `SKILL.md` tells Claude to suggest 3 to 5 titles with a one-line reason
  each, rather than dumping the whole list, and to offer more or a different mood.
- **Only what's on the server.** No suggestions of titles to download or find elsewhere, and no new
  network destinations.
- Options: `--type movie|show`, `--library NAME`, `--genre NAME` (repeatable), `--min-minutes`,
  `--max-minutes`, `--decade` or `--year-from`/`--year-to`, `--min-rating`, `--content-rating`
  (repeatable), `--unwatched`, `--continue`, `--sort random|rating|added|year`, `--limit N`,
  `--check`.
- Not on the dashboard: the dashboard is about the server, and this is about tonight.
- README: new row in the Skills table and an example question; `what-to-watch` comes out of the
  Roadmap and `openspec/ideas.md`. Website: a new skill with a demo panel (eight skills).
- Version bump to 0.15.0.

## Capabilities

### New Capabilities

- `what-to-watch`: what the script requests, how filters and "watched" work, continue watching, what
  the report contains, and options.

### Modified Capabilities

- `conventions`: "Connection check" adds the new script.
- `security`: "Only known destinations" adds `what-to-watch` to the scripts that contact only Plex.
- `testing`: "Tests check the specs" adds `what-to-watch` coverage.
- `website`: "Shows every skill" adds `what-to-watch` (eight skills).

## Impact

- New: `plugins/cinemetric/skills/what-to-watch/SKILL.md` and
  `plugins/cinemetric/skills/what-to-watch/scripts/what_to_watch.py` (with copies of the shared
  helpers: `load_config`, `validate_url`, `PlexClient` and `clean`).
- New: `tests/test_what_to_watch.py` and made-up fixtures in `tests/fixtures/what-to-watch/`. The
  cross-script security tests gain the new script.
- `README.md`, `openspec/ideas.md`, `website/index.html`.
- `VERSION` in all eight scripts, `plugin.json` and `marketplace.json`.
- No new network destinations, no Tautulli use, and no change to the other skills' behavior.
