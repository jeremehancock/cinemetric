## Context

`library-report` reads every movie and episode from `/library/sections/<id>/all`, including added
dates and file sizes. `watch-activity` reads plays from Tautulli's `get_history` or Plex's
`/status/sessions/history/all`. Nothing joins the two, so no skill can say "these titles take up
space and nobody finishes them".

The obvious shortcut, Plex's `viewCount` and `lastViewedAt` on each library item, only describes the
account the token belongs to (the owner). A movie a friend watched last week would look unwatched.
So plays have to come from a history that covers every account.

Decisions already made with the user (2026-10-05): a separate skill, not part of `library-report`;
included on the dashboard; a 6 month default; partly watched titles don't count as played.

## Goals / Non-Goals

**Goals:**
- One list per library of titles that take up space and haven't been finished by anyone lately,
  largest first, with honest wording about how sure "nobody" is.
- Reuse the paths and Tautulli command other scripts already use. No new network destinations.
- Show the same facts on the dashboard.

**Non-Goals:**
- Suggesting deletions, or any change to the library. The skill describes; the user decides.
- Music and photo libraries. Listening history is noisy (shuffles, partial albums) and photos have no
  plays. Can be revisited.
- Who watched what. That's `watch-activity`. The report names no people.
- Adding the list to `library-report`. Its `SKILL.md` points to `unwatched` instead (see below).
- Remembering results between runs. That belongs to the separate snapshots idea.

## Decisions

**One threshold for both "old" and "not played lately".** `--months 6` means: added more than 6 months
ago, and no finished play in the last 6 months. The alternative was two options (added before X, not
played since Y). One number is easier to explain and was what the user picked. Each title still shows
`last_finished`, so Claude can separate "never finished" from "last finished two years ago", and the
report counts `never_finished` separately.

**Read the whole history, not just the last 6 months.** Reading only back to the cutoff would be enough
to decide which titles to list, but couldn't tell "never" from "a long time ago". The history entries
are small, so reading it all is cheap: 100,000 plays is 100 Tautulli pages or 500 Plex pages.
`history_since` (the oldest play read) and `history_capped` let Claude say how far back "never" really
goes. If the cap is hit and `history_since` is after the cutoff, some listed titles might have been
finished between the cutoff and `history_since`; SKILL.md says so.

**Source of plays: same rule as `watch-activity`.** `--source auto` prefers Tautulli and falls back to
Plex's history with a `fallback_reason`. This is familiar to users and the code pattern is already
tested. Both sources cover every account:
- Plex's history only records plays that were finished or nearly finished, which happens to be exactly
  the "partly watched doesn't count" rule. Every entry counts.
- Tautulli records every play, so only rows with `watched_status` 1 count. `grouping=1` is used, like
  `watch-activity`'s unfinished titles, so a movie paused and resumed later counts as one play and its
  combined progress decides whether it was finished.

**Matching plays to titles by rating key.** A movie play matches the movie's `ratingKey`; an episode
play matches its show through the grandparent rating key. Tautulli rows carry `rating_key` and
`grandparent_rating_key` (a number). Plex history entries carry `ratingKey` (text) and a
`grandparentKey` like `/library/metadata/123`, but no `grandparentRatingKey`, so the show's key is the
last part of `grandparentKey`. Keys are compared as text. Alternative considered: matching by `guid`. It survives a title being removed and re-added,
but Plex's history entries may not carry a guid, and it would make the same movie in two libraries
count as one. Per item is more honest about space: if the 1080p copy in "Movies" gets watched, the 4K
copy in "4K Movies" is still using space unwatched.

**A show's "added" date is its newest episode.** A show added years ago that just got a new season
isn't stale; using the show's own `addedAt` would list it. The episode listing (`type=4`) already gives
each episode's `addedAt`, `grandparentRatingKey`, `grandparentTitle` and sizes, so one listing gives
everything for shows. Shows are counted as one title each, with `episodes` for context.

**Size counts every file that exists.** Unlike duplicate detection in `library-report`, optimized
versions (`proxyType`) are included here, because the question is how much disk the title uses. Files
Plex can't find (`deletedAt`) use no space and are left out; a title with nothing left isn't listed
(`library-report` already reports unavailable files).

**Calendar months.** The cutoff is the same date N months ago (clamped, so "6 months before 31 August"
is 28 or 29 February). This matches what people mean by "6 months" better than 180 days, and is a few
lines with the standard library.

**`library-report` gets a pointer, not the list.** The user wasn't sure about including it. Adding it
there would mean `library-report` needs watch history (slower, and an `OWNER_ONLY` failure mode it
doesn't have today) and the same list would live in two places. Instead its `SKILL.md` suggests
`unwatched` when someone asks which titles nobody watches. If the user later wants it in
`library-report`, that's a small follow-up change.

**Dashboard runs `unwatched.py --limit 10`.** Each library lists its 10 largest, so the 10 largest
overall are always among them. The section is facts only and doesn't touch the overall status, like
the Sharing section. It has no people's names, so "hide names" doesn't affect it.

**Shared helpers copied.** Per the conventions, `load_config`, `validate_url`, `PlexClient`, the
Tautulli client and `clean` are copied from `watch_activity.py` (which already has the Tautulli-aware
config loading). `tests/helpers.py`' `SCRIPTS` list gets the new script so the cross-script security
tests cover its copies.

**What the confirmation step found (owner's real server, 2026-10-05).** Only shapes, counts and
timings were printed.
- Plex's history had 31,919 plays going back to December 2021. Reading it all in pages of 1,000 took
  about 11 seconds. Pages of 1,000 are honored, so the script uses them.
- Tautulli's grouped history had 4,837 movie and episode plays, also going back to December 2021, and
  reading it all took about 1 second. `watched_status` takes the values 0, 0.25, 0.5, 0.75 and 1, so
  only exactly 1 counts.
- The episode listing has `grandparentRatingKey`, `grandparentTitle`, `addedAt` and part `size` for
  episodes, as expected.
- A full run took about 10 seconds with Tautulli and 23 with Plex's history. Both sources listed
  almost the same titles (1,252 and 1,262), but "never finished" differed a lot: 933 with Tautulli,
  426 with Plex. 730 movies had a Plex history entry and no Tautulli row at all, and Plex had far more
  movie entries in early years (1,210 in 2021 against Tautulli's 28). The likely cause is that Plex's
  history also holds titles marked as watched by hand and plays Tautulli didn't see, while Tautulli
  only records plays it watched happen. The rules aren't changed for this: one source per report, as
  in `watch-activity`. SKILL.md explains the difference, and `--source plex` is there for an owner who
  wants titles marked as watched to count.

## Risks / Trade-offs

- [Plex history can be trimmed] → Plex can be set to delete old history, and history for removed
  accounts goes away. `history_since` shows how far back it goes, and SKILL.md explains that "never
  finished" means "not in the history that exists".
- [Rating keys change when a title is removed and re-added] → A title re-added under a new key looks
  unplayed. Rare in practice; SKILL.md mentions that a recently re-added title may show up.
- [The dashboard now reads the full library twice] → `library_report.py` and `unwatched.py` both list
  every item. They run side by side, so the build takes about as long as the slower one, but Plex does
  twice the listing work. Acceptable for a manual refresh; could share data later if it's slow.
- [Wording that sounds like a cleanup list] → SKILL.md has explicit rules: describe, never recommend
  removal, and mention that some titles are kept on purpose (favorites, kids' rewatches, archives).
- [Tautulli `watched_status` threshold differs from Plex's] → Tautulli marks watched at its own
  configured percent (default 85%), Plex at about 90%. Small difference; SKILL.md doesn't need to
  dwell on it.

## Migration Plan

Additive: a new skill and script, plus a new dashboard section. Rollback is removing the skill folder,
the dashboard section and the doc edits.

## Open Questions

- Should a title finished in another library (same `guid`) count as played? Decided per item for now;
  revisit if users find it confusing.
- Is 25 titles per library the right default for `--limit`? Easy to change.
