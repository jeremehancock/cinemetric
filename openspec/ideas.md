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
    1. Join areas together     (playback-check)
    2. Remember over time      (weekly digest, dashboard trends; snapshots are done)
    3. Go one level deeper     (per-item details: subtitles, audio)
```

Suggested order: open. (Snapshots and "what changed" were done on 2026-10-06, and so was
`episode-gaps`, the former `tv-completeness` idea. The `server-health` settings checks, the
`watch-activity` one person, busiest moment and unfinished titles additions, the `unwatched` skill,
`library-report` growth by month with its dashboard chart, and the `what-to-watch` skill were done on
2026-10-05; `library-report` music details (lossless vs lossy, missing artwork) on 2026-10-06. Hi-res
music (bit depth, sample rate) was left out: it isn't in the track listing and needs a request per
track.)

---

## New skills

### `playback-check`

**What:** files across the library that are likely to transcode on common devices, and why:
- image-based subtitles (PGS, VOBSUB), which force Plex to draw subtitles into the video
- TrueHD or DTS audio, which many TVs and streaming sticks can't play directly
- bitrates above the remote streaming limit the server is set to
- with Tautulli: which devices and users transcode most often, from past plays.

**Why:** `server-health` explains transcoding that is happening *right now*. This answers the
follow-up question: "why does this keep happening, and which files will cause it?"

**Data:**
- Subtitle and audio stream details are **not** in the library listing. They come from each title's
  detail page, `/library/metadata/<id>` **(to verify that the listing really lacks them)**. That's one
  request per title.
- The remote streaming limit is in `/:/prefs`, which `server-health` already reads.
- Tautulli history includes the transcode decision per play.

**The big catch:** cost. One request per title means thousands of requests on a big library. Options:
limit to one library at a time, sample (e.g. the 200 largest files), or only check titles added
recently. Snapshots could cache results so later runs only check new titles.

**Open questions:**
- Which device rules are worth encoding, given clients vary a lot? Keep it to the few universal
  causes (image subtitles, lossless audio, bitrate) rather than a device database.
- Should this be part of `server-health` instead of its own skill?

### `year-in-review`

**What:** a yearly recap page: top titles, total hours watched, busiest months, most active people,
favorite genres. Built with the same page machinery as `dashboard`, saved locally and/or as a private
claude.ai page.

**Data:** Tautulli history gives the richest version; Plex's own history works with less detail
(plays only, no watch time), as in `watch-activity`.

**Privacy note:** the security spec's "other people's private details stay private" rule covers
emails, access tokens and account ids, not viewing habits, and `watch-activity` already shows
per-person activity. So this doesn't conflict with a spec. It is still a tone decision: a recap that
singles people out reads differently from a stats report, especially if the page gets shared.

**Open questions:**
- Per-person sections by default, or only when asked?
- Calendar year only, or any date range?
- Could this just be a `dashboard` mode instead of a new skill?

---

## Updates to existing skills

### Weekly digest and dashboard trends (built on snapshots)

Snapshots themselves were done on 2026-10-06 (the `changes` skill, `since_snapshot` in the library,
server and sharing reports, and the dashboard's "Since" section). One file per server per day, kept 90
days, in `<data folder>/snapshots/<server id>/`. See `openspec/specs/changes`.

**Weekly digest:** pairs with Claude Code's `/schedule` skill: a routine that runs
`changes.py --since 7` and only mentions what changed. The dashboard previously tried scheduled runs
and hit a limit (background mode couldn't publish claude.ai pages on the test account; see the
archived `dashboard-local-or-online` change), so check what scheduled runs can do before promising a
digest that publishes anything.

**Trends on the dashboard:** the snapshots already hold per-library counts and sizes for each day, so
a chart of library size or people with access over the last 90 days needs no new data. Reading 90
files on each build is the cost to check.

**Open questions:** should the dashboard's "Since" section compare with about a week ago instead of
the previous day? Should snapshots be opt-out for people who don't want anything saved?

### `watch-activity`

- **Busiest moment for one person:** Tautulli's `most_concurrent` stat ignores `user_id` (checked on
  v2.18.2), so with `--user` the report leaves it out. It could be worked out from that person's
  history `started` / `stopped` times instead. Only worth it if someone asks.

### `setup`

**More than one server:** save several servers and switch between them, or pass a server name to a
report. Medium effort: it changes the config file format, and every script's copy of `load_config`
would need updating (see "Self-contained scripts"). Probably only worth it if users ask.
