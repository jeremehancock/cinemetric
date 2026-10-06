## Context

Every TV episode in Plex carries its season number (`parentIndex`) and episode number (`index`). The
episode listing `/library/sections/<id>/all?type=4`, which `library-report` and `unwatched` already
read, returns these for a whole library in a few pages, along with the show it belongs to
(`grandparentRatingKey`, `grandparentTitle`) and its files (`Media`, with `deletedAt` when Plex can't
find the file). That is everything needed to spot numbers that are missing between the ones present.

What the server can't tell us is how many episodes a season is meant to have. Plex knows that from its
online metadata service, but asking it would be a new network destination and a change to the
security spec's "Only known destinations" rule. Decided on 2026-10-05 (recorded in `ideas.md`) and
again with the user on 2026-10-06: on-server only. The user also chose the name `episode-gaps` over
`tv-completeness`, `missing-episodes` and others, because it promises only what the skill can find,
and chose a separate skill over a section in `library-report`.

## Goals / Non-Goals

**Goals:**
- Per show, list episode numbers that are probably missing, seasons that are missing between others,
  and episodes whose files Plex can't find, compactly enough to read on a big library.
- Avoid the common false gaps: specials, multi-episode files, numbering that carries on across
  seasons, and date-numbered shows.
- Be plain about the blind spot: nothing after the last episode or season on the server is seen.
- Plex only, with paths other scripts already use. Fast: one listing per TV library.
- Show the same facts on the dashboard.

**Non-Goals:**
- Knowing how many episodes a season should have, or that a show has a newer season. That needs
  online metadata (see Context).
- Suggesting downloads, replacements or deletions. The report lists numbers; the user decides.
- Specials (season 0). Their numbering is sparse by nature, so gaps there mean nothing.
- Duplicate episodes and upgrade candidates. `library-report` already covers those.
- Snapshots ("new gaps since last week"). Can be added later if wanted.

## Decisions

**Two listings per TV library, both on an allowed path.** The episode listing (`type=4`) gives the
numbers. The show listing (`type=2`) gives each show's title and year, so two shows with the same
title (a remake and the original) stay apart and can be told apart in the report. Both use
`/library/sections/<id>/all`, in pages of 500. Episodes are grouped by `grandparentRatingKey`, not by
title. Alternative: only the episode listing and the show's title from `grandparentTitle`. That saves
one request per library but loses the year. The cost is tiny, so both are read.

**What counts as "there".** An episode number is there when at least one episode with that season and
number has a file Plex can find (a `Media` without `deletedAt`). Two copies of the same episode count
once. An episode whose every file is unavailable is not there; its number is reported under
`unavailable`, not `missing`, because the cause is different (the file went away, rather than never
being added) and so is what the owner might check.

**Gaps inside a season.** For each season numbered 1 or higher, every number between the lowest and
highest number there that is neither there nor unavailable is `missing`. Missing numbers are reported
as ranges (`[3, 3]`, `[5, 7]`) so a season with many gaps stays short.

**Seasons that start late.** If a season's lowest number is above 1, the numbers from 1 up to it are
missing too, with one exception: if the season's lowest number is exactly one more than the highest
number in the season before it (season 1 ends at E12 and season 2 starts at E13), the show numbers
its episodes straight on across seasons, and nothing before the start is reported. The season is
marked `continues_numbering`. Alternative considered: treat any season starting above the previous
season's highest number as carrying on. That would hide a real late start whenever the previous
season was short (season 1 has E01 to E03, season 2 has E05 to E10). The strict rule can still report
a false late start when a carried-on season is also missing its first episode; SKILL.md mentions it.

**Missing seasons.** Season numbers between the lowest and highest season the show has (season 0
excluded) that have no episode there or unavailable are `missing_seasons`. Seasons before the first
one present are not: the show's `first_season` records where it starts, and the library counts
`shows_starting_later`, but that alone doesn't make the show "have gaps". The first plan counted them
as missing, like late-starting episodes. The confirmation step showed why not: on the owner's server,
92 of 103 missing seasons came from three long-running shows that only keep their latest seasons
(for example 35 to 40), which is a choice, not a gap. Decided with the user on 2026-10-06. Late
starts inside a season still count, since a season usually is collected whole.

**Multi-episode files.** On the owner's server Plex lists a file named `S01E01-02` as one episode
(numbered 1), not as two episodes sharing the file, so without help E02 would look missing. The
script reads the file name (the last part of the path, never printed) for a season and episode
followed by more episode numbers: `S01E01-E02`, `S01E01-02`, `S01E01E02`, `S01E01-E02-E03`. Every
number from the first to the last counts as there for that season, but only when the first number is
the episode's own number, and never when a number runs into `p` or `i` (`S01E01-1080p`). The file
path is only read in memory to find these numbers.

**Date-numbered shows.** Daily and talk shows are often numbered by date: season 2023, episode
20231005, or episodes with no number at all. A season numbered above 999, or with an episode numbered
above 999, is not checked for gaps; it's counted in `seasons_not_checked`. Missing seasons are only
worked out from seasons numbered 1 to 999, so a show with seasons 1999 and 2023 doesn't report 23
missing seasons. Episodes with no season or episode number are counted in `unnumbered` and otherwise
ignored. 999 is a guess that leaves room for long-running shows numbered straight on; the
confirmation step checks it against the real server.

**Which shows are listed.** A show is listed when it has at least one missing episode, unavailable
episode or missing season. Listed shows are sorted by missing plus unavailable episodes, then missing
seasons, then title, and `--limit N` (default 25, 0 to 500) caps how many are listed per library.
Counts for the library (`shows`, `episodes`, `shows_with_gaps`, `missing_episodes`,
`unavailable_episodes`, `missing_seasons`) always cover every show, and `more_shows` says how many
weren't listed. `--limit 0` gives counts only.

**`--show TEXT`** keeps only shows whose title contains the text (case-insensitive), for "is anything
missing from The Wire?". No match isn't an error: the report has zero shows, and SKILL.md says so.

**Dashboard runs `episode_gaps.py --limit 10`.** Each library lists its 10 shows with the most gaps,
so the 10 with the most overall are always among them. The section mirrors the Unwatched section: a
total line (shows with gaps, missing and unavailable episodes, missing seasons), each TV library's
counts, the 10 shows with the most missing plus unavailable episodes across libraries, and the
report's `limits` note in small print. Each show's ranges are written out ("S02E03, S02E05 to E07"),
up to 5 per show and then "and N more", so one badly gapped show can't fill the page. The section is
facts only, isn't added to "Needs a look", doesn't change the overall status, and has no people's
names, so hiding names doesn't affect it. It also isn't in the dashboard's snapshot, for the same
reason snapshots are a non-goal above. Decided with the user on 2026-10-06 (it was first left out).

**Shared helpers copied.** Per the conventions, `load_config`, `validate_url`, `PlexClient` and
`clean` are copied from `what_to_watch.py`, which also contacts only Plex. `tests/helpers.py`'
`SCRIPTS` list gets the new script so the cross-script security tests cover its copies.

**What the confirmation step found (owner's real server, 2026-10-06).** Only shapes, counts and
timings were printed.
- One TV library: 417 shows, 19,008 episodes. Every episode has `parentIndex`, `index`,
  `grandparentRatingKey` and a part `file`; every show has a `year`. Reading both listings took about
  10 seconds.
- No file is shared by two episodes. 41 file names hold a range (40 `E01-02` style, one covering 33
  episodes); with the pattern above all 41 are found, all start at the episode's own number, and no
  other file name matches.
- No episode is numbered above 70 and none lacks a number. 284 episodes sit in 16 year-numbered
  seasons of one show, with no gaps inside them, so leaving those seasons unchecked loses nothing.
- No season continues the previous season's numbering. 7 seasons start late. With the rules above:
  10 shows with gaps, 90 missing episodes, 11 missing seasons in one show, and 3 shows starting
  later. No unavailable episodes at the time.

## Risks / Trade-offs

- [Missing episodes at the end are invisible] → A season with E01 to E08 of 10 looks complete, and
  so does a show missing its newest season. The report carries a fixed `limits` note, and SKILL.md
  says it every time, including when nothing is found ("no gaps between the episodes you have", never
  "complete").
- [Plex's episode ordering setting changes the numbers] → A show set to DVD or absolute order in Plex
  is numbered that way, so gaps follow that order. SKILL.md mentions it when a show's gaps look odd.
- [Wrongly matched episodes] → An episode matched to the wrong number creates a gap and hides
  another. The report can't tell; SKILL.md suggests checking the show in Plex if a gap looks wrong.
- [Strict carry-on rule] → See "Seasons that start late". Rare, and visible as an obviously large late
  start in a show where the previous season ends just below.
- [The dashboard reads the episode list three times] → `library_report.py`, `unwatched.py` and
  `episode_gaps.py` each list every episode. They run side by side, so the build takes about as long
  as the slowest, but Plex does the listing work three times. Acceptable for a manual refresh; the
  confirmation step times it.
- [Very large libraries] → The episode listing is already read in full by other scripts; tens of
  thousands of episodes is under a hundred pages.

## Migration Plan

Additive: a new skill and script. Rollback is removing the skill folder and the doc edits.

## Open Questions

- Is 999 the right line for date-numbered seasons and episodes? Checked against the real server in
  the first task group; adjust before writing tests if it misfires.
- Should a later change add an opt-in online lookup for missing final episodes and seasons? That would
  need its own security spec change and is out of scope here.
