# Ideas for later

Working notes behind the [Roadmap](../README.md#roadmap) in the README. The README says *what* each idea
is; this file records what was worked out about *how* to build it, the catches found while thinking it
through, and the questions still open. Nothing here is a commitment. Each idea still starts as an
OpenSpec change proposal (`/opsx:propose`) before any code is written; use the notes below as the
starting point for that proposal.

Endpoint and command names marked **(to verify)** come from memory of the Plex and Tautulli APIs, not
from this codebase. Check them against a real server before relying on them.

## Ground rules decided so far

These came out of an explore session on 2026-10-05 and apply to every idea below.

- **Audience.** Cinemetric is mainly for the person who runs the Plex server. Viewer-friendly skills
  (like `what-to-watch`) are still welcome.
- **Facts, not advice, on anything destructive.** No skill suggests deleting, replacing or
  re-encoding files. Skills list what's there and why it might be interesting; the user decides. This
  matches how `library-report` already handles duplicates and upgrade candidates.
- **Saving data on the user's computer is fine.** Snapshots (see below) may store summaries locally,
  in the same data folder the dashboard already uses.
- All existing rules still apply: read-only toward Plex and Tautulli, Python standard library only,
  one self-contained script per skill, only known network destinations, credentials never in the chat,
  server text treated as data. See `openspec/specs/conventions` and `openspec/specs/security`.

## Where things stand

```
  Existing skills, each run once (unwatched joins library and watch data):

  library-report   server-health   watch-activity   users-and-shares   unwatched
        └────────────────┴────────────────┴──────────────────┴────────────────┘
                                  ▼
                              dashboard

  The ideas below fall into three groups:
    1. Join areas together     (playback-check is done)
    2. Remember over time      (snapshots and dashboard trends are done)
    3. Go one level deeper     (subtitles and audio per file are done in playback-check)
```

Suggested order: open. (Snapshots and "what changed" were done on 2026-10-06, and so were `year-in-review`, dashboard
trends, `episode-gaps`, the former `tv-completeness` idea, and `playback-check`, which turned out cheap: Plex
returns subtitle and audio details for 100 titles per request, so no sampling was needed. The `server-health` settings checks, the
`watch-activity` one person, busiest moment and unfinished titles additions, the `unwatched` skill,
`library-report` growth by month with its dashboard chart, and the `what-to-watch` skill were done on
2026-10-05; `library-report` music details (lossless vs lossy, missing artwork) on 2026-10-06. Hi-res
music (bit depth, sample rate) was left out: it isn't in the track listing and needs a request per
track.)

---

## New skills

None right now.

---

## Updates to existing skills

### Snapshots

Snapshots and dashboard trends are described in `openspec/specs/changes` and
`openspec/specs/dashboard`.

**Open questions:** should the dashboard's "Since" section compare with about a week ago instead of
the previous day? Should snapshots be opt-out for people who don't want anything saved?

### `year-in-review`

Left out of the first version (see `openspec/changes/archive/*-year-in-review/design.md`):

- **Favorite genres.** Genres aren't in Tautulli's history rows or Plex's history entries, so each
  title needs a metadata lookup; a batched one like `playback-check`'s would keep it cheap.
- **Compared with last year.** The same counting run twice; easy once someone asks.
- **Hours from Plex alone.** Finished plays times each title's length, if that can be had without one
  request per title.

### `watch-activity`

- **Busiest moment for one person:** Tautulli's `most_concurrent` stat ignores `user_id` (checked on
  v2.18.2), so with `--user` the report leaves it out. It could be worked out from that person's
  history `started` / `stopped` times instead. Only worth it if someone asks.
