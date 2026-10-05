## Context

Every existing skill answers a server owner's question. `what-to-watch` answers a viewer's: "what's
on my server that I'd enjoy tonight?". The data is already within reach: `library-report` and
`unwatched` read every movie and episode from `/library/sections/<id>/all`, and those listings also
carry the fields a viewer cares about (year, runtime, genres, ratings, summary, the signed-in
account's watched state).

Decisions already made with the user (2026-10-05, `openspec/ideas.md`): "unwatched" means the owner's
own account; only titles on the server, never suggestions from outside; Claude suggests a short list
of 3 to 5 with a one-line reason each.

## Goals / Non-Goals

**Goals:**
- One script that filters the movie and TV libraries by the things people actually ask for (genre,
  length, decade, rating, content rating, unwatched) and returns a shortlist for Claude to pick from.
- Variety: asking again gives different suggestions.
- "Pick up where I left off" from the same skill.
- No new network destinations, no Tautulli.

**Non-Goals:**
- Recommendations based on taste or history ("because you watched X"). That needs a model of the
  person's viewing, which is a much bigger idea.
- Titles not on the server, trailers, or anything from outside Plex.
- Music, photos and live TV.
- A dashboard section. The dashboard is about the server.
- Picking for someone else in the household. Plex keeps watched state per account and Cinemetric has
  only the owner's token, so another person's watched state isn't available.

## Decisions

**Filter in the script, except for genre.** Plex's listing accepts filters like `genre=` and
`unwatched=1`, but which ones work, and how they treat edge cases, isn't documented. Reading the whole
listing and filtering in Python is predictable and testable with fixtures.

Genre is the exception. The check on the owner's server found that library listings carry at most
two genres per title, while a title's own page has up to seven. Filtering on the listing missed 25 to
75% of matches (one movie genre: 393 titles from the listing, 695 from Plex's filter). So for
`--genre`, the script reads the library's genre list from `/library/sections/{id}/genre` (which also
gives the full `genres_available`) and asks `/library/sections/{id}/all` with `genre=<key>` for the
matching titles, then intersects that with the other filters. Each genre request took under a second.
Fetching every title's own page instead would be about 2,400 requests. The user chose Plex's filter
on 2026-10-05; it adds one read-only Plex path. The cost is reading every
movie and show each time; `unwatched` does the same with episodes (far more items) in about 10 seconds
on the owner's server, and shows are one item each here, so this should take a few seconds.

**Shows come from the show listing (`type=2`), not episodes.** The show-level item has `leafCount`
(episodes), `viewedLeafCount` (episodes this account has watched), `childCount` (seasons), genres,
year, ratings and `duration` (a typical episode's length). That's everything needed, in one item per
show, instead of thousands of episodes.

**Three watched states for shows.** "A random unwatched show" means one you haven't started, so
`--unwatched` keeps only shows with no episode watched. Shows you're partway through are `started` and
belong to continue watching. In-progress movies do count as unwatched, since you haven't seen the end;
they're marked `in_progress` so Claude can say so.

**Random by default.** Shuffling before the
limit means repeat questions give new titles. No seed option: tests replace the shuffle. Other sorts
(rating, added, year) are there for "the best rated" or "something new".

**What else the check found (owner's server, 2026-10-05).** Shapes, counts and timings only. 1,968
movies and 412 shows read in about 1.3 seconds. Movies had `audienceRating` (1,961) and `rating`
(critic, 1,838), mostly from Rotten Tomatoes; shows had only `audienceRating` (from TMDB). All items
had a `plex://` `guid`, a year and a summary. 13 content ratings on movies, 9 on shows.

**Which rating.** Plex items can carry `audienceRating` and `rating` (critic), both on a 0 to 10
scale, depending on the agent (Rotten Tomatoes, IMDb, TMDB). Audience rating is used for
`--min-rating` and `--sort rating` because more titles have it and it's closer to "will I enjoy it";
critic rating is the fallback. Both are reported so Claude can mention either.

**Merge the same movie across libraries by `guid`.** Owners often keep "Movies" and "4K Movies".
Suggesting the same film twice would look broken. This is the opposite choice from `unwatched`
(which counts per item because it's about disk space) because here the question is about the film.
Shows are merged the same way.

**Continue watching from `/library/onDeck`.** It returns in-progress movies and episodes plus the next
episode of started shows. On the owner's server it returned 13 items (10 movies, 3 episodes, one of
them not started yet), while the newer `/hubs/continueWatching` returned only 5, because a hub is
trimmed to a few items. Both had the fields needed (`parentIndex`, `index`, `viewOffset`, `duration`,
`lastViewedAt`, `librarySectionTitle`). `--continue` refuses other filters rather than ignoring them, so Claude doesn't present an
unfiltered list as if it were filtered.

**Summaries cut to 120 characters.** The security spec cuts every server text to 120 characters. That
is enough for one line of "what it's about", which is all SKILL.md asks Claude to give. No exception
is made to the rule.

**`genres_available` and `content_ratings_available`.** Genre names differ by metadata agent ("Science
Fiction" vs "Sci-Fi & Fantasy"). Listing what exists lets Claude map "something spacey" to the right
name and rerun, instead of guessing and getting zero matches.

**Shared helpers copied from `unwatched.py`,** minus the Tautulli client, per the conventions.
`tests/helpers.py`' `SCRIPTS` list gets the new script so the cross-script security tests cover its
copies.

## Risks / Trade-offs

- [Each title's `genres` shows at most two] → Matching uses Plex's full genres, but the genres
  printed for each title come from the listing. SKILL.md says not to describe a title as "not a
  comedy" just because the genre isn't among its two.
- [Ratings missing for some agents or libraries] → Titles with no rating are excluded by
  `--min-rating` and sorted last by `--sort rating`; SKILL.md mentions this when results look thin.
- [Content ratings vary by country] → "PG-13", "12", "TV-14" don't compare. The filter is exact
  match, and `content_ratings_available` shows what exists so Claude can pick the right ones for "for
  the kids".
- [Shared server, not the owner] → If Cinemetric is connected with a friend's access, watched state
  is the friend's own, which is still right for this skill. No `OWNER_ONLY` case is needed.
- [Reading the whole library every question] → A few seconds per ask. Acceptable; caching belongs to
  the separate snapshots idea.

## Migration Plan

Additive: a new skill and script. Rollback is removing the skill folder and the doc edits.

## Open Questions

- Should `--unwatched` treat in-progress movies as unwatched? Decided yes for now; easy to change.
- Is 20 the right default `--limit`? It gives Claude enough to choose 3 to 5 with variety.
