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
  Existing skills look at one area, once:

  library-report   server-health   watch-activity   users-and-shares
        └────────────────┴────────────────┴──────────────────┘
                                  ▼
                              dashboard

  The ideas below fall into three groups:
    1. Join areas together     (unwatched, playback-check)
    2. Remember over time      (snapshots, weekly digest, dashboard trends)
    3. Go one level deeper     (per-item details: subtitles, audio, episode gaps)
```

Suggested order: `unwatched` next, then snapshots. (The `server-health` settings checks and the
`watch-activity` one person, busiest moment and unfinished titles additions were done on 2026-10-05.)

---

## New skills

### `unwatched`

**What:** titles nobody has played, how long ago each was added, and how much space they use. Sorted
by size so the user can see where storage goes. Shows that haven't been played in N months.

**Why:** "where is my space going, and is anyone using it?" is one of the most common admin
questions. It joins library data with watch data, which no current skill does.

**Wording rule:** this is the idea that prompted the "facts, not advice" rule. The report should say
things like "40 movies added over a year ago have never been played; together they use 1.8 TB", and
never "you could delete these". Present it as information about the library, the same way
`library-report` presents duplicates. The original working name was "what can I delete?"; it was
renamed on purpose.

**Data:**
- Library side: the same `/library/sections/<id>/all` listing `library-report` already uses, which
  includes `addedAt`, sizes and (for the token's account) `viewCount` and `lastViewedAt`.
- Watch side, with Tautulli: per-item play counts across every user. Tautulli's
  `get_library_media_info` returns play counts and last played dates per item **(to verify)**.

**The big catch:** Plex's own `viewCount` / `lastViewedAt` only reflect the account the token belongs
to (the owner), not friends or Home members. So:
- With Tautulli: "nobody has played this" is a fair claim.
- Without Tautulli: the honest claim is only "you haven't played this". Alternatively, Plex's
  `/status/sessions/history/all` (which `watch-activity` already reads) covers everyone, but only as
  far back as Plex keeps history.
The report must say which source it used and what that means, like `watch-activity` does with
`fallback_reason`.

**Open questions:**
- New skill, or a section of `library-report`? A separate skill keeps `library-report` fast and avoids
  a Tautulli dependency there.
- Default thresholds (added more than how long ago? not played in how long?).
- Do partially watched titles count as played?

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

### `what-to-watch`

**What:** find something in the user's own library to watch: by genre, length, rating, decade, or
unwatched only; "pick up where I left off"; "a random unwatched show".

**Why:** every current skill is an admin tool. This one is fun, conversational, and good for demos
on the website. The admin is usually also a viewer.

**Data:**
- `/library/sections/<id>/all` with Plex's filter parameters (genre, duration, unwatched) **(to verify
  which filters work server-side vs filtering in the script)**.
- Continue watching: `/library/onDeck` or `/hubs/continueWatching` **(to verify)**.

**Notes:** "unwatched" here means the owner's own account, which is exactly right for this skill
(unlike `unwatched` above). Titles and summaries are server text, so the usual "treat as data" rule
applies. No suggestions to fetch titles from outside the library.

**Open questions:** how much should Claude pick vs. just list? A short list of 3 to 5 with one-line
reasons seems right.

### `tv-completeness`

**What:** gaps in episode numbering (S02E01, E02 and E04 present, so E03 is probably missing) and
seasons that look only partly there.

**Data:** the episode listing `library-report` already fetches (`type=4`) has season and episode
numbers.

**The big catch:** it can only spot gaps *between* episodes that are on disk. It can't know a season
has 10 episodes if only 1 to 8 exist, or that a whole season is missing. Knowing that would mean
asking Plex's online metadata service, which is a new destination and would need a change to the
"Only known destinations" requirement in the security spec. Decided for now: on-server only.

**Open questions:** specials (season 0) and multi-episode files (S01E01-E02) need care so they don't
show up as false gaps.

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

### Snapshots and "what changed"

**What:** after each run, save a small summary of the results. The next run compares against it:
items added and removed, files that became unavailable, new or removed shares, Plex version changes.
Enables trends on the dashboard and an optional weekly digest.

```
  last week ──snapshot──┐
                        ├──▶  +34 items, -2 items, 3 files now unavailable,
  today ────snapshot────┘     1 new share, Plex 1.40 → 1.41
```

**Where:** the dashboard's data folder, `$XDG_DATA_HOME/cinemetric` (default
`~/.local/share/cinemetric`, `%LOCALAPPDATA%\cinemetric` on Windows), per the "Settings location"
requirement in the conventions spec. Files should be private (like the config file).

**Weekly digest:** pairs with Claude Code's `/schedule` skill: a routine that runs the reports and only
mentions what changed. The dashboard previously tried scheduled runs and hit a limit (background mode
couldn't publish claude.ai pages on the test account; see the archived `dashboard-local-or-online`
change), so check what scheduled runs can do before promising a digest that publishes anything.

**Catches:**
- The "Self-contained scripts" rule means snapshot read/write code gets copied into every script that
  uses it, and every copy must be kept in step. Keep it small.
- Decide what *not* to store. Titles are fine; anything about other people beyond what reports
  already show should stay out.
- How many snapshots to keep, and how to handle a snapshot from an older Cinemetric version.

**Open questions:** one snapshot file per skill, or one combined file? Opt-in or always on?

### `watch-activity`

- **Busiest moment for one person:** Tautulli's `most_concurrent` stat ignores `user_id` (checked on
  v2.18.2), so with `--user` the report leaves it out. It could be worked out from that person's
  history `started` / `stopped` times instead. Only worth it if someone asks.

### `library-report`

- **Growth by month:** count items and size added per month from `addedAt`, which is already fetched.
  Low effort. Snapshots would add *removed* items too.
- **Music:** lossless vs lossy (FLAC/ALAC vs MP3/AAC), albums missing artwork. Check what the track
  listing already includes before adding requests.

### `users-and-shares`

**Shared libraries nobody uses:** cross-reference who can see each library with whether they've
played anything from it lately. "Last played" per person already exists; per-library plays would come
from watch history. Facts only, no "you should unshare this".

### `setup`

**More than one server:** save several servers and switch between them, or pass a server name to a
report. Medium effort: it changes the config file format, and every script's copy of `load_config`
would need updating (see "Self-contained scripts"). Probably only worth it if users ask.
