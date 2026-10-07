# year-in-review Specification

## Purpose

A read-only recap of one calendar year of watching on a Plex server, written as a rule-based HTML
page plus a JSON summary: hours and plays, busiest months and day, the movies/TV/music split and the
most watched titles. A whole-server recap names no one and leaves off titles only one person watched;
a recap can also cover the owner's own viewing or one person's. History comes from Tautulli when it's
set up and from Plex's own history otherwise. Script: `skills/year-in-review/scripts/year_in_review.py`.
How Claude presents and publishes it is in the skill's `SKILL.md`.
## Requirements
### Requirement: Sources used
With Plex, the script SHALL request only `/`, `/accounts`, `/status/sessions/history/all` and
`/:/prefs`. `/:/prefs` SHALL be read only for the media deletion setting (see "Media deletion setting" in the conventions spec). When Plex isn't configured, the setting isn't read and
`media_deletion_allowed` is `null`. With
Tautulli, it SHALL run only `get_tautulli_info`, `get_history` and `get_users`. Source choice SHALL
work as in `watch-activity`: `--source auto` (the default) uses Tautulli if it's configured and falls
back to Plex otherwise, recording why in `fallback_reason`; `--source tautulli` fails with
`TAUTULLI_NOT_CONFIGURED` if it isn't set up and never falls back; `--source plex` uses Plex only.

#### Scenario: Building a recap from Tautulli
- **WHEN** the recap is built from Tautulli
- **THEN** only commands from that list are sent to Tautulli and no Plex path outside the list is
  requested

#### Scenario: Tautulli is down
- **WHEN** Tautulli is configured but can't be reached and `--source` is `auto`
- **THEN** the recap comes from Plex and `fallback_reason` says Tautulli failed and why

### Requirement: Owner-only history
If the Plex history request is refused (401 or 403) but the token still works for `/`, the script
SHALL fail with `OWNER_ONLY`.

#### Scenario: Connected to a shared server without Tautulli
- **WHEN** the history request returns 403 and `/` succeeds
- **THEN** the script stops with `error: OWNER_ONLY: ...`

### Requirement: Options
The script SHALL accept `--year YYYY` (from 2000 to the current year; default the current year),
`--me`, `--user NAME`, `--min-viewers N` (default 2, limited to 1–10), `--top N` (entries per top
list, default 10, limited to 1–25), `--source auto|tautulli|plex`, `--output PATH`, `--json-only` and
`--check`. A year outside the allowed range SHALL be refused with an error naming the range. `--me`
and `--user` together SHALL be refused with an error.

#### Scenario: A future year
- **WHEN** run with `--year 2031` in 2026
- **THEN** the script stops with an error saying the year must be from 2000 to 2026

#### Scenario: Both kinds of personal recap
- **WHEN** run with `--me --user alex-test`
- **THEN** the script stops with an error saying to choose one

### Requirement: The year
The recap SHALL cover plays that started from local midnight on 1 January of the chosen year up to,
but not including, local midnight on 1 January of the next year. For the current year it SHALL end
at the time the script runs, and `partial_year` SHALL be true; otherwise `partial_year` SHALL be
false. With Tautulli, live TV plays (marked `live`) SHALL be left out; Plex's history doesn't mark
live TV, so it can't be left out there.

#### Scenario: Plays around New Year
- **WHEN** the year is 2025 and history has plays that started at 23:50 on 31 December 2024, 00:10 on
  1 January 2025 and 23:50 on 31 December 2025
- **THEN** the last two are counted and the first is not

#### Scenario: The current year
- **WHEN** the script runs on 6 October 2026 without `--year`
- **THEN** `year` is 2026, `partial_year` is true, and plays up to now are counted

### Requirement: Whose plays are counted
Without `--me` or `--user`, `scope` SHALL be `server` and plays by every person SHALL be counted.

With `--me`, `scope` SHALL be `me` and only the server owner's plays SHALL be counted: with Tautulli,
the person `get_users` marks as the admin (`is_admin`); with Plex, account id 1, which Plex uses for
the owner. If the owner
can't be identified, the script SHALL fail with `USER_NOT_FOUND` saying so.

With `--user NAME`, `scope` SHALL be `user` and only that person's plays SHALL be counted. The person
SHALL be matched as in `watch-activity` ("Choosing one person"), with the same `USER_NOT_FOUND` and
`USER_AMBIGUOUS` errors, and `user` SHALL be their display name. With Tautulli, their `user_id`
SHALL be passed to every `get_history` request; with Plex, history entries SHALL be kept only when
their account matches.

`user` SHALL be `null` unless `scope` is `user`.

#### Scenario: My year with Tautulli
- **WHEN** run with `--me`, Tautulli is the source and the admin's user id is 1
- **THEN** every `get_history` request carries `user_id` 1 and `user` is `null`

#### Scenario: One person with Plex
- **WHEN** the source is Plex, run with `--user alex-test`, and the history holds plays by `alex-test`
  and another account
- **THEN** only `alex-test`'s plays are counted and `user` is `alex-test`

#### Scenario: Nobody matches
- **WHEN** run with `--user nobody` and no one matches
- **THEN** the script stops with `error: USER_NOT_FOUND: ...` and, with `--source auto`, does not fall
  back to Plex

### Requirement: Reading the history
With Tautulli, the script SHALL read `get_history` with grouping on (so a play paused and resumed
later counts once), in pages, up to 100,000 rows. Tautulli's own date filters SHALL only narrow the
request, to a window starting two days before the year and ending two days after it; each row SHALL
then be kept or dropped by its `started` time, so the year's edges don't depend on how Tautulli reads
dates. With Plex, it SHALL read
`/status/sessions/history/all` newest first, in pages, stopping at the first page whose oldest entry
is before the year, up to 100,000 entries. `history_capped` SHALL be true when the limit is reached.

#### Scenario: Plex history reaching back years
- **WHEN** the year is 2026 and Plex's history goes back to 2019
- **THEN** paging stops at the first page that reaches into 2025

#### Scenario: Very large history
- **WHEN** the year holds more than 100,000 plays
- **THEN** 100,000 are counted and `history_capped` is true

### Requirement: Hours and plays
With Tautulli, each play's hours SHALL be the time it was actually played, with paused time left out
(`play_duration`; on older Tautulli without it, `duration`).
With Plex, which records only finished plays and no watch time, every `hours` value in the report
SHALL be `null` and `hours_unavailable` SHALL say why; otherwise `hours_unavailable` SHALL be `null`.
`totals` SHALL hold `plays`, `hours`, `titles` (different movies, shows and artists played) and
`active_days` (days with at least one play). `by_type` SHALL give plays and hours for `movies`, `tv`
and `music`.

#### Scenario: A paused movie
- **WHEN** Tautulli reports a play of 2 hours 30 minutes from start to stop, 30 minutes of it paused
- **THEN** it adds 2 hours to the totals

#### Scenario: Plex as the source
- **WHEN** the recap comes from Plex
- **THEN** `totals.hours`, each month's `hours` and each top entry's `hours` are `null`, and
  `hours_unavailable` gives the reason

### Requirement: Months and busiest day
`months` SHALL have 12 entries, January first, each with `month` (1–12), `plays`, `hours` and
`future` (true for months that haven't started yet in a partial year). A play SHALL be placed in the
month and day it started, in local time. `busiest_month` SHALL be the month with the most hours
(Tautulli) or plays (Plex), and `busiest_day` the date (`YYYY-MM-DD`) with the most, each with its
plays and hours; on a tie the earlier one SHALL win. Both SHALL be `null` when nothing was played.

#### Scenario: A partial year
- **WHEN** the recap is for the current year in October
- **THEN** `months` has 12 entries and November and December have `future` true and zero plays

#### Scenario: Two months tie
- **WHEN** March and July have the same, highest number of hours
- **THEN** `busiest_month` is March

### Requirement: Top lists
`top_movies` (by title and year), `top_shows` (episodes counted toward their show) and `top_artists`
(tracks counted toward their artist) SHALL each hold up to `--top` entries, ranked by hours
(Tautulli) or plays (Plex), ties broken by title. Each entry SHALL have `title`, `plays` and `hours`;
in a `server` recap, also `viewers` (how many different people played it).

#### Scenario: Ranking by hours
- **WHEN** with Tautulli, show A has 40 plays and 12 hours and show B has 10 plays and 20 hours
- **THEN** show B is listed above show A

### Requirement: A whole-server recap names no one
When `scope` is `server`, neither the JSON nor the page SHALL contain any person's name, user name,
user id or account id, any device or player name, or the time of any single play. People SHALL appear
only as `people` (how many different people played something in the year). There SHALL be no list or
ranking of people.

#### Scenario: Names in the history
- **WHEN** the history holds plays by `alex-test` and `sam-test` on a device called "Alex's iPhone"
- **THEN** none of `alex-test`, `sam-test` or "Alex's iPhone" appears in the JSON or the page, and
  `people` is 2

### Requirement: Titles one person watched alone stay out of a whole-server recap
When `scope` is `server`, a title SHALL be listed in a top list only when at least `--min-viewers`
different people played it in the year. Titles left out this way SHALL still count in the totals,
months and `by_type`. Each top list SHALL report `held_back`: how many titles that would have ranked
within `--top` were left out for this reason. `--min-viewers` SHALL NOT apply when `scope` is `me` or
`user`. `min_viewers` in the report SHALL give the value used, or `null` when it didn't apply.

#### Scenario: A movie only one person watched
- **WHEN** `--min-viewers` is 2, one person played a movie 5 times and nobody else played it
- **THEN** it isn't in `top_movies`, `held_back` counts it, and its plays are in the totals

#### Scenario: A show two people watched
- **WHEN** `--min-viewers` is 2 and two different people played episodes of a show
- **THEN** the show can be listed in `top_shows` with `viewers` 2

#### Scenario: The owner's own recap
- **WHEN** run with `--me` and the owner played a movie that no one else did
- **THEN** it can be listed in `top_movies`, and `min_viewers` is `null`

### Requirement: Report contents
The script SHALL print JSON with `cinemetric_version`, `generated_at`, `year`, `partial_year`,
`scope`, `user`, `source`, `fallback_reason`, `history_capped`, `min_viewers`, `hours_unavailable`,
`totals`, `people` (`null` unless `scope` is `server`), `by_type`, `months`, `busiest_month`,
`busiest_day`, `top_movies`, `top_shows`, `top_artists`, `output` (the page's path, or `null`
with `--json-only`), `recap_id`, `destination` (`local`, `online`, `both`, or `null` if never
chosen), `online_page` (this recap's saved link, or `null`) and `ask` (containing `destination` when
none is saved). Each top list SHALL be an object with `entries` and `held_back` (`0` when
`--min-viewers` doesn't apply). Text from the server SHALL be cleaned as the security spec requires.

#### Scenario: Nothing played that year
- **WHEN** the history has no plays in the chosen year
- **THEN** the totals are zero, `busiest_month` and `busiest_day` are `null`, the top lists are empty,
  and a page is still written saying nothing was played

### Requirement: The recap page
Unless `--json-only` is given, the script SHALL write an HTML page by fixed rules (not AI), so the
same data always gives the same page. The page SHALL contain no scripts, load nothing from outside
itself, and start its `<head>` with a Content Security Policy of `default-src 'none'`, as the dashboard
page does. Every value from the server SHALL be HTML-escaped. The page SHALL show the year (with "so
far" when `partial_year` is true), the totals, a bar chart of the 12 months with the busiest one
marked, the busiest day, the movies/TV/music split and the top lists. A `server` recap SHALL say how
many titles were held back and why, when any were; a `user` recap SHALL be titled with the person's
display name; a `me` recap SHALL say "Your year" and name no one.

#### Scenario: A title with HTML in it
- **WHEN** a top title is `<b>Test</b>`
- **THEN** the page shows it as text, escaped

#### Scenario: Held back titles
- **WHEN** a `server` recap holds back 4 movies
- **THEN** the page says 4 movies watched by only one person were left out to keep each person's
  viewing private

### Requirement: Where the page is saved
The page SHALL be written to the data folder as `year-in-review-<year>.html` (`server`),
`year-in-review-<year>-me.html` (`me`) or `year-in-review-<year>-person-<id>.html` (`user`, where
`<id>` is the first 8 hex characters of the SHA-256 of the person's key, so no name is in the file
name), or to `--output PATH`. The key SHALL be the same for a person whichever source the history
came from: `owner` for the server owner (Tautulli's admin, or Plex account 1), otherwise the person's
Plex account id, which Tautulli also uses as its user id. It SHALL replace any earlier file in one step, and be
created readable only by the user (`600`) in a folder readable only by the user (`700`). `recap_id`
SHALL be the default file name without the `year-in-review-` prefix and `.html` (`2025`, `2025-me`,
`2025-person-1a2b3c4d`), even when `--output` is given. The script SHALL never publish the page
itself.

#### Scenario: Running the same recap twice
- **WHEN** the 2025 whole-server recap is built twice
- **THEN** `year-in-review-2025.html` is replaced, there is still one file, and `recap_id` is `2025`
  both times

#### Scenario: One person's recap file
- **WHEN** a recap is built with `--user alex-test`
- **THEN** neither the file name nor `recap_id` contains `alex-test`

#### Scenario: Same person, either source
- **WHEN** a recap for the same person is built once from Tautulli and once from Plex
- **THEN** both runs give the same `recap_id`, including when that person is the server owner

### Requirement: Choosing where recaps go
`destination local|online|both` SHALL save the choice in `year-in-review-state.json` in the data
folder and print it. One choice SHALL apply to every recap. Until a choice is saved, builds SHALL
print `destination: null` and `ask` containing `destination`; after that, `ask` SHALL be empty.
Choosing `local` SHALL keep saved online links, so switching back to `online` or `both` updates the
same pages. The state file SHALL be separate from the dashboard's, so choosing a destination for one
never changes the other.

#### Scenario: First recap
- **WHEN** a recap is built and no destination has been saved
- **THEN** the page is written, `destination` is `null` and `ask` contains `destination`

#### Scenario: Saving a choice
- **WHEN** `destination both` runs
- **THEN** the next build of any recap prints `destination: "both"` and `ask` is empty

#### Scenario: The dashboard's choice
- **WHEN** the dashboard's destination is `online` and no recap destination has been saved
- **THEN** a recap build prints `destination: null`

### Requirement: Remembering each recap's online page
`online-page --recap ID --url URL` SHALL save the link of a published recap so later builds of that
recap print it as `online_page` and it can be updated in place. `ID` SHALL match
`^\d{4}(-me|-person-[0-9a-f]{8})?$`; the URL SHALL be accepted only under the same rules as the
dashboard's `online-page` (an `https://claude.ai/` link whose path is `/artifact/<id>` or
`/code/artifact/<id>`). Anything else SHALL be refused with an error and nothing saved.
`online-page --recap ID --forget` SHALL clear that recap's link only. Each recap's link SHALL be kept
separately, so building or publishing one recap never changes another's link.

#### Scenario: Re-running a published recap
- **WHEN** the link for recap `2026` was saved and the 2026 whole-server recap is built again
- **THEN** `online_page` is that link

#### Scenario: Two recaps, two pages
- **WHEN** links are saved for `2026` and `2026-me`
- **THEN** building the `--me` recap prints the `2026-me` link, and the whole-server recap still
  prints the `2026` link

#### Scenario: A link to somewhere else
- **WHEN** `online-page --recap 2026 --url https://example.com/page` runs
- **THEN** the script exits with an error and the saved link is unchanged

#### Scenario: A crafted recap id
- **WHEN** `online-page --recap ../dashboard --url https://claude.ai/artifact/abc` runs
- **THEN** the script exits with an error and nothing is saved

### Requirement: Connection check
`--check` SHALL test Plex and Tautulli separately, as in `watch-activity`, and SHALL ignore the other
options. A Tautulli failure SHALL be reported in the result (with `ok: false`) rather than as an error.

#### Scenario: Tautulli key changed
- **WHEN** `--check` runs and Tautulli rejects the key
- **THEN** the output has `ok: false` and the Tautulli error, and the Plex result is still shown

