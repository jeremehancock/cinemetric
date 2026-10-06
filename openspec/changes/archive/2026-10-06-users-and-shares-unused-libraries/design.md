## Context

`users_and_shares.py` already knows, per library, which accepted people can see it (`shared_with`),
and per person, their most recent play (one Tautulli `get_users_table` call, or one Plex history
request per person). Neither says *which library* a play came from.

Both history sources carry that:
- Plex `/status/sessions/history/all` entries have `accountID`, `viewedAt` and `librarySectionID`.
  Only finished (or nearly finished) plays are recorded.
- Tautulli `get_history` rows have `user_id` and `date`, and include unfinished plays. They do **not**
  say which library a play came from (checked on the real server, 2026-10-06), but `get_history`
  accepts a `section_id` filter. On the real server the per-library counts (100 + 319 + 688 + 0)
  added up exactly to the unfiltered total (1,107).

`unwatched` and `watch-activity` already page through both of these the same way.

## Goals / Non-Goals

**Goals:**
- For each library, say which of the people it's shared with played anything from it recently.
- Flag shared libraries none of those people have played from recently, as a neutral fact.
- Keep the number of extra requests small and bounded.

**Non-Goals:**
- A per-person, per-library "last played" date going back further than the window. That would mean
  reading all history ever, or one request per person per library.
- Counting the owner's plays. The question is about what was shared, and the owner isn't listed.
- Suggesting changes to anyone's access. The skill stays read-only and facts-only.

## Decisions

**One window, reusing `--inactive-days`.** The existing option already means "how long counts as a
while" for people; using it for libraries too keeps one idea and one number. A separate
`--library-days` option was considered, but it's two knobs for the same question and SKILL.md
already maps the user's wording ("in six months") onto `--inactive-days`.

**A few history sweeps instead of per-person requests.** Read history newest first, in pages of
1,000, and stop at the first page that reaches back past the cutoff, or at a cap of 100,000 plays in
total (the same cap as `unwatched`). From each play keep only `(account id, library key)`. Then
`played_by` for a library is everyone in its `shared_with` whose account id appears with that key.
Plex needs one sweep for all libraries. Tautulli needs one sweep per library (filtered by
`section_id`), because its rows don't carry the library. Per-person-per-library requests were
rejected: 10 people × 8 libraries is 80 requests.

The existing per-person last-played lookup stays as it is; it can find dates older than the window,
which the sweep doesn't read.

**Same source preference as last played.** Tautulli when set up, otherwise Plex. If Tautulli's
`get_history` fails, fall back to the Plex sweep and list "Tautulli library activity" in
`unavailable`. If Plex's sweep fails too, `played_by` is `null` on every library, `library_activity`
has `source` null, and `unavailable` lists "library activity". Keeping the same preference avoids a
person showing "last played 3 days ago" (Tautulli) while appearing in no library's `played_by`
(Plex).

**Report shape.** Per library: `played_by` (sorted names, or `null` when unknown) and
`played_by_count` (or `null`). Top level: `library_activity` = `{source, days, complete}`.
`complete` is false when the cap was hit before the cutoff; in that case `played_by` still lists
what was found, but no `unused_library` flag is raised, because "no play found" isn't trustworthy.

**The `unused_library` flag.** One item with `kind`, `days` and `libraries` (sorted titles) instead
of `people`. A library qualifies when its `shared_with` is not empty, `played_by` is empty, and at
least one person in `shared_with` was invited more than `days` ago or has no invite date. A library
shared only with people who joined inside the window isn't flagged; they haven't had a fair chance.
The existing worth-a-look rule ("each with a kind and the names of the people involved") is reworded
to allow this item to carry library names instead.

**Matching people to plays.** Plays are matched by the same id the existing last-played code uses
(`_user_id`, the plex.tv user id, which is Plex's `accountID` and Tautulli's `user_id`). Library keys
are compared as strings. Plays from libraries the server no longer has are ignored.

**Dashboard.** `share_note()` gains a branch for `unused_library`: "N shared libraries with no plays
by the people they're shared with in D+ days" plus the titles. Library titles are shown even when
people's names are hidden, since they aren't about any person.

## Risks / Trade-offs

- [Plex history only records finished plays] → a library someone dips into but never finishes looks
  unused. SKILL.md already explains this caveat for last played; it will say it once for libraries too.
- [Bigger servers mean more pages] → bounded by the 100,000 cap and by stopping at the cutoff; a
  90-day window on a busy home server is usually one to a few pages.
- [Plex history entries missing `librarySectionID`] → those plays are skipped. On the real server all
  200 recent entries checked had it.
- [Tautulli needs one read per library] → a server with many libraries makes more requests, but each
  read is small (only that library's plays in the window).
- [Tautulli `get_history` returns grouped rows by default] → grouping doesn't change which library or
  person a play belongs to, so the default is fine.

## Migration Plan

Additive fields only. Existing fields and flags are unchanged, so the dashboard and any other reader
keep working. Rollback is reverting the change.

## Open Questions

None blocking.
