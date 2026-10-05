## Why

`quality-upgrades` is one of the two ideas left in the README Roadmap. Most people's libraries have
older files in SD or 720p that have been sitting there for years, and Plex has no simple way to list
them: you can filter one library by resolution, but it won't tell you that a 720p movie in "Movies"
is already in 4K in "4K Movies", and it lists TV episode by episode.

`library-report` already downloads every movie and episode with each version's resolution, and it
already matches titles across libraries for duplicates. So it has everything needed to answer "what's
worth upgrading?" with no extra requests to Plex, which is why this goes into the library report
instead of a new skill.

## What Changes

- Each movie and TV library in the report gets an `upgrades` section: titles whose best copy is SD or
  720p, how many of each, and examples with resolution, video codec and size. TV examples are grouped
  by show so a whole 720p series shows up as one line.
- A title only counts if its *best* copy is low quality. A movie with both a 720p and a 1080p copy is
  not listed, and neither is one that has a 1080p or better copy in another library being reported
  (matched by Plex's metadata ID, the same way cross-library duplicates are found). Those skipped
  because of another library are counted in `covered_elsewhere`.
- Copies Plex can't find on disk and Plex's own "optimized versions" are ignored, matching the
  duplicates rules. Titles whose resolution Plex doesn't know are not listed.
- A new `--upgrade-examples N` option (default 15, limited to 0-500) sets how many examples are listed.
- `SKILL.md` learns the new fields, triggers on questions about low-quality, SD or 720p titles and
  what to upgrade, and stays read-only: it never downloads, searches for or replaces anything.
- README: the `quality-upgrades` Roadmap idea is removed (now done). Website: the library-report
  feature list mentions upgrade candidates.
- Version bump to 0.7.0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `library-report`: "Options" adds `--upgrade-examples`; "Report contents" adds the per-library
  `upgrades` section; a new requirement defines which titles are upgrade candidates.

## Impact

- `plugins/cinemetric/skills/library-report/scripts/library_report.py`: new upgrade-finding code and
  option; no new Plex requests.
- `plugins/cinemetric/skills/library-report/SKILL.md`: description, field list and presentation.
- `tests/test_library_report.py`: new offline tests for the spec scenarios.
- `README.md` Roadmap and `website/index.html` library-report feature list.
- `VERSION` in all five scripts, `plugin.json` and `marketplace.json`.
- The dashboard is not changed. It receives the new field but ignores it, as it does duplicates.
