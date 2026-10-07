## Context

`check_library` in `subtitles_and_languages.py` reads every episode in a TV library from the episode
listing (`/library/sections/{id}/all?type=4`), reads each episode's tracks from the detail listing,
and groups flagged episodes into one entry per show. Each entry only keeps counts
(`episodes_flagged`) and the main audio languages, so which episodes were flagged is lost. The episode
listing items already carry `parentIndex` (season), `index` (episode) and `originallyAvailableAt`.

## Goals / Non-Goals

**Goals:**
- Say which episodes of each listed show have each finding, compactly enough that a show with
  hundreds of flagged episodes doesn't swamp the output.
- Handle episodes with no numbers and episodes with several versions without misleading the user.

**Non-Goals:**
- Changing movie entries, the findings themselves, the counts or the sorting.
- Listing every flagged episode across a whole library as its own list (episodes stay grouped under
  their show, and `--limit` still caps the shows).
- Reading file names to guess numbers for unnumbered episodes (episode-gaps does that for two-episode
  files; here the listing's numbers are enough).

## Decisions

**Ranges per season, not one entry per episode.** A show with 22 flagged episodes in a row becomes one
range. Alternatives: a flat list of `S01E04` strings (simple, but can run to hundreds of entries per
show) or preformatted text like "S01E01 to E10" (saves Claude work but fixes the wording in the
script, while the other skills leave wording to SKILL.md). Structured `[first, last]` pairs match what
episode-gaps already outputs for missing episodes.

**Reuse episode-gaps' `ranges`.** It turns whole numbers into `[first, last]` pairs. Copy it as is and
add `"ranges": {}` to `SHARED` in `tools/shared_helpers.py`, so the existing test keeps the two copies
the same. The dashboard's `number_ranges` does the same job under another name and also drops
non-numbers; folding it in is a separate cleanup and isn't needed here.

**Collect numbers while grouping.** In the loop that already builds each show entry, record each
flagged episode as `(season, number)` when both are whole numbers, or as an unnumbered episode with its
title and air date. Keep a set per show per finding so an episode listed twice counts once in the
numbers. Record whether the episode had more checked files than flagged ones (`some_versions`). After
the loop, when building `listed`, turn each show's sets into the season entries and apply the caps.
This only runs for shows that make it into `listed`, though doing it for all is cheap too.

**Caps: 30 ranges and 10 unnumbered episodes per show per finding.** 30 ranges covers any normal
show (a fully flagged 30-season show is 30 ranges) while bounding the worst case (alternating
episodes). The leftover counts (`ranges_more`, `unnumbered_more`) are numbers of episodes, which is
what a user can act on ("and 20 more episodes"). Numbers of episodes cut by the cap are dropped from
`some_versions` too, so it never names an episode the ranges don't show.

**Season 0 sorts first.** That's Plex's own order and keeps the rule simple (plain numeric sort).
SKILL.md calls it "Specials".

**SKILL.md decides what to show.** The script always gives numbers for all three findings. SKILL.md
tells Claude to show them by default under foreign audio with no subtitles (usually a short list the
user acts on) and for the other two findings only when the user asks for the list or for episodes,
written like "S01E01 to E04, S01E06, S03E02".

## Risks / Trade-offs

- [Bigger JSON for large libraries] → ranges plus the per-show caps bound each entry, and `--limit`
  still bounds the number of shows.
- [Wrong or missing numbers in Plex make the ranges wrong] → the report goes by Plex's numbers, like
  every other skill; unnumbered episodes are named by title and air date instead of being dropped.
- [`some_versions` could confuse] → it's only set when an episode really has another checked version
  without the finding, and SKILL.md explains it in one phrase ("one version of S02E05").
