## Context

`watch-mix` joins two things Cinemetric already reads separately: what's on the shelf (library
listings, as `library-report` and `unwatched` read them) and what gets watched (history from Tautulli,
or Plex's own history without it, as `watch-activity`, `unwatched` and `year-in-review` read it). The
answer is a set of side-by-side shares, for movies and TV separately, by genre, decade and quality.

It follows every existing rule: read-only toward Plex and Tautulli, standard library only, one
self-contained script, only the configured Plex server and Tautulli address, server text cleaned
before it's printed, facts only, and a whole-server report that names no one.

Fields and paths below come from the existing scripts and were checked against a real server on
2026-10-09: a movie library of 1,970 titles with 34 genres and a TV library of 419 shows with 39
genres. Plex's genre filter works for both (`type=1` and `type=2`, using each genre's `key`); 1,551
of the movies and 300 of the shows have more genres than the listing shows (the listing never shows
more than two, the filter up to 12). All the genre requests took about 4 seconds for the movies and 2
for the shows. Plex history entries carry `ratingKey`, `type`, `viewedAt`, `accountID` and, for
episodes, `grandparentKey`, but no `duration`, so length comes from the shelf. Tautulli rows carry
`rating_key`, `grandparent_rating_key`, `media_type`, `play_duration`, `duration`, `started`, `live`
and `user_id`.

## Goals / Non-Goals

**Goals:**
- For each genre, decade and resolution, give its share of the shelf (titles and storage) next to its
  share of watching (plays and watch time), for movies and TV separately.
- Pick out the groups watched most above and below their shelf share, so the headline line ("Horror
  is 18% of your movies but 3% of what's watched") falls straight out of the report.
- Work with or without Tautulli, and say plainly which way watch time was measured.
- Whole server by default with no names; one person only when asked.

**Non-Goals:**
- Suggestions of any kind (add more of this, remove that).
- Listing titles. The report holds only groups and counts, so a whole-server report can't reveal what
  one person watched. (A "which titles make up anime's 22%" drill-down could come later, with
  `year-in-review`'s `--min-viewers` rule.)
- Music, photo and live TV.
- Other ways of grouping (content rating, studio, country, codec, HDR). Easy to add later on the same
  plumbing.
- A dashboard section, `changes` snapshots, or `year-in-review`'s favorite genres. The genre lookup
  here is what those would reuse; not in this change.
- Adjusting for titles added partway through the period (see Risks).

## Decisions

**Two halves, kept apart: movies and TV.** Every share is worked out within one kind, across every
included library of that kind ("18% of your movies", not "18% of everything"). Mixing them would let
one long-running show swamp every movie.

**What a "title" is on the shelf.** For genre and decade, a movie or a show (a show with 300 episodes
is one title, as people think of it). For quality, a movie or an episode, because resolution belongs
to a file and a show's episodes can differ. Storage share is given next to the title share, since
storage weights a long show properly and is what a server owner pays for.

**Genres come from Plex's genre filter, not the listing.** Library listings carry at most two genres
per title (found while building `what-to-watch`), which would undercount every genre past the second.
For each included library, the script reads `/library/sections/{id}/genre` for the genre list, then
`/library/sections/{id}/all?type=1` (movies) or `type=2` (shows) with `genre=<key>` for each genre,
keeping only rating keys. That gives every title's full genre set in one request (plus paging) per
genre, about 20 to 40 per library. Alternative considered (and suggested in `ideas.md`): detail
batches of 100 from `/library/metadata/{ids}`, as `playback-check` does. Those answers carry every
stream of every file, which is much heavier, and only played titles would need them, leaving the
shelf side still on the two-genre listing. The filter covers both sides with the same data.

**Decade from `year`.** A movie's `year`, or a show's (its first year). With no `year`, the year from
`originallyAvailableAt`; with neither, the title goes in an `unknown` decade. Decades are named like
`1980s`.

**Quality from the file on the server now.** Same buckets as `library-report` (`4K`, `2K`, `1080p`,
`720p`, `SD`, `unknown`). A movie with several versions counts at its best version. A play counts at
the quality of the title's file today, which may differ from what was played if the file was
replaced; the report says so (`quality_note`). Plex's history doesn't record what resolution was
played, and using one rule for both sources keeps them comparable.

**Which plays count, and watch time.**
- *Tautulli:* every grouped movie and episode play in the period, finished or not, since starting
  something is part of what gets watched; live TV left out. Watch time is `play_duration` (paused time
  left out), falling back to `duration` on older Tautulli. `watch_time_method` is `"played"`.
- *Plex:* Plex's history only holds finished (or nearly finished) plays, so each counts as one play,
  and watch time is the title's length from the shelf listing (`duration` of the movie or episode).
  `watch_time_method` is `"finished_plays_times_length"`. A play whose title has no `duration` adds a
  play but no time.
- The period: plays that started in the last `--months` calendar months (default 12), using the same
  `months_before` rule as `unwatched`.

Alternative considered: count only finished plays with Tautulli too, so both sources match. Rejected
because Tautulli's real watch time already weights a five-minute sample lightly, and dropping
unfinished plays would hide genres people start and abandon, which is part of the story.

**Matching plays to the shelf, in steps.** Plex gives a title a new rating key when its file is
replaced or it's added again. On the test server, matching by rating key alone left 143 of 365 movie
plays in the last year unmatched, and 141 of those were movies still on the server under a new key;
the 2020s went from "watched less" (-10.5 points) to "watched more" (+8.3) once they matched. So:
- A movie matches by rating key, else (Tautulli only) by `guid`, else by title and year, else by
  title alone when only one shelf movie has it. Titles are compared ignoring case, spaces and
  punctuation (`normalize`, as in `show-progress`). Plex history has no `guid` or `year`, only
  `originallyAvailableAt`.
- An episode's show matches by rating key (Tautulli's `grandparent_rating_key`, or the last part of
  Plex's `grandparentKey`, which is all Plex history has), else through the episode's own rating key,
  else by show title. Its episode matches by rating key, else by season and episode number within
  the show, which is how `show-progress` survives replaced files.
- Several shelf titles with the same name means no match at that step, rather than a guess.

With this, 1 movie play and 7 TV plays in the year stayed unmatched. What's left is left out of every
share and counted in `unmatched_plays` (plays and hours), so Claude can say "7 plays were of titles no
longer on the server." A show matched but its episode removed still counts for genre and decade, and
goes to `unknown` quality. The history's titles are only used to match and never printed.

**Sizes and quality from files Plex can still find.** A version with `deletedAt` is a file that's
gone, so it adds no storage and doesn't set the quality, as in `unwatched`.

**Shares and the gap.** Each group row has `titles`, `titles_percent`, `storage_bytes`,
`storage_percent`, `plays`, `plays_percent`, `hours`, `hours_percent` and `gap_points`
(`hours_percent` minus `titles_percent`, in percentage points). Percentages are one decimal place and
`null` when the whole is zero. Genre rows can add up to more than 100%, because a title in two
genres counts in both; `genre_note` says so in the report. Titles with no genre go in a `(no genre)`
row.

**Biggest differences.** For each kind, `watched_more` and `watched_less` list up to `--top` (default
5) rows from all three groupings together, sorted by `gap_points`. Rows with fewer than 5 titles on
the shelf, `unknown` decade or quality and `(no genre)` are left out, so a single odd title doesn't
lead the report. Each entry says which grouping it came from.

**Small samples are flagged, not hidden.** When a kind has fewer than 30 matched plays,
`few_plays` is true for it. The shares are still printed; SKILL.md tells Claude to say they're based
on very little watching.

**Whole server names no one; one person on request.** Without `--user`, plays by every account count
and no person's name, id or device appears anywhere (the report has no titles or people at all).
With `--user NAME`, the person is matched as in `watch-activity` (Tautulli `get_users`, or Plex
`/accounts`), with the same `USER_NOT_FOUND` and `USER_AMBIGUOUS` errors, and only their plays count;
the shelf stays the same. There's no `--me`: the owner can use their own name.

**Source choice and errors as elsewhere.** `--source auto|tautulli|plex` and `fallback_reason` work as
in `unwatched`; the shelf always comes from Plex. A refused Plex history while `/` works is
`OWNER_ONLY`. History is read newest first in pages, stopping once past the period, up to 100,000
plays (`history_capped`). If one library's listing or genre requests fail, that library is left out,
named in `unavailable`, and the report is built from the rest.

## Risks / Trade-offs

- [Titles added recently look under-watched: they've been on the shelf for weeks, not the whole
  period] → Accepted for a first version. SKILL.md tells Claude to mention it when a group's gap might
  come from recent additions (for example, a 4K row after a run of 4K upgrades). An "added before the
  period" filter is an easy follow-up.
- [Plex-only watch time is an estimate] → `watch_time_method` in the report and a sentence in every
  answer built from Plex history.
- [Many genre requests on a big server] → One light request (plus pages of 500) per genre per
  library. About 6 seconds for 73 genres on the test server; `--library` narrows it.
- [Quality of a replaced file] → `quality_note` says plays are grouped by today's file.
- [A genre with one dedicated viewer] → Group shares don't name anyone or any title, and `--user` is
  only used when asked. No further hiding.

## Open Questions

- Should the period default be 12 months, or follow the shelf (everything since each title was
  added)? Going with 12 months, as `ideas.md` proposed.
