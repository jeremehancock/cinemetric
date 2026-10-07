## 1. Shared helper

- [x] 1.1 Copy `ranges` from `episode_gaps.py` into `subtitles_and_languages.py` unchanged
- [x] 1.2 Add `"ranges": {}` to `SHARED` in `tools/shared_helpers.py` and confirm
      `python3 tools/shared_helpers.py` reports no differences

## 2. Script

- [x] 2.1 Add caps `MAX_RANGES_PER_SHOW = 30` and `MAX_UNNUMBERED_PER_SHOW = 10`
- [x] 2.2 In `check_library`, for each flagged episode in a TV library, record its season and episode
      number (both whole numbers) or, when either is missing, its cleaned title and `aired` date
      (`originallyAvailableAt` when it is `YYYY-MM-DD`, else `null`); record `some_versions` when the
      episode has more checked files than flagged ones; ignore repeats of the same season and number
- [x] 2.3 When building `listed`, turn each show's records into `seasons` (season order, ranges via
      `ranges`, `some_versions` per season), `ranges_more`, `unnumbered` and `unnumbered_more`,
      applying both caps and dropping capped-out numbers from `some_versions`
- [x] 2.4 Make sure the new fields only use internal sets while counting and are plain lists in the
      JSON output, and that movie entries are unchanged

## 3. Tests and fixture

- [x] 3.1 Build test shows from the fixture (a `one_show` helper in the tests) with unnumbered
      episodes, air dates and two-version episodes where one version is flagged, so the fixture's
      existing counts stay the same
- [x] 3.2 Tests for each scenario in the delta spec: two seasons of ranges, one version fine,
      unnumbered episode, 30-range cap with `ranges_more`, every episode flagged, specials first,
      duplicate episode counted once, and the updated "show with some foreign episodes" case
- [x] 3.3 Check no file paths appear in the new fields (existing no-paths test still passes)
- [x] 3.4 Run the full test suite

## 4. SKILL.md

- [x] 4.1 Describe `seasons`, `ranges_more`, `unnumbered`, `unnumbered_more` and `some_versions` in
      section 3's field list
- [x] 4.2 Under "Foreign audio with no subtitles", show each show's episodes by default, written like
      "S01E01 to E04, S01E06, S03E02", season 0 as "Specials", unnumbered episodes by title and air
      date, "one version of S02E05" for `some_versions`, and "and N more episodes" for the caps
- [x] 4.3 Under "No subtitles in your language" and "Language not set", give the episodes only when
      the user asks for the list or the episodes, and say they can ask

## 5. Release

- [x] 5.1 Bump the version in every script's `VERSION`, `plugin.json` and `marketplace.json`
- [x] 5.2 Run the full test suite again and run the skill against a real server to check the output
