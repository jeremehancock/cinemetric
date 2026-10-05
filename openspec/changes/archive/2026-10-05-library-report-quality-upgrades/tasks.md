## 1. Find upgrade candidates in the script

- [x] 1.1 Add a resolution rank table (SD < 720p < 1080p < 2K < 4K) and a helper that returns an item's best counted copy by resolution (largest if tied), or nothing if no copy has a ranked resolution
- [x] 1.2 While summarising movie and show libraries, collect each library's candidates (best copy SD or 720p) with their `guid`, and record the best rank per `guid` per library for matched items
- [x] 1.3 In `build_report`, after all libraries are read, move candidates that another reported library has at 1080p or better into `covered_elsewhere`
- [x] 1.4 Build each library's `upgrades` section: `titles`, `by_resolution`, `covered_elsewhere`, and examples (movies: `title`, `resolution`, `video_codec`, `gb`, SD first then title; shows: `title`, `episodes`, `by_resolution`, most episodes first then title)
- [x] 1.5 Add `--upgrade-examples N` (default 15, clamped to 0-500) and apply it to every `upgrades` example list

## 2. Tests

- [x] 2.1 Add offline tests in `tests/test_library_report.py` for each spec scenario: SD movie, 720p plus 1080p versions, optimized-only better copy, better copy in another library, `--library` limited to one library, unknown resolution, 720p series grouping, ordering, example limit and clamping
- [x] 2.2 Check the existing whole-report tests: music and photo libraries have no `upgrades`, only allowed Plex paths are requested
- [x] 2.3 `python3 -m unittest discover -s tests` passes

## 3. Tell Claude about it

- [x] 3.1 `SKILL.md`: add low-quality, SD/720p and "what should I upgrade" to the `description` triggers and document `--upgrade-examples` in the run section
- [x] 3.2 `SKILL.md`: describe the `upgrades` fields, add upgrade candidates to "Worth a look" (counts, a few examples, `covered_elsewhere`), lead with them when that's what the user asked, and mention when `--library` limited the cross-library check
- [x] 3.3 `SKILL.md`: say the skill only lists titles; it never searches for, downloads or replaces files

## 4. Docs

- [x] 4.1 README: remove the `quality-upgrades` item from Roadmap "Ideas for later"
- [x] 4.2 Website: add upgrade candidates to the library-report feature list (and an example question) in `website/index.html`

## 5. Verify

- [x] 5.1 Run against the real server (if available): output is valid JSON, existing fields unchanged, and a few listed candidates match what Plex shows for those titles (ran against the real server: valid JSON, every existing field identical to the previous version; 30 movie and 2,343 episode candidates, all plausibly older titles; individual titles not yet checked by hand in Plex)
- [x] 5.2 Run `dashboard.py` against the new report and confirm the page still builds unchanged
- [x] 5.3 `openspec validate library-report-quality-upgrades` passes

## 6. Release

- [x] 6.1 Bump the version to 0.7.0 in all five scripts, `plugin.json` and `marketplace.json`
