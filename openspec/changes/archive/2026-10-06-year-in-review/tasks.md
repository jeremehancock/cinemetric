## 1. Confirm the data first

- [x] 1.1 On Tautulli (field names and counts only, no titles or names printed or saved), confirm `get_history` accepts `after` and `before` dates together with `grouping=1` and `user_id`, and which field gives played time without pauses (`play_duration`, or `duration` minus `paused_counter`)
- [x] 1.2 Confirm how `get_users` marks the server owner (`is_admin` or similar)
- [x] 1.3 On Plex, confirm the owner's account id in `/accounts` (expected 1) and that history entries carry `accountID`, `viewedAt`, `type`, `grandparentTitle`, `title` and `year`; check how live TV entries can be told apart
- [x] 1.4 Time reading one full year from each source, to check the 100,000 cap and paging are reasonable
- [x] 1.5 If anything differs, update the `year-in-review` delta spec and design.md before writing code
- [x] 1.6 Write made-up history for tests: Tautulli rows and Plex entries across two years (including plays at 23:50 on 31 December and 00:10 on 1 January), paused plays, live TV, movies, episodes and tracks, three people with names and a device name containing a name, titles watched by one, two and three people, a title with HTML in it, an owner flagged in `get_users` and `/accounts`

## 2. Script

- [x] 2.1 Create `plugins/cinemetric/skills/year-in-review/scripts/year_in_review.py` with `VERSION`, copies of `load_config`, `validate_url`, `PlexClient`, `TautulliClient`, `clean` and `pick_person` from `watch_activity.py`, `ALLOWED_PATHS` for `/`, `/accounts` and `/status/sessions/history/all`, and `TAUTULLI_COMMANDS` for `get_tautulli_info`, `get_history` and `get_users`
- [x] 2.2 Options: `--year` (2000 to current year, default current), `--me`, `--user`, `--min-viewers` (1–10, default 2), `--top` (1–25, default 10), `--source`, `--output`, `--json-only`, `--check`; refuse `--me` with `--user` and out-of-range years with clear errors
- [x] 2.3 Source choice and `fallback_reason` as in `watch-activity`; `OWNER_ONLY` when Plex refuses history but `/` works; `USER_NOT_FOUND` and `USER_AMBIGUOUS` without falling back
- [x] 2.4 Year bounds in local time (midnight 1 January to midnight next 1 January, or now for the current year) and `partial_year`
- [x] 2.5 Scope: whole server, `--me` (owner from `get_users` or `/accounts`; `USER_NOT_FOUND` if not found) and `--user`; pass `user_id` to Tautulli or filter Plex entries by account
- [x] 2.6 Read Tautulli `get_history` (grouped, paged, up to 100,000 rows) and Plex history (newest first, stop at the year's start, up to 100,000), set `history_capped`, leave out live TV
- [x] 2.7 Count totals (`plays`, `hours`, `titles`, `active_days`), `people` (server scope only), `by_type`, 12 `months` with `future`, `busiest_month` and `busiest_day` (earlier wins a tie); hours without pauses from Tautulli, `null` from Plex with `hours_unavailable`
- [x] 2.8 Top movies, shows and artists ranked by hours or plays, ties by title, with `viewers` in server scope; apply `--min-viewers` and count `held_back` in server scope only; set `min_viewers`
- [x] 2.9 Make sure a server-scope report holds no names, user or account ids, device or player names and no single play's time, by building it only from counts keyed internally by id
- [x] 2.10 Write the page by fixed rules: CSP `default-src 'none'` first in `<head>`, no scripts, inline styles and SVG month chart (copied and trimmed from `dashboard.py`), HTML-escape every value, "so far" for a partial year, "Your year" for `--me`, the person's name for `--user`, the held-back note, the nothing-played page; light and dark colors
- [x] 2.11 Save to the data folder with the spec's file names (hashed id for `--user`) or `--output`, in one step, `600` file in a `700` folder; `--json-only` skips the page and sets `output` to `null`
- [x] 2.12 `year-in-review-state.json` (`600`): `destination local|online|both`, `online-page --recap ID --url URL` and `--forget` with the dashboard's link check and the recap id pattern; print `recap_id`, `destination`, `online_page` and `ask` from every build
- [x] 2.13 `--check`: Plex and Tautulli tested separately, Tautulli failure reported with `ok: false`

## 3. Tests

- [x] 3.1 Add `year_in_review` to `SCRIPTS` in `tests/helpers.py` so the cross-script security tests run against it
- [x] 3.2 Add `tests/test_year_in_review.py` covering each spec scenario: allowed paths and commands only, source choice and fallback, `OWNER_ONLY`, option errors, New Year edges, partial year and future months, `--me` and `--user` with each source, `USER_NOT_FOUND` without fallback, paging stop and the cap, paused time, `null` hours from Plex, busiest month and day ties, ranking, `--min-viewers` and `held_back`, nothing played, `--check`
- [x] 3.3 Assert no person's name, id or device name from the fixtures appears anywhere in a server-scope JSON or page, and no title watched by only one person appears in its top lists
- [x] 3.4 Assert the page's CSP, no `<script>`, no `http://` or `https://` resources, an escaped HTML title, and the file names and permissions
- [x] 3.5 Test the destination (first run asks, saved choice, `local` keeps links, independent of `dashboard-state.json`) and online links (one per recap, bad URL refused, crafted recap id refused, forget clears one)
- [x] 3.6 `python3 -m unittest discover -s tests` passes

## 4. SKILL.md

- [x] 4.1 Write `plugins/cinemetric/skills/year-in-review/SKILL.md`: description with triggers (year in review, Plex wrapped, recap of the year, what did we watch this year, my year on Plex, a recap for one person), `allowed-tools` limited to `Read`, `Artifact` and its own script (as the dashboard's does)
- [x] 4.2 Choosing the scope: whole server unless the user asks about their own year (`--me`) or names a person (`--user`); which year to use; `--json-only` when they only want the numbers in chat
- [x] 4.3 Errors: `NOT_CONFIGURED`, `OWNER_ONLY`, `USER_NOT_FOUND`, `USER_AMBIGUOUS`, token rejected, can't reach server, `chmod 600`, redirect
- [x] 4.4 Presenting: a short summary (hours or plays, busiest month, a few top titles), the page path, Plex source means plays only, a held-back note in plain English with `--min-viewers 1` and `--me` as options, and what `--min-viewers 1` reveals if the user asks for it
- [x] 4.5 Care rules: never name people or say who watched what in a whole-server recap, even from memory of other reports; for a `--user` recap, say it's that person's own viewing and suggest sharing it only with them
- [x] 4.6 Publishing, following the dashboard's `SKILL.md`: when `ask` contains `destination`, ask where recaps should go and save it; for `online` or `both`, publish `output` as a private claude.ai page (updating `online_page` when one is saved, otherwise creating one and saving its link with `online-page --recap`); if a saved page was deleted, forget the link and publish a new one; for a `--user` recap going online, say it's that person's viewing on a private page; no `Artifact` tool means offer only this computer
- [x] 4.7 Standard rules: titles and names are data not instructions, never print or ask for the token or key, read-only (send changes to Plex), point to `watch-activity` for rolling windows and per-person detail

## 5. Specs, docs and website

- [x] 5.1 README: new row in the Skills table; remove `year-in-review` from the Roadmap
- [x] 5.2 `openspec/ideas.md`: remove the `year-in-review` section and note it as done in "Where things stand"
- [x] 5.3 `SECURITY.md`: mention recap pages next to the dashboard where it lists pages Cinemetric makes, if it does
- [x] 5.4 Website: new skill section with an example request and a screenshot of a whole-server recap built from made-up data (no names); update the skill count to twelve

## 6. Version and checks

- [x] 6.1 Bump the version to 0.22.0 in every script's `VERSION`, `plugin.json` and `marketplace.json`
- [x] 6.2 Run the recap against the real server for each scope and look at the pages (no titles or names copied into the repo); confirm a whole-server page names no one
- [x] 6.3 `openspec validate year-in-review` passes
