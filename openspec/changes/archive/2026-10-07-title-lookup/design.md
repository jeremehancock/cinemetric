## Context

Every existing report reads whole libraries. `title-lookup` answers a question about one title, so it
should make only a handful of requests: find the title, read its details, read its history. Most of
the facts it reports already have rules in other specs (playback causes in `playback-check`, plays
and sources in `watch-activity` and `unwatched`). Scripts are self-contained, so those rules are
copied, not imported.

Endpoint details were checked against a real server (Plex 1.43.4, Tautulli 2.18.2) on 2026-10-07;
what was found is noted under each decision.

## Goals / Non-Goals

**Goals:**
- One answer about one movie, show or episode, built from a few requests.
- The same playback rules and the same choice of history source as the existing skills, so two
  skills never disagree about the same file.
- Never guess between several matches.

**Non-Goals:**
- Episode gap detection for a show (that's `episode-gaps`; the report points to it).
- Anything outside the server: no lookups on other sites, no "is there a better version" advice.
- Music. Artists and albums can come later if anyone asks.
- A dashboard section. A lookup is a question, not a standing report.

## Decisions

**Finding the title: filter each library's listing by title.** The script asks each movie and TV
library for `/library/sections/{id}/all` with `type=1` (movies) or `type=2` (shows) and a `title`
filter, which Plex matches as "contains", ignoring case (checked: "runner" finds both Blade Runner films). This reuses a path every
skill already allows. Alternative considered: Plex's search endpoints (`/hubs/search`, `/search`).
They rank fuzzily and mix in people, collections and other types, which makes "exactly which title
did you mean" harder, and they'd add a new path to the allowlist. The filter doesn't ignore punctuation, so when it finds nothing the script reads the full listings
(pages of 500) and matches with punctuation ignored. On a 2,000-movie server that took about 1.5
seconds.

**Matching and picking.** An exact title match (ignoring case and punctuation) wins over "contains"
matches. `--year`, `--library` and `--type` narrow the list. The same title in several libraries
(same Plex `guid`) counts as one match with several libraries, as in `what-to-watch`. If more than one
match is left, the script prints `matches` (up to 20, with rating key, title, year, type and
libraries) and no title report; Claude asks which one and runs again with `--key`. No match prints an
empty `matches`.

**Details: one request per title.** `/library/metadata/{key}` gives media versions, streams
(audio and subtitle tracks), collections, genres and ratings in one answer. For a show,
`/library/metadata/{key}/allLeaves` lists every episode with its media versions in one request
(checked: 195 episodes with season and episode numbers); season counts, sizes and unavailable episodes come from that. An episode
(`--season` and `--episode` with a show) is found in the same listing, then read with
`/library/metadata/{key}` for its streams.

**Playback rules copied from `playback-check`.** The image-subtitle, TrueHD/DTS and bitrate rules
are copied word for word in behavior, and the tests run the same made-up files through both scripts
and expect the same causes. For a show, the playback part summarizes episodes (how many have each
cause) instead of listing every file, which would read the detail of every episode; it reads details
in batches of 100 like `playback-check` (`/library/metadata/{ids}`), so a 200-episode show costs 2
requests.

**History: filtered at the source where possible.**
- Tautulli: `get_history` with `rating_key` (movie or episode) or `grandparent_rating_key` (show),
  `grouping=1`. Both are documented filters of `get_history`.
- Plex: `/status/sessions/history/all` with `metadataItemID`. Checked for a movie, an episode and a
  show (a show's filter returns its episodes' entries). Reading the whole history instead hit the
  20,000-entry cap on a busy server and missed older plays, so the filter matters. Entries are still
  checked against the title in the script. Episode entries carry the show as `grandparentKey`
  (`/library/metadata/123`), not `grandparentRatingKey`.
- Plex history gives account ids, so `/accounts` is read for names, as `watch-activity` does.
- Source choice follows `watch-activity`'s `--source` rules exactly (`auto`, `tautulli`, `plex`,
  `fallback_reason`).

**History problems don't stop the report.** `watch-activity` fails with `OWNER_ONLY` when Plex
refuses history. Here the history is one part of a bigger answer, so the script sets `watching` to
`null` with `watching_unavailable` giving the reason, and still exits 0. `--source tautulli` with
Tautulli failing still fails, as in the other skills, because the user asked for it by name.

**Names are shown.** Like `watch-activity`, this is the server owner's own report, so people's names
appear. Nothing about people beyond name, plays, dates and progress is kept (no emails, ids,
addresses or device identifiers).

## Risks / Trade-offs

- [Collections couldn't be checked on a real server: the test server has none] → The script reads
  Plex's standard `Collection` tags from the details; tests cover it with made-up data.
- [Copied playback rules drift from `playback-check`] → Shared test cases run against both scripts
  (see the testing spec), and the conventions rule about shared helpers covers the copied functions.
- [Long-running shows have big episode lists] → One `allLeaves` request plus detail batches of 100;
  a 1,000-episode show is about 11 requests, still far below a library-wide report.
- [Tautulli and Plex count plays differently] → Tautulli merges a paused and resumed play into one
  row; Plex keeps an entry per finished view. `watching.source` says which was used, and SKILL.md
  tells Claude not to compare the two.

## Open Questions

- Should the summary be included at all, or left to Plex? It's included, cut to 300 characters, since
  "tell me about" questions usually want it.
- Should file paths be shown in full? Yes for now: the owner asked about their own server and paths
  help find files. Revisit if the skill is ever used on a shared server.
