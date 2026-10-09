## Context

Collections and playlists are the two ways Plex lets people group titles. Collections live in a
library and are shared by everyone who can see that library; playlists belong to one Plex account
and can mix titles from several libraries. Cinemetric doesn't report on either yet (`title-lookup`
only lists the collections one title is in).

The skill follows every existing rule: read-only toward Plex, standard library only, one
self-contained script, only the configured Plex server, server text cleaned before it's printed,
facts only. No Tautulli: nothing here depends on watch history.

Endpoint details were checked against a real server on 2026-10-09 (206 movie collections, 205 of them
smart; six playlists, all music); what was found is noted under each decision. The server had no TV
collections and no playlist items with missing files, so those cases rest on Plex's usual shapes and
the tests.

## Goals / Non-Goals

**Goals:**
- List every collection in movie and TV libraries with how many titles it holds and how much storage
  those titles use.
- Pick out collections with one title (and empty ones), since those are the ones people usually ask
  about.
- List the signed-in account's playlists and find the ones with items Plex can no longer find.
- Be honest about what the token can't see (other people's playlists).

**Non-Goals:**
- Changing anything: no creating, merging or deleting collections or playlists, and no suggestions
  to do so.
- Music and photo library collections. Music collections are rare and sizing them means reading
  every track; they can come later if anyone asks. Music and photo *playlists* are included, since
  `/playlists` returns them anyway.
- Other people's playlists. The owner's token can't see them, and fetching a token per person would
  mean handling other people's credentials.
- Missing posters or artwork for collections (that's `library-report`'s area).
- A dashboard section or snapshots in `changes`. Could be added later.

## Decisions

**Collections: one listing per library, then each collection's children.**
`/library/sections/{id}/collections` lists a library's collections with `title`, `smart` (the
string `"1"` for a smart one, missing otherwise), `childCount` and `ratingKey`. Each collection's
contents come from `/library/collections/{id}/children`. That's one request per collection (checked:
206 collections took about 10 seconds, and every children count matched `childCount`), and it's the
only way to see what a smart collection holds. Alternative considered: reading `Collection` tags from
the library listing. Checked: the listing carries no `Collection` tags at all, so this isn't an
option. If the children request fails for one collection, that collection keeps
Plex's `childCount`, gets `storage_bytes` `null` and is noted in `unavailable`.

**Sizes from the library listing, not from each collection.** The script reads each library's full
listing once (movies with `type=1`, episodes with `type=4`, pages of 500 as `library-report` does)
and builds a table of rating key to size. A movie's size is the total of every media version's
parts; a show's size is the total of its episodes (grouped by `grandparentRatingKey`), and a season's
the total of its episodes (`parentRatingKey`). A collection's storage is the total of its titles'
sizes, each title counted once. The same listing gives "titles in no collection": titles whose rating
key isn't in any collection's children. Alternative considered: reading each collection's children
with their media. Shows don't carry episode sizes in that answer, so a TV collection would need
`allLeaves` per show; the library listing gets everything in a few requests.

**Playlists: `/playlists`, then each playlist's items.** `/playlists` returns the signed-in
account's playlists with `title`, `playlistType` (video, audio, photo), `smart` (a real boolean here,
unlike collections), `leafCount` and `duration`. `/playlists/{id}/items` returns each item with its
media and part sizes, read in pages of 500 (paging checked). Checked: a smart playlist's `leafCount`
can be out of date ("All Music" said 5,291 but returned 6,549 items), so `items` is the number of
entries actually returned, never `leafCount`. An item is unavailable when any of its media versions has a `deletedAt` value
and none of its versions is without one, which matches what `library-report` counts as unavailable
(a title with one good copy left still plays). A playlist's storage is the total of its items' file
sizes, each title counted once even when it's in the playlist twice.

**Items deleted from the library.** Not checked: that would mean deleting a title. Plex is expected
to drop a removed title from its playlists, so the report only covers items still in the library
whose files can't be found. SKILL.md says that when asked about "broken" playlists, without claiming
either way what Plex does with removed titles.

**Playlists scope is stated in the report.** `playlists_scope` is `"signed_in_account"` and the
report says how many playlists that account has. With a managed user's or friend's playlists not
visible, SKILL.md tells Claude to say the list covers only the account Cinemetric signed in with.

**`--library` narrows collections only.** Playlists can span libraries, so filtering them by library
would cut playlists in half. `--library` limits which libraries' collections are read; playlists are
unaffected, and the report says which libraries were included. `--only collections` or
`--only playlists` skips the other half entirely (fewer requests).

**One part failing doesn't stop the report.** If one library's collections can't be read, or
`/playlists` answers 401 or 403, that part is `null` or left out with a reason in `unavailable`, and
the rest of the report is still printed, as `server-health` does with its parts.

**Ordering.** Collections largest first by number of titles, then by storage; playlists by number of
items, then by storage. Single-title and empty collections are listed separately, sorted by library
then title. `--limit` (default 50) caps each list; totals always cover everything.

## Risks / Trade-offs

- [Missing-file items and TV collections weren't seen on a real server] → Tests use made-up data in
  Plex's usual shapes (`deletedAt` on media, as in library listings).
- [Many collections means many requests] → One small request per collection. A server with 500
  collections would take a few seconds; acceptable for an on-demand report. No caching.
- [Collections that hold seasons or episodes, not whole titles] → Sizes cover shows, seasons and
  episodes from the same episode listing; any other kind is counted but adds no size.
- [Users may assume all playlists were checked] → `playlists_scope` in the output and a sentence in
  every answer that mentions playlists.
- [A huge playlist (thousands of music tracks)] → Items are read in pages of 500 and only sizes and
  `deletedAt` are kept, so memory stays small.

## Open Questions

- Should music libraries' collections be included later? Left out for now; see Non-Goals.
- Should collections and playlists go on the dashboard or into `changes` snapshots? Not in this
  change.
