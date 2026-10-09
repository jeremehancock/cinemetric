## Why

Nothing in Cinemetric looks at collections or playlists today. `title-lookup` shows which collections
one title is in, but there's no way to ask "what collections do I have, and how big are they?" or
"do any of my playlists point at files Plex can't find?". It's the last open skill planned for the
website's **Your library** group, and it fits the project's style: facts about what's on the server,
built from a few read-only requests.

## What Changes

- A new read-only skill, `collections-and-playlists`, with one script,
  `collections_and_playlists.py`. It reports:
  - **Collections** in each movie and TV library: title, library, smart or regular, how many titles
    each holds and how much storage those titles use, largest first.
  - **Collections with only one title**, and empty collections, listed on their own.
  - **Titles in no collection:** a count per library (and the share of the library), not a list.
  - **Playlists** visible to the signed-in account: title, kind (video, music or photo), smart or
    regular, how many items, total length and storage.
  - **Playlists with items Plex can no longer find:** each such playlist with how many of its items
    have a file Plex lists as unavailable, and up to 15 examples per playlist.
  - Totals: number of collections and playlists, how many have only one title, how many have
    missing items.
- **Only the signed-in account's playlists.** Plex keeps playlists per account, so the owner's token
  sees only the owner's playlists. The report says so (`playlists_scope`) instead of implying it
  saw everyone's.
- **Facts only:** no "you should make a collection for ..." or "delete this playlist" suggestions.
- Options: `--library NAME` (repeatable), `--only collections|playlists`, `--limit N` for the
  listed collections and playlists, `--check`.
- README: new row in the Skills table; `collections-and-playlists` comes off the Roadmap and out of
  `openspec/ideas.md`. Website: the new skill in the **Your library** group with a terminal demo
  panel (sixteen skills).
- Version bump to 0.30.0.

## Capabilities

### New Capabilities

- `collections-and-playlists`: what the script requests from Plex, which collections and playlists
  it reads, how sizes, single-title collections, titles in no collection and unavailable playlist
  items are worked out, the playlists scope, the options and the report totals.

### Modified Capabilities

- `conventions`: "Connection check" and "Media deletion setting" add the new script.
- `security`: "Only known destinations" gets a scenario saying `collections_and_playlists.py`
  contacts only the configured Plex server.
- `testing`: "Tests check the specs" adds `collections-and-playlists` coverage and a scenario for an
  unavailable playlist item that isn't reported.
- `website`: "Shows every skill" adds `collections-and-playlists` (sixteen skills).

## Impact

- New: `plugins/cinemetric/skills/collections-and-playlists/SKILL.md` and
  `plugins/cinemetric/skills/collections-and-playlists/scripts/collections_and_playlists.py` (with
  copies of the shared helpers `load_config`, `validate_url`, `PlexClient`, `clean` and
  `media_deletion_allowed`).
- New: `tests/test_collections_and_playlists.py` and made-up fixtures in
  `tests/fixtures/collections-and-playlists/`; the new script listed in `tests/helpers.py` so the
  cross-script security and media deletion checks find it.
- Changed: `README.md`, `openspec/ideas.md`, `website/index.html`.
- `VERSION` in every script, `plugin.json` and `marketplace.json`.
- Plex paths new to the project: `/library/sections/{id}/collections`,
  `/library/collections/{id}/children`, `/playlists` and `/playlists/{id}/items`, all read with
  `GET`. No Tautulli, no plex.tv, no new destinations.
