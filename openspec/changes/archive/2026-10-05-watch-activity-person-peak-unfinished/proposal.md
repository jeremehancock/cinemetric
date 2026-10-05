## Why

Three common watch questions can't be answered well today: "what has Sam watched lately?", "how many
streams does my server have to handle at its busiest?" and "what did people start but never finish?".
The data for all three is already in the history `watch-activity` reads (or one small step away), so
they fit in one change and finish the `watch-activity` line on the README roadmap.

## What Changes

- **One person** (`--user NAME`): the whole report narrows to one person: totals, top lists, daily
  counts, trend, recent plays, what they're watching now and their unfinished titles. (Their busiest
  moment isn't available: Tautulli only counts streams at once for the whole server.) Names are
  matched without caring about upper or lower case, first exactly, then by a part of the name if only
  one person matches. No match, or more than one, stops with a clear error that lists the names it
  knows (`USER_NOT_FOUND`, `USER_AMBIGUOUS`). The report gains a `user` field (the matched name, or
  `null` for everyone).
- **Most streams at once**: `most_concurrent_streams` (Tautulli only, already there) also reports the
  most transcodes at once and when, since transcodes are the streams that work the server hardest.
  With Plex as the source it stays `null`, and a new `most_concurrent_streams_unavailable` field says
  why (Plex's history only records when a play was logged, not when it started and stopped).
- **Started but never finished**: a new `unfinished` list of movies and episodes someone started in
  the period but didn't finish, each with who, how far they got and when they last played it, plus
  `unfinished_count`. Tautulli only: Plex's own history only records finished plays, so with Plex
  `unfinished` is `null` and `unfinished_unavailable` says why.
- One new read-only Tautulli command, `get_users`, to look up a person by name.
- `SKILL.md`: when to use `--user`, the two new errors, and how to present the new sections (facts
  only, no comments on anyone's habits).
- README roadmap: remove the finished `watch-activity` item. `openspec/ideas.md`: drop the
  `watch-activity` notes.

No breaking changes: every existing field keeps its meaning, and without `--user` the report covers
everyone as before.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `watch-activity`: "Sources used" gains the `get_users` Tautulli command; "Options" gains `--user`;
  "Report contents" and "Differences between sources" gain `user`, the transcode peak,
  `most_concurrent_streams_unavailable`, `unfinished`, `unfinished_count` and
  `unfinished_unavailable`; new requirements for choosing one person, the person filter, and
  unfinished titles.

## Impact

- `plugins/cinemetric/skills/watch-activity/scripts/watch_activity.py`: new option, `get_users` in
  `TAUTULLI_COMMANDS`, paged Tautulli history read for unfinished titles, person filtering in both the
  Tautulli and Plex paths and in current sessions.
- `plugins/cinemetric/skills/watch-activity/SKILL.md`: argument hint, errors, report sections.
- `tests/test_watch_activity.py` and `tests/fixtures/watch-activity/tautulli.json`: new samples and
  tests.
- `README.md`, `website/index.html`, `openspec/ideas.md`: docs.
- Version bump in every script, `plugin.json` and `marketplace.json`.
- `dashboard` is unchanged: it doesn't pass `--user` and ignores fields it doesn't know.
- Speed: the unfinished list reads the period's movie and episode history from Tautulli in pages.
  Capped at 20,000 rows, like the Plex history read.
