## Context

`library_report.py` already reads every movie and episode with all of its `Media` entries (versions),
and each version carries a `videoResolution`. The duplicates work added two pieces this change can
reuse:

- `copies(item)`: an item's versions that count (skips files Plex can't find, `deletedAt`, and
  Plex's own optimized versions, `proxyType`), each with its resolution bucket, codec and size.
- A `guids` map built while each library is summarised, used afterwards in `build_report` to find
  the same title in other libraries.

The question "is this worth upgrading?" depends on every library being reported, not just the one
the item is in, because a common setup keeps "Movies" (1080p and below) and "4K Movies" side by side.

## Goals / Non-Goals

**Goals:**
- List titles whose best available copy is SD or 720p, per library.
- Don't list titles the user already has in better quality, whether in the same library (another
  version) or another library.
- No new Plex requests and no meaningful extra run time.

**Non-Goals:**
- Flagging 1080p titles that could be 4K. That's a different, much longer list and a matter of taste;
  it could become an option later (see Open Questions).
- Judging quality beyond resolution (bitrate, codec age, HDR). Resolution is the one signal the
  listing gives reliably; the example's codec and size give the user enough to judge further.
- Music and photos.
- Showing upgrades on the dashboard. As with duplicates, the field is there for a follow-up.
- Finding, downloading or recommending a source for a better copy. The skill stays read-only and
  says nothing about where to get files.

## Decisions

**Roll into `library-report`, not a new skill.** The data is already downloaded, and cross-library
matching already exists. A separate skill would re-download the whole library and add another copy of
the shared helpers. The user chose this.

**"Best copy" means highest resolution, not largest file.** Duplicates use "largest" because the
question there is about space. Here the question is quality, so a 1080p copy beats a bigger 720p
remux. Ranking: SD < 720p < 1080p < 2K < 4K. Unknown or unusual values (empty, `8k`) are unranked:
an item with only unranked copies is not a candidate, since we can't say it's low quality; an item
with a ranked and an unranked copy is judged on the ranked one. The example's codec and size come
from the best-resolution copy (the largest one if two share that resolution).

**Cross-library check is done after all libraries are read.** While summarising a library, the
script keeps its candidates (with their `guid`) and records, for every matched item, the best rank
seen per `guid` per library. In `build_report`, once every library is done, each library's
candidates are filtered: if any *other* library has that `guid` at 1080p or better, the item moves to
`covered_elsewhere`. Then each library's `upgrades` section is finished (counts, sorting, limit).
Alternative considered: a second pass over the libraries. Not needed; the per-guid ranks are small.

This could share the existing `guids` map, but that map stores the *largest* copy per library for the
duplicates calculation. Keeping a separate `best_rank` map (guid → library → rank) avoids changing
duplicates behaviour.

**`--library` limits the cross-library check.** Only libraries in the report are compared, the same
as cross-library duplicates. If the user reports only "Movies", a title that's in "4K Movies" will be
listed. SKILL.md tells Claude to mention this when `--library` was used.

**TV grouped by show.** A 720p series is one row with an episode count and an SD/720p split, ordered
by most episodes first, since that's where an upgrade helps most. Counts still reflect episodes.

**Movie ordering: SD before 720p, then title.** There is no good "importance" signal in the listing
(view counts are per-user and ratings are often missing), so worst quality first, alphabetical within
that, is predictable and easy to scan.

**Separate `--upgrade-examples` option**, default 15 and limited to 0–500, mirroring
`--duplicate-examples`. Reusing that option would be confusing when someone asks for "every
duplicate" and gets 500 upgrade rows too.

## Risks / Trade-offs

- [Plex reports some older DVD rips as `576` or `480`, others as `sd`] → `resolution_bucket` already
  maps all three to SD.
- [A file with wrong resolution metadata (never analysed) has no `videoResolution`] → It's left out
  rather than guessed. SKILL.md can mention that unanalysed files won't appear.
- [Long lists for big older libraries] → Default 15 examples; counts cover the rest; the user can ask
  for more.
- [The report JSON grows] → One small section per video library.

## Migration Plan

Additive only: a new field per library and a new option; existing fields unchanged, so the dashboard
keeps working. Rollback is reverting the script and SKILL.md.

## Open Questions

- Should a later option (for example `--upgrade-below 4K`) let people also flag 1080p titles? Left out
  for now to keep the first version simple; easy to add on top of the rank table.
