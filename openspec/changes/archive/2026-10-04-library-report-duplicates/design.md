## Context

`library_report.py` reads every movie (`type=1`) and every episode (`type=4`) through
`/library/sections/{id}/all`. Each item comes back with a `Media` list: one entry per version Plex
has grouped under that title, each with a `Part` list (the actual files, usually one, more for a
movie split across files). The `Tally` class already walks this structure for sizes, resolutions and
unavailable files. So everything duplicate detection needs is already in memory; the work is in how
we interpret it.

Plex has two different situations a user would call "duplicates":

1. **Grouped versions.** Plex matched two files to the same title in one library and shows them as
   one item with several versions. This is visible as two or more `Media` entries.
2. **Same title in different libraries.** Plex never groups across libraries, so these are separate
   items. The only link between them is the shared metadata ID (`guid`, such as
   `plex://movie/5d776...`).

## Goals / Non-Goals

**Goals:**
- Report both kinds of duplicate, with a space figure that means something concrete.
- Add no new Plex requests and no meaningful run time.
- Keep the output compact by default but able to list everything on request.

**Non-Goals:**
- Showing duplicates on the dashboard. The data will be there; how to show it (and whether it should
  affect the "Healthy / Mostly fine" status, given many duplicates are intentional) is a follow-up.
- Music. A song appearing on an album and a compilation is a separate track by design, and true
  multi-version tracks are rare. Including music would mostly produce false alarms.
- Finding files that Plex matched to *different* titles but are really the same film (a wrong match).
  That needs file names or fuzzy title matching, and file paths are kept out of reports.
- Recommending which copy to delete. The report gives quality and size per copy; the user decides,
  in Plex.

## Decisions

**Roll into `library-report` instead of a new skill.** The data is already fetched, it's the same
kind of housekeeping as unmatched items and very large files, and the dashboard picks it up
automatically. A separate skill would re-download the whole library and add a sixth copy of the
shared helpers (config loading, URL checks, the Plex client), which the conventions spec requires
keeping in sync by hand. Alternative considered: a standalone `duplicates` skill with a more
detailed view. The `--duplicate-examples` option covers the "show me everything" case without that
cost.

**"Extra" = every copy except the largest.** It answers "how much would I get back if I kept one
copy of each?" with a single, predictable rule. Alternatives: keep the highest *resolution* (needs a
ranking of codecs and resolutions, and ties get messy), or keep the smallest (overstates savings for
someone who'd keep the 4K copy). Largest is simple, and usually the best-quality copy anyway.

**Count copies at the `Media` level, not the `Part` level.** A `Part` is a file; a `Media` entry is a
version. A movie split into `cd1`/`cd2` files is one version with two parts, not a duplicate.

**Skip unavailable and optimized copies.** A `Media` entry with `deletedAt` is a file Plex can't find
any more; it's already reported under unavailable files and isn't using space. A `Media` entry with
`proxyType` is an "optimized version" Plex made itself on purpose (for example a smaller copy for
phones); calling those duplicates would be wrong and the user manages them in a different place in
Plex.

**Cross-library matching uses `guid`, and each library contributes its largest copy.** `guid` is
Plex's own identity for a title, so it avoids guessing from titles and years. Unmatched (`local://`)
items have per-file guids and can't be compared, so they're skipped. Using one copy per library keeps
the two sections from counting the same extra file twice: in-library extras are in that library's
`duplicates`, and cross-library extras are on top of that.

**Group TV examples by show.** A duplicated season produces one row per episode, which would fill the
example list with a single show. Grouping by show (and, for cross-library, by which libraries) keeps
the list readable; the counts still reflect individual episodes.

**Example limit is an option, capped at 500.** 15 matches the other example lists. 500 is generous
for a cleanup session while keeping the JSON a manageable size for Claude to read.

**SKILL.md presentation.** Duplicates go under "Worth a look" with counts, space and a few examples.
When the user asks specifically about duplicates, Claude leads with them and can rerun with a higher
`--duplicate-examples`. Claude should say plainly that cross-library copies and 4K-plus-1080p pairs
are often deliberate, and point to Plex's own "Duplicates" filter and the item's "versions" menu for
making changes.

## Risks / Trade-offs

- [Some Plex versions might not include every `Media` entry in the section listing] → Verify against
  a real server with a known multi-version movie before release; if the listing is incomplete, Plex's
  `duplicate=1` filter on the same path can be used to find which items need a closer look.
- [Large TV libraries mean more work per item] → It's a single pass over data already in memory,
  plus a dictionary keyed by guid; negligible next to the download time.
- [Duplicates on purpose look like problems] → The section is informational; SKILL.md frames it
  that way, and the dashboard (which has a status badge) isn't changed yet.
- [Report JSON grows] → Defaults keep it to 15 examples per section; the bigger lists only appear
  when asked for.

## Migration Plan

Additive only: new fields and a new option, existing fields unchanged, so the dashboard and anything
else reading the JSON keeps working. Rollback is reverting the script and SKILL.md.
