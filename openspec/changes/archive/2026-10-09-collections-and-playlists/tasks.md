## 1. Check the Plex details on a real server

- [x] 1.1 Check that `/library/sections/{id}/collections` lists a library's collections with `title`, `smart`, `childCount` and `ratingKey` (make a regular and a smart collection on the test server if it has none)
- [x] 1.2 Check that `/library/collections/{id}/children` returns a collection's titles, including for a smart collection, and what a TV collection holding a season or episode looks like
- [x] 1.3 Check that `/playlists` returns the signed-in account's playlists with `playlistType`, `smart`, `leafCount` and `duration`, and that `/playlists/{id}/items` returns items with their media and `deletedAt` when a file is missing
- [x] 1.4 Check what happens to a playlist item when its title is removed from the library (dropped from the playlist or kept), and adjust the design and SKILL.md wording to match (not checked: it would mean deleting a title; the wording makes no claim either way)
- [x] 1.5 Update the spec and design if any path or field differs from what they say

## 2. Script

- [x] 2.1 Create `plugins/cinemetric/skills/collections-and-playlists/scripts/collections_and_playlists.py` with copies of the shared helpers (`load_config`, `validate_url`, `PlexClient`, `clean`, `media_deletion_allowed`) and `ALLOWED_PATHS` for the eight paths
- [x] 2.2 Options and `--check`: `--library`, `--only`, `--limit` (0 to 500), and the error for a `--library` that matches no movie or TV library
- [x] 2.3 Library listings in pages of 500 and the size table: movies (every version's parts), episodes, and totals per show and season
- [x] 2.4 Collections: read each library's collections and children, `smart`, `titles`, `storage_bytes` with each rating key once, and a failed children request kept with `childCount` and noted in `unavailable`
- [x] 2.5 Single-title and empty collections, and per-library titles in a collection and in none (shows counted through seasons and episodes)
- [x] 2.6 Playlists: kind, smart, items, duration, storage with each rating key once, unavailable items by the `deletedAt` rule, up to 15 examples, `playlists_scope`, and 401 or 403 turned into `playlists` `null` with an `unavailable` entry
- [x] 2.7 Sorting, the limits and `more_*` counts, `totals`, `skipped_libraries`, and cleaning every server title
- [x] 2.8 `media_deletion_allowed` from `/:/prefs`, reading only `allowMediaDeletion`

## 3. SKILL.md

- [x] 3.1 Write `plugins/cinemetric/skills/collections-and-playlists/SKILL.md`: when to use it, how to call the script (`--only` when the user asks about just one half), presentation order (totals, collections largest first, single-title and empty collections, titles in no collection, playlists, playlists with missing items), always saying playlists cover only the signed-in account, facts only (no suggestions to make, merge or delete collections or playlists), the media deletion line, and the rules every `SKILL.md` carries
- [x] 3.2 `allowed-tools` lists only `Read` and the script

## 4. Tests

- [x] 4.1 Add made-up fixtures in `tests/fixtures/collections-and-playlists/` (no real names; titles from the public domain or invented)
- [x] 4.2 Add `tests/test_collections_and_playlists.py` covering everything listed for `collections-and-playlists` in the testing spec
- [x] 4.3 List the new script in `tests/helpers.py` so the cross-script security, shared helper and media deletion checks run against it
- [x] 4.4 Run the full test suite and fix anything that fails

## 5. Docs, website and version

- [x] 5.1 README: new row in the Skills table and an example question; remove `collections-and-playlists` from the Roadmap (the README has no list of example questions; the Skills table row covers it)
- [x] 5.2 `openspec/ideas.md`: remove the `collections-and-playlists` notes and update the line about the three new skills
- [x] 5.3 `website/index.html`: the new skill in the **Your library** group, with a description, an example request and a terminal demo panel using made-up data (sixteen skills)
- [x] 5.4 Bump the version to 0.30.0 in every script's `VERSION`, `plugin.json` and `marketplace.json`
- [x] 5.5 Try the skill against a real server: all libraries, one library, `--only playlists`, a single-title collection, a smart collection, and a playlist with a missing file (if the test server has none, say so and rely on the tests) (done: all libraries, TV only, --only playlists and --only collections, two single-title smart collections and one empty regular one; the server has no playlist with a missing file or a TV collection, so those rest on the tests)
