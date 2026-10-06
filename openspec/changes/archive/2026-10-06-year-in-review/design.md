## Context

`watch-activity` already reads watch history from Tautulli or Plex, matches a person by name, and
handles the owner-only rule. The dashboard already turns report data into a rule-based HTML page with
no scripts and a Content Security Policy that blocks all outside requests. A yearly recap needs both:
the history reading of one and the page building of the other.

`openspec/ideas.md` left three questions open for this idea:
1. Per-person sections by default, or only when asked?
2. Calendar year only, or any date range?
3. Could this just be a `dashboard` mode instead of a new skill?

It also noted that the security spec's "other people's private details stay private" rule covers
emails, tokens and account ids, not viewing habits. The user asked for this change "with care taken
around other people's viewing details", so this design answers question 1 with privacy rules in the
spec, not just a tone choice in `SKILL.md`.

## Goals / Non-Goals

**Goals:**
- A recap of one calendar year: total hours and plays, plays and hours per month with the busiest
  month and busiest day, top movies, shows and music artists, and the split between them.
- A page worth keeping or showing, built by rules so the same data always gives the same page.
- A whole-server recap that never reveals what any one other person watched.
- A way to make a recap of just your own year, or of one person's year to give to them.

**Non-Goals:**
- Arbitrary date ranges. `watch-activity --days` covers rolling windows.
- Favorite genres. Genres aren't in Tautulli's history rows or Plex's history entries, so each title
  would need a metadata request. Could be added later with a batched lookup like `playback-check`'s.
- A comparison with the previous year. Easy to add later by running the same counting twice.
- A "most active people" ranking, per-person sections in a whole-server recap, devices, or times of
  day. These are exactly the details that single people out.
- A dashboard section. The dashboard is about now and the last 30 days.
- Snapshots. History already holds everything a recap needs.

## Decisions

**A new skill, not a dashboard mode (question 3).** The dashboard is one page refreshed in place,
always about the last 30 days, with a remembered destination and names shown by default. A recap is a
fixed past period, one page per year, with stricter privacy defaults. Folding it into the dashboard
would mean a second set of defaults inside one script and one `SKILL.md`. Alternative considered:
`dashboard.py --year`, rejected for that reason.

**One script that reads history and writes the page.** Running `watch_activity.py --days 365` (the
way the dashboard runs other scripts) doesn't work: it counts a rolling window, not January to
December, has no monthly breakdown, and its top lists don't record how many different people played
each title, which the privacy rule needs. So `year_in_review.py` reads history itself, using a subset
of `watch-activity`'s allowed Plex paths (`/`, `/accounts`, `/status/sessions/history/all`) and
Tautulli commands (`get_tautulli_info`, `get_history`, `get_users`), and copies the shared helpers as
the conventions require. It writes the page by fixed rules, the second skill after `dashboard` to do
so; the page code is a smaller copy of the dashboard's escaping, CSP header and inline SVG bar chart,
not an import.

**Calendar year, default this year so far (question 2).** `--year YYYY` (2000 up to the current year).
The year runs from local midnight on 1 January to local midnight on 1 January of the next year, or to
now for the current year, which the page labels "so far". Today is in October, so the default is
useful immediately and becomes a full year in January via `--year`. Alternative considered: default to
the last finished year, rejected because for most of the year that's old news.

**Three scopes, with care built in (question 1).**
- *Whole server* (default). No person's name, user id or device in the JSON or on the page. Totals,
  months, busiest day and the movies/TV/music split are sums over everyone, which say nothing about any
  one person. People appear only as a count ("6 people watched something").
  Top lists are the risky part: on a household server, "top movie: X, 1 viewer" is simply what one
  person watched. So a title is listed only when at least `--min-viewers` different people played it
  (default 2, limit 1 to 10). The JSON gives `held_back` (how many titles were left out for this
  reason) so the page can say so. When fewer people than `--min-viewers` watched anything all year,
  the top lists are empty and the page suggests a "my year" recap instead. `--min-viewers 1` is
  allowed for owners who want the plain list (for example a server only they use); `SKILL.md` has
  Claude mention what it reveals when the user asks for it.
  Alternatives considered: names hidden by default but titles unfiltered (still reveals solo viewing
  on small servers); per-person sections behind a flag (that's what `watch-activity --user` is for).
- *My year* (`--me`). Only the signed-in account's plays: with Tautulli the user `get_users` marks as
  the admin (`is_admin`), with Plex the account with id 1, which Plex uses for the owner (both checked
  on the owner's server; Plex also lists an account 0, which isn't a person). The JSON names no one; the page says "Your year". If the owner can't be found, fail with
  `USER_NOT_FOUND` explaining why.
- *One person* (`--user NAME`). Same matching and errors as `watch-activity` (`USER_NOT_FOUND`,
  `USER_AMBIGUOUS`), and only that person's plays are read (Tautulli `user_id`; Plex entries filtered by
  account). The page is titled with their display name. `SKILL.md` has Claude say it's a recap of that
  person's own viewing and suggest sharing it only with them.
  `--min-viewers` doesn't apply to `--me` or `--user`; there's one viewer by definition. `--me` and
  `--user` together are refused.

**Counting.**
- Tautulli: `get_history` with `grouping=1` (a paused-and-resumed play counts once), in pages of
  1,000, up to 100,000 rows (`history_capped` when reached). The probe found Tautulli's `after` and
  `before` don't include the named day itself (`after=2025-12-31&before=2025-12-31` returned nothing
  on a day with plays) and work in Tautulli's own time zone, so the request asks for two extra days
  each side and the script keeps rows by their `started` time. Hours use `play_duration` (pauses
  already left out; `duration` on older Tautulli). A play is placed in the month and day it started, in
  local time.
- Plex: `/status/sessions/history/all` newest first, stopping once entries are older than the year
  (same paging and 100,000 cap). Plex records finished plays only and no watch time, so `hours` is
  `null` everywhere and top lists rank by plays.
- Live TV is left out with Tautulli, which marks it (`live`). Plex's history has no such mark, so
  there it's counted like any other play. Episodes count toward their show, tracks
  toward their artist (`grandparent_title`), movies by title and year.
- Top lists hold up to `--top` entries (default 10, limit 1 to 25), ranked by hours (Tautulli) or
  plays (Plex), ties broken by title so the page is stable. Each entry has `title`, `hours`, `plays` and
  `viewers` (how many different people; omitted for `--me` and `--user`).
- Busiest month: most hours (Tautulli) or plays (Plex); busiest day the same. `months` always has 12
  entries, with future months in the current year marked `future: true` so the chart shows them empty
  rather than as zero.

**Output.** The script writes the page and prints JSON with the recap data plus `output` (the page
path), `scope` (`server`, `me` or `user`), `user` (display name, only for `--user`), `year`,
`partial_year`, `source` and `fallback_reason`. The page goes to
`year-in-review-<year>.html`, `year-in-review-<year>-me.html` or
`year-in-review-<year>-person-<n>.html` in the data folder, where `<n>` is a short hash of the
person's key so names don't end up in file names (`--output PATH` overrides). The key has to be the
same from either source, or a run that falls back from Tautulli to Plex would start a second file and
page for the same person. Checked on the owner's server: Tautulli's user ids equal Plex's `/accounts`
ids for everyone except the owner (Plex's server calls the owner 1, Tautulli uses the plex.tv id), so
the key is the account id, or `owner` for the owner. Usernames were considered and rejected: only 4
of 12 matched between Tautulli's `username` and `/accounts` names. Written in one step,
`600`, folder `700`, like the dashboard. `--json-only` skips writing the page, for when the user only
wants the numbers in chat; nothing is published then.

**Publishing works like the dashboard (decided with the user, 2026-10-06).** Re-running a recap
should update what the user already has, both the local file and the online page, the way a dashboard
refresh does. So:
- One saved destination for all recaps (`local`, `online` or `both`), asked on the first run and
  changed with `destination local|online|both`. Alternative considered: a destination per recap,
  rejected as one more question every time a new year or person comes up.
- One saved online link per recap, keyed by `recap_id`: the file name's stem without the
  `year-in-review-` prefix (`2026`, `2026-me`, `2026-person-1a2b3c4d`). The first publish of a recap
  creates a page and Claude saves its link with `online-page --recap ID --url URL`; later runs update
  that page in place. `online-page --recap ID --forget` clears one link. Alternative considered: one
  link for all recaps (one page overwritten by whichever recap ran last), rejected because a person's
  recap would replace the household's at the same link.
- Links are checked exactly like the dashboard's (only `https://claude.ai/` artifact links), and
  `recap_id` must match `^\d{4}(-me|-person-[0-9a-f]{8})?$`, so the state file can't be steered
  elsewhere.
- Choosing `local` keeps saved links, so switching back updates the same pages.
- State lives in `year-in-review-state.json` in the data folder (`600`), separate from
  `dashboard-state.json` so the two skills never share a destination by surprise.
- The script never publishes; Claude does, following the saved destination.

## Risks / Trade-offs

- [`--min-viewers 2` hides favorites on servers where people watch different things] → `held_back`
  tells the user, the page says why, and `--min-viewers 1` or `--me` are offered.
- [Two people can still be inferred: on a two-person server, a title with 2 viewers was watched by
  both] → That's shared viewing, which the household already knows about. Accepted.
- [Totals for a small server still hint at one person's habits, e.g. busiest day when only one person
  watched that day] → Sums over a month or a day, with no title or time attached, are accepted as
  not singling anyone out.
- [A year of history could be slow] → The probe on the owner's server (2026-10-06) read 2025 in 1.3
  seconds from Tautulli (4,216 grouped rows) and 2025 to now in 3 seconds from Plex (about 8,000
  entries, pages of 1,000). The 100,000 cap bounds the worst case.
- [With `online` or `both` saved, a `--user` recap goes online too] → It's a private page only the
  owner can see until they share it, the same as the dashboard, which already shows names. `SKILL.md`
  has Claude say when a person's recap is being published, so it's never a surprise.
- [Copying more of `dashboard.py`'s page code adds a second copy to keep in step] → Only the escaping
  helper, CSP header and bar chart are copied; the conventions rule on shared helpers applies.

## Open Questions

- Whether hours from Plex can be estimated (finished plays times each title's length) without one
  request per title. Left out for now: plays only, like `watch-activity`.
