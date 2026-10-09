# collections-and-playlists Specification

## Purpose

A read-only report on a Plex server's collections and playlists: each collection in the movie and TV
libraries with how many titles it holds and the storage they use, smart or regular, collections with
one title or none, how many titles are in no collection, and the signed-in account's playlists with
their size and length, including items whose files Plex can no longer find. Plex keeps playlists per
account, so other people's playlists can't be seen. Script:
`skills/collections-and-playlists/scripts/collections_and_playlists.py`. How Claude presents it is in
the skill's `SKILL.md`.
## Requirements
### Requirement: Sources used
The script `skills/collections-and-playlists/scripts/collections_and_playlists.py` SHALL request only
`/`, `/library/sections`, `/library/sections/{id}/all`, `/library/sections/{id}/collections`,
`/library/collections/{id}/children`, `/playlists`, `/playlists/{id}/items` and `/:/prefs` from the
user's Plex server, all with `GET`, reading listings in pages of 500. `/:/prefs` SHALL be read only
for the media deletion setting (see "Media deletion setting" in the conventions spec). It SHALL NOT
contact Tautulli, plex.tv or any other address, and SHALL NOT create, change or delete any
collection or playlist.

#### Scenario: Building a report
- **WHEN** the script builds a report
- **THEN** every request goes to the configured Plex server, to one of the eight allowed paths, with
  `GET`

#### Scenario: Tautulli is set up
- **WHEN** Tautulli is configured
- **THEN** the script still makes no Tautulli request

#### Scenario: A request to change a playlist
- **WHEN** the script tries to send a `PUT` or `DELETE` to `/playlists/{id}/items`
- **THEN** it stops with the blocked request error and nothing is sent

### Requirement: Collections read
Collections SHALL be read from movie and TV libraries only; other libraries SHALL be named in
`skipped_libraries` with their type. For each collection the script SHALL report `title`, `library`,
`smart` (true for a smart collection), `titles` (how many items its children listing returns),
`storage_bytes`, `storage_gb` (rounded to one decimal place) and `rating_key`. A collection's children SHALL be read with
`/library/collections/{id}/children`, so smart collections are counted by what Plex puts in them now.
If the children request fails for one collection, that collection SHALL keep Plex's `childCount` as
`titles`, have `storage_bytes` and `storage_gb` `null`, and be named in `unavailable`; the rest of the
report SHALL be built as usual. If a library's listing or its collections listing can't be read, that
library's counts SHALL be `null`, none of its collections SHALL be listed, it SHALL be named in
`unavailable`, and the other libraries SHALL be reported as usual. Each `unavailable` entry SHALL have
`part` (what couldn't be read) and `reason`.

#### Scenario: A smart collection
- **WHEN** a movie library has a smart collection whose children listing returns 12 movies
- **THEN** its entry has `smart` true and `titles` 12

#### Scenario: A music library
- **WHEN** the server has a music library with collections
- **THEN** that library is in `skipped_libraries` and none of its collections are listed

#### Scenario: One collection can't be read
- **WHEN** the children request for one collection answers 500
- **THEN** that collection is listed with Plex's `childCount` as `titles` and `storage_bytes` `null`,
  `unavailable` names it, and the script exits 0

#### Scenario: One library can't be read
- **WHEN** the movie listing for "Movies" answers 500 and "TV Shows" reads normally
- **THEN** "Movies" has `collections` `null` and is named in `unavailable`, and the TV collections
  are reported

### Requirement: Collection sizes
Sizes SHALL come from each library's full listing: movies with `type=1` and episodes with `type=4`.
A movie's size SHALL be the total of every part of every media version. A show's size SHALL be the
total of its episodes' sizes (grouped by `grandparentRatingKey`), and a season's the total of its
episodes (grouped by `parentRatingKey`); an episode's size is its own. A collection's
`storage_bytes` SHALL be the total of its children's sizes, each rating key counted once. A child of
any other kind SHALL count toward `titles` but add nothing to `storage_bytes`.

#### Scenario: A movie with two versions
- **WHEN** a collection holds one movie with a 4 GB version and a 20 GB version
- **THEN** the collection's `storage_bytes` is 24 GB

#### Scenario: A collection of shows
- **WHEN** a TV collection holds two shows whose episodes total 30 GB and 50 GB
- **THEN** the collection's `storage_bytes` is 80 GB

### Requirement: Single-title and empty collections
`single_title_collections` SHALL list every collection with `titles` 1, and `empty_collections`
every collection with `titles` 0, each entry with `title`, `library` and `smart`, plus, for a
single-title collection, `item_title` and `item_year` (the one title's title and year, or `null`). Both lists SHALL be sorted by library, then
collection title, and capped by `--limit`, with `more_single_title` and `more_empty` giving how many
were left out.

#### Scenario: A collection with one movie
- **WHEN** the "Paddington Collection" holds only "Paddington" (2014)
- **THEN** it is in `single_title_collections` with `item_title` "Paddington" and `item_year` 2014,
  and still appears in the main collections list

#### Scenario: An empty smart collection
- **WHEN** a smart collection's rules match no titles
- **THEN** it is in `empty_collections` with `smart` true

### Requirement: Titles in no collection
For each library whose collections were read, the report SHALL give `titles` (movies or shows in the
library listing), `in_a_collection` and `in_no_collection` (counts), and `in_no_collection_percent`
(rounded to one decimal place, or `null` for an empty library). A show SHALL count as in a
collection when the show itself, or one of its seasons or episodes, is a child of any collection in
that library. Titles in no collection SHALL NOT be listed by name.

#### Scenario: Some movies in collections
- **WHEN** a library has 200 movies and 50 of them are in at least one collection
- **THEN** its `in_a_collection` is 50, `in_no_collection` is 150 and `in_no_collection_percent` is
  75.0

#### Scenario: A movie in two collections
- **WHEN** one movie is in two collections
- **THEN** it counts once in `in_a_collection`

### Requirement: Playlists read
The script SHALL read the playlists `/playlists` returns for the signed-in account. For each playlist
it SHALL report `title`, `kind` (`video`, `audio` or `photo`, from `playlistType`), `smart`, `items`
(the number of entries returned by `/playlists/{id}/items`, counting a title once for each time it
appears), `duration_ms`, `storage_bytes` (the total size of the items' media, each rating key
counted once), `storage_gb` and `unavailable_items`. `items` and `duration_ms` SHALL come from the
items returned, never from the playlist's own `leafCount` or `duration`, which can be out of date for
a smart playlist; `duration_ms` SHALL fall back to the playlist's own `duration` only when the items
give none, and be `null` when neither does. The report SHALL include `playlists_scope` set to
`"signed_in_account"`. When `/playlists` can't be read (for example 401 or 403), `playlists` SHALL be
`null`, `unavailable` SHALL say playlists couldn't be read, and the collections part SHALL still be
built. When one playlist's items can't be read, that playlist SHALL be listed with `items`,
`storage_bytes`, `storage_gb` and `unavailable_items` `null`, and named in `unavailable`.

#### Scenario: A music playlist
- **WHEN** the account has an audio playlist with 300 tracks
- **THEN** it is listed with `kind` `audio` and `items` 300

#### Scenario: A smart playlist with an out-of-date count
- **WHEN** a smart playlist's `leafCount` is 5291 but its items listing returns 6549 entries
- **THEN** its `items` is 6549

#### Scenario: A title in a playlist twice
- **WHEN** one 2 GB episode appears twice in a playlist of 2 entries
- **THEN** its `items` is 2 and `storage_bytes` is 2 GB

#### Scenario: Playlists refused
- **WHEN** `/playlists` answers 403
- **THEN** `playlists` is `null`, `unavailable` explains it, the collections are still reported, and
  the script exits 0

### Requirement: Playlist items Plex can't find
A playlist item SHALL be unavailable when every one of its media versions has a `deletedAt` value
(the rule `library-report` uses for unavailable files); an item with at least one version without
`deletedAt` SHALL count as available. `playlists_with_missing_items` SHALL list every playlist with
`unavailable_items` above 0, sorted by `unavailable_items` (most first), then title, capped by
`--limit`, each with `title`, `kind`, `items`, `unavailable_items` and up to 15 `examples` (each with
`title`, `year`, for an episode `show_title`, `season` and `episode`, and for a music track
`artist`). `more_playlists_with_missing_items` SHALL give how many were left out.

#### Scenario: An episode whose file is gone
- **WHEN** a playlist has 10 items and one episode's only media version has `deletedAt` set
- **THEN** the playlist has `unavailable_items` 1 and is in `playlists_with_missing_items` with that
  episode as an example, including its show title, season and episode

#### Scenario: One copy left
- **WHEN** a movie in a playlist has two versions and only one has `deletedAt` set
- **THEN** it doesn't count as unavailable

#### Scenario: More than 15 missing items
- **WHEN** a playlist has 40 unavailable items
- **THEN** its `unavailable_items` is 40 and `examples` holds 15

### Requirement: Options
The script SHALL accept `--library NAME` (repeatable, case-insensitive), `--only
collections|playlists`, `--limit N` (entries per list, default 50, limited to 0–500) and `--check`.
`--library` SHALL narrow only the libraries whose collections are read; playlists SHALL NOT be
filtered by it. A `--library` that matches no movie or TV library SHALL stop the script with an
error. `--only collections` SHALL make no playlist requests and set the playlists part to `null`;
`--only playlists` SHALL read no library listings or collections and set the collections part to
`null`.

#### Scenario: Playlists only
- **WHEN** run with `--only playlists`
- **THEN** no `/library/sections/{id}/...` request is made and `collections` is `null`

#### Scenario: One library
- **WHEN** run with `--library "Kids Movies"`
- **THEN** only that library's collections are read, and every playlist is still reported

#### Scenario: Out-of-range limit
- **WHEN** run with `--limit 9999`
- **THEN** each list holds at most 500 entries

### Requirement: Report contents
The JSON report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version),
`media_deletion_allowed`, `libraries` (the per-library counts from "Titles in no collection", with
`name`, `type` and `collections`), `skipped_libraries`, `collections` (sorted by `titles` most first,
then `storage_bytes` most first, then title, capped by `--limit`, with `more_collections`),
`single_title_collections`, `empty_collections`, `playlists_scope`, `playlists` (sorted by `items`
most first, then `storage_bytes`, then title, capped by `--limit`, with `more_playlists`),
`playlists_with_missing_items`, `unavailable` and `totals`. `totals` SHALL give `collections`,
`smart_collections`, `single_title_collections`, `empty_collections`, `playlists`,
`smart_playlists`, `playlists_with_missing_items` and `unavailable_playlist_items`, covering
everything read before any limit, with `null` for a part not read. Every title from the server SHALL
be cleaned as described in the security spec's "Server text is treated as data".

#### Scenario: No collections or playlists
- **WHEN** the server has no collections and the account has no playlists
- **THEN** every list is empty, `totals` counts are 0, and the script exits 0

#### Scenario: More collections than the limit
- **WHEN** a server has 80 collections and `--limit` is 50
- **THEN** `collections` holds the 50 with the most titles, `more_collections` is 30, and
  `totals.collections` is 80

#### Scenario: A collection title with control characters
- **WHEN** a collection's title contains control characters or text made to look like instructions
- **THEN** the control characters are removed and the text appears only as a value in the JSON

