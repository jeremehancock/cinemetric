## Context

Every piece of data this skill needs is already read by another skill: `episode-gaps` lists every
episode in a TV library, `unwatched` reads the whole watch history from Tautulli or Plex, and
`watch-activity` chooses between the two sources and finds one person by name. What's new is joining
them: lining up each person's finished episodes against the show's episode list on the server.
Scripts are self-contained, so the source choice and person matching are copied from
`watch-activity`, not imported.

Plex and Tautulli details were checked against a real server (Plex 1.43.4, Tautulli 2.18.2) on
2026-10-07; what was found is noted under each decision.

## Goals / Non-Goals

**Goals:**
- For each person and show, one clear answer: where they are, what's next, and whether they're caught
  up, waiting on new episodes, in the middle, or stopped.
- Don't call someone behind just because they rewatched early episodes or started partway in.
- The same choice of history source, and the same way of finding a person, as `watch-activity`.

**Non-Goals:**
- Episodes that aren't on the server. "Caught up" means caught up with what's on the server; the
  skill can't know a show has a new season out. Gaps are `episode-gaps`' job.
- Movies (a movie is watched or not; `watch-activity` and `unwatched` cover that) and music.
- Suggestions of what to remove or download.
- A dashboard section. It could come later if asked for; a per-person table doesn't fit the
  dashboard's server-wide summary well.
- Snapshots. Nothing is saved.

## Decisions

**Episode list: one paged listing per TV library.** `/library/sections/{id}/all?type=4` lists every
episode with `grandparentRatingKey`, `parentIndex`, `index`, `addedAt` and its media versions, the
same way `episode-gaps` reads it (pages of 500). `type=2` gives each show's title and year. An
episode counts as on the server when at least one media version has no `deletedAt`; one Plex can't
find doesn't count as left to watch. Episodes with no season or episode number, and season 0, are
left out. Alternative considered: `/library/metadata/{id}/allLeaves` per show, as `title-lookup`
does. That's one request per show, which is fine for one show but slow for a whole library, so it's
not used, even with `--show`.

**History: finished episodes per person.**
- Tautulli: `get_history` with `media_type=episode` and `grouping=1`, in pages, newest first.
  `grandparent_rating_key`, `parent_media_index`, `media_index`, `user_id`, `friendly_name`,
  `watched_status`, `date` and `stopped` are read; every other field is dropped on reading. With
  `--show`, `grandparent_rating_key` is passed; with `--user`, `user_id` is passed.
- Plex: `/status/sessions/history/all`, in pages, newest first. Plex can't filter it to episodes
  (checked on Plex 1.43.4: `type=4` returns nothing, `metadataType=4` is ignored and `type=episode`
  is refused), so every entry is read and only `type` `episode` entries are kept. Episode entries give the show as `grandparentKey` (`/library/metadata/123`), as found for
  `title-lookup`, plus `parentIndex`, `index`, `accountID` and `viewedAt`. With `--show`,
  `metadataItemID` is set to the show's rating key (checked for `title-lookup`). With `--user`,
  entries are kept only for that account, filtered in the script (as `watch-activity` does).
  `/accounts` is read only for names.
- Up to 100,000 rows, with `history_capped`, as `unwatched` does. Live TV is left out.
- `history_since` is how far back the source's history goes. With `--show` or `--user` the rows read
  are narrowed, so their oldest is only when that show or person was first played (found on a real
  server: September 2026 instead of August 2024). One extra request, oldest first, gets the real
  date; both Tautulli (`order_dir=asc`) and Plex (`sort=viewedAt:asc`) support it.
- History rows are matched to the episode list by show rating key, season and episode number, not by
  the episode's own rating key. Rating keys change when a file is replaced or the show is re-matched,
  but numbers don't, so a person's place survives an upgrade to a better file. (Checked: of 127
  Tautulli plays whose episode rating key no longer exists, 43 still match by numbers.)
- Alternative considered: Plex's own watched marks (`viewCount`) on episodes. Rejected, as in
  `unwatched`: they only describe the token's own account.

**A person's place is their furthest finished episode, by order, not by date.** For each person and
show the script takes every finished episode (Tautulli `watched_status` 1 or more; every Plex entry)
and keeps the highest (season, episode). Examples:
- Sam finished S01E01 to S02E05, then rewatched S01E01 last week. Furthest is S02E05; Sam isn't
  behind by a whole season.
- Alex started at S03E01 and finished S03E01 to S03E04. Furthest is S03E04. Seasons 1 and 2 aren't
  counted as left, because Alex chose to skip them.
- Episodes left = episodes on the server after the furthest one. Next episode = the first of those.
Alternative considered: the most recently finished episode. Simpler, but a rewatch of the pilot would
make someone look like they'd started over.

**Status, in this order:**
1. `caught_up`: no episodes on the server after the furthest one.
2. `new_episodes`: episodes are left, and every one of them was added after the person's last play of
   the show. They had watched everything there was, so this isn't stopping; they're waiting on new
   episodes they may not know about.
3. `stopped`: episodes are left, and the person's last play of the show is more than
   `--stopped-months` months ago (3 by default; calendar months, as `unwatched` counts them).
4. `in_progress`: everything else.
"Last play" counts any play of the show, finished or not (with Tautulli), because starting an episode
shows the person is still watching. With Plex it's the last finished episode.

**Who appears.** A person appears for a show when they finished at least one regular episode of it.
Someone who only started the pilot (Tautulli, never finished) isn't following it. A show nobody has
finished an episode of doesn't appear; `unwatched` covers those.

**Recently added.** Shows with at least one episode added in the last `--new-days` days. For each, the
episodes added in that window, and for each person who has finished an episode of the show, how many
of the new ones they've finished and whether they were following it before the new ones arrived
(`was_following`). This answers "which shows got new episodes nobody has watched yet" without a
separate pass. A first version listed only people who were already following, which made a show new
to the server look unwatched even when someone had finished most of it (found on a real server), so
`nobody_started` counts everyone.

**Sorting and the limit.** `shows` is sorted by the most recent play of the show by anyone, newest
first, and limited to `--top` (25 by default); `show_count` is the total before the limit. People
within a show are sorted by last play. Totals by status count everything before the limit.

**Names are shown, nothing else about people.** As in `watch-activity`, this is the owner's report on
their own server, so names appear. Only name, finished counts, positions and dates are printed: no
emails, account ids, user ids, IP addresses or device names. Tautulli and Plex ids are used only to
group rows and are dropped before printing.

**Owner-only history stops the report.** Unlike `title-lookup`, the history is the whole report, so
Plex answering 401 or 403 fails with `OWNER_ONLY`, as `watch-activity` does.

## Risks / Trade-offs

- [Plex history only records finished episodes] → Status still works, since it's built from finished
  episodes, but "last play" is the last finished one, so someone halfway through an episode last week
  may show as `stopped`. `source` and a `plex_history_note` say so, and SKILL.md tells Claude to
  mention it.
- [A full rewatch looks like being caught up] → Someone rewatching from the start after finishing
  shows as `caught_up`, which is true of where they've been, not where they are. Accepted; SKILL.md
  explains positions are the furthest episode reached.
- [Episodes numbered by date (season 2023, episode 20231005)] → Ordering by numbers still works.
  `episode-gaps` treats these specially only because gaps between dates aren't real gaps; here only
  order matters.
- [Absolute numbering across seasons, or a show re-matched with different numbering] → A person's
  finished numbers might not line up with the server's. Rows that don't match any episode on the
  server still count for last play, and are counted in `unmatched_plays` per show so the report can
  say so.
- [Big histories] → Up to 100,000 rows in pages, as `unwatched`; `--show` and `--user` filter at the
  source with Tautulli, so they're cheap.
- [Tautulli and Plex disagree] → `source` says which was used; SKILL.md tells Claude not to compare
  runs from different sources.

## Open Questions

- Is 3 months the right default for `stopped`? Shows that air weekly can have long breaks between
  seasons, but those are covered by `new_episodes` once the new season arrives. Revisit after trying
  it on a real server.
- Should `--user` without a name default to the signed-in owner (like `year-in-review --me`)? Left out
  for now; easy to add.
