## Why

The subtitles-and-languages report lists each TV show with a count of affected episodes ("Squid Game:
9 of 22 episodes, Korean audio") but not which episodes they are. To fix the files, the user has to
open every episode of the show to find the 9. The script already reads each episode's season and
episode number, so it can say which ones are affected.

## What Changes

- Each show listed under a finding in a TV library gains the season and episode numbers of its
  flagged episodes, grouped into ranges per season (season 1, episodes 1 to 10 and 12), so a show
  with hundreds of flagged episodes stays short.
- Episodes Plex has no season or episode number for are listed by title and air date instead,
  up to a fixed number per show, with a count of the rest.
- When an episode has more than one version and only some of them have the finding, the episode is
  marked, so the user knows another version of it is fine.
- The number of ranges given per show is capped, with a count of what was left out.
- The script gives the numbers for all three findings. SKILL.md has Claude show them by default for
  foreign audio with no subtitles, and for the other two findings only when the user asks for the
  list or the episodes.
- The episode-gaps script's `ranges` helper (whole numbers to `[first, last]` ranges) is copied into
  this script and registered as a shared helper so the copies stay the same.
- Movie libraries are unchanged.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `subtitles-and-languages`: a new "Episode numbers for listed shows" requirement (the ranges, the
  fallback for unnumbered episodes, the mark for partly flagged episodes and the caps), and "Report
  contents" names the new fields on each listed show.

## Impact

- `plugins/cinemetric/skills/subtitles-and-languages/scripts/subtitles_and_languages.py`: keep each
  flagged episode's numbers and add them to the show entries.
- `plugins/cinemetric/skills/subtitles-and-languages/SKILL.md`: describe the new fields and when to
  show them.
- `tools/shared_helpers.py`: register `ranges`.
- `tests/test_subtitles_and_languages.py` and `tests/fixtures/subtitles-and-languages/plex.json`: new
  cases for ranges, unnumbered episodes, partly flagged episodes and the caps.
- Version bump in every script, `plugin.json` and `marketplace.json`.
- No new Plex requests: the numbers come from the episode listing the script already reads.
