## Why

Duplicates are the last unstarted idea in the Roadmap that fits what Cinemetric already does. Extra
copies of the same movie or episode quietly use a lot of disk space, and Plex doesn't show the total
anywhere. When Plex groups several files under one title, you only see it by opening that title's
"versions" menu; when the same title sits in two libraries (say "Movies" and "4K Movies"), Plex never
connects them at all.

`library-report` already downloads every movie and episode together with all of its files, so it has
everything needed to find duplicates without any extra requests to Plex. Adding it there, instead of
as a separate skill, keeps one place for library housekeeping, avoids a sixth copy of the shared
helper code, and gives the dashboard the numbers for free (it builds its library section by running
`library_report.py`).

## What Changes

- Each movie and TV library in the report gets a `duplicates` section: how many titles have more
  than one copy, how many extra copies there are, how much space the extras use, and the biggest
  examples with each copy's resolution, video codec and size. TV examples are grouped by show so a
  duplicated season shows up as one line, not twenty.
- A new top-level `cross_library_duplicates` section finds the same movie or episode in more than one
  library, matched by Plex's metadata ID, with the same counts and examples.
- "Extra" always means every copy except the largest one, so the space figure is what you'd get back
  by keeping only the biggest copy. Files Plex can no longer find, and Plex's own "optimized
  versions", are not counted as copies.
- A new `--duplicate-examples N` option (default 15) sets how many examples are listed, so someone
  cleaning up can ask for the full list.
- `SKILL.md` learns the new fields, triggers on questions about duplicates or multiple versions, and
  explains that many duplicates are on purpose (a 4K copy plus a smaller one for streaming). It stays
  read-only: it never offers to delete anything.
- README: the `duplicates` Roadmap idea is removed (now done). Website: the library-report feature
  list mentions duplicates.
- Version bump to 0.5.0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `library-report`: "Options" adds `--duplicate-examples`; "Report contents" adds the per-library
  `duplicates` section and the top-level `cross_library_duplicates` section; new requirements define
  how duplicates are found within a library and across libraries.

## Impact

- `plugins/cinemetric/skills/library-report/scripts/library_report.py`: new duplicate-finding code
  and option; no new Plex requests.
- `plugins/cinemetric/skills/library-report/SKILL.md`: description, field list and presentation.
- `README.md` Roadmap and `website/index.html` library-report feature list.
- `VERSION` in all five scripts, `plugin.json` and `marketplace.json`.
- The dashboard is not changed in this change. It will receive the new fields but ignore them until a
  follow-up decides how to show them.
