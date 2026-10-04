## 1. Find duplicates in the script

- [x] 1.1 Add a helper that turns an item's `Media` list into counted copies (skip `deletedAt` and `proxyType`; size = sum of parts; keep resolution bucket and video codec)
- [x] 1.2 Build each movie library's `duplicates` section: `titles`, `extra_copies`, `extra_gb`, and per-movie examples with `copies`, largest extra space first
- [x] 1.3 Build each show library's `duplicates` section over episodes, with examples grouped by show (`title`, `episodes`, `extra_gb`)
- [x] 1.4 While summarising each library, record each matched movie's and episode's largest copy by `guid` (skip missing and `local://` guids)
- [x] 1.5 In `build_report`, build the top-level `cross_library_duplicates` from guids seen in two or more libraries: movies one example each with `libraries`; episodes grouped by show and library set
- [x] 1.6 Add `--duplicate-examples N` (default 15, clamped to 0–500) and apply it to every duplicate example list

## 2. Tell Claude about it

- [x] 2.1 `SKILL.md`: add duplicates and multiple versions to the `description` triggers and document `--duplicate-examples` in the run section
- [x] 2.2 `SKILL.md`: list the new fields, add duplicates to "Worth a look" (counts, space, a few examples, why they matter and that many are deliberate), and say to lead with duplicates when that's what the user asked about
- [x] 2.3 `SKILL.md`: say changes are made in Plex (the item's versions menu, or Plex's duplicates filter), never by this skill

## 3. Docs

- [x] 3.1 README: remove the `duplicates` item from Roadmap "Ideas for later"
- [x] 3.2 Website: add duplicates to the library-report feature list in `website/index.html`

## 4. Verify

- [x] 4.1 Unit check with hand-built items: two versions, split file (two parts), unavailable copy, optimized copy, duplicated season, same guid in two libraries, `local://` guids, `--library` limited to one library; numbers match the spec scenarios
- [x] 4.2 Run against a real server (if available) with a known multi-version movie and confirm the listing includes every version; output is valid JSON and existing fields are unchanged (ran against the real server: valid JSON, existing fields unchanged, 0 duplicates, matching Plex's own duplicate filter; no multi-version movie was available to test with, and the user accepted that risk)
- [x] 4.3 Run `dashboard.py` against the new report and confirm the page still builds unchanged
- [x] 4.4 `openspec validate library-report-duplicates` passes

## 5. Release

- [x] 5.1 Bump the version to 0.5.0 in all five scripts, `plugin.json` and `marketplace.json`
