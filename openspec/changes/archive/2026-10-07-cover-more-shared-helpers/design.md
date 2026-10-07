## Context

`tools/shared_helpers.py` lists the shared helpers whose copies must match, and
`tests/test_shared_helpers.py` fails when they don't. A full comparison of every top-level name that
appears in more than one script sorted the rest into three groups: helpers that drifted, helpers
that match but aren't listed, and helpers that only share a name.

## Goals / Non-Goals

**Goals:**
- Every helper that does the same job in several scripts is either listed (and so checked) or listed
  as allowed to differ, with the reason.
- Drifted copies are lined up without changing any report's output for real data.

**Non-Goals:**
- Making same-name helpers with different jobs match (`hours`, `check`, `need_plex`,
  `choose_sections`, `HISTORY_CAP`, the dashboard and recap page builders, `write_private`, ...).
- Checking the TypeScript mods in `hooks/`.

## Decisions

**Pick the most permissive version when lining up.** For `as_bool` the `server-health` copy accepts
everything the others did, plus `yes` and surrounding spaces, so no value that was true becomes false.
For `get_all` the copy with optional extra filters sends the same request when no filters are given.
For `day` the `show-progress` copy also treats negative times (Plex's "never") as no date.

**Allow a different copy where the job really differs**, with the reason in the list:
`users-and-shares`' `day` (times already whole seconds, no `as_int` in that script),
`what-to-watch`'s `as_float` (missing ratings stay unknown instead of 0), `year-in-review`'s
`tautulli_person` (also returns the key recaps use to tell people apart) and
`subtitles-and-languages`' `check_file` (checks languages, not playback).

**Name the same-name, different-job helpers in the tool.** A short `DIFFERENT_JOBS` note in
`tools/shared_helpers.py` lists them, so a later comparison doesn't flag them as drift. It is only a
note; nothing checks it.

## Risks / Trade-offs

- [`as_bool` accepts more values in three scripts] → Plex sends `0`, `1`, `true` or `false` for
  these fields; `yes` and spaces never appear in real replies, so reports don't change.
- [A longer list makes harmless edits fail the test] → The failure names the fix:
  `python3 tools/shared_helpers.py copy NAME --from SKILL`.
