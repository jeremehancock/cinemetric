## Why

The Roadmap lists "`server-health`: failed or stuck tasks" as an unfinished part of an existing skill.
Failed tasks can't be detected: Plex only records failures in its log files, and those contain private
details (user names, IP addresses, file paths and possibly tokens) that Cinemetric's security rules
keep out of its reports. Stuck tasks are different. `/activities`, which the script already reads,
gives each running task's progress, so checking it twice a short time apart shows whether a task is
moving. That covers the most useful half of the item with no new Plex paths and no private data, and
it's as far as this item is planned to go, so the Roadmap entry can be closed.

## What Changes

- When a background task is running, the script checks `/activities` a second time after a short wait
  (15 seconds by default) and records, for each task, whether its progress moved.
- A task that is still running with the same progress is flagged in `worth_a_look` as
  `task_not_progressing`. It is worded as "possibly stuck", never as a failure, because some tasks
  legitimately sit at one percentage for a while (for example while scanning a very large folder).
- If nothing is running, there is no second check and no wait, so the report is as fast as today.
- A new `--stuck-wait SECONDS` option sets the wait (default 15, at most 300); `0` turns the check off.
- The dashboard runs `server_health.py` with `--stuck-wait 0`, because it doesn't show the result and
  shouldn't be slowed down for it.
- If the second check fails, the report still succeeds: the stuck check is listed in `unavailable`
  and nothing is flagged.
- `SKILL.md` explains the new flag in plain words, says the report takes about 15 seconds longer when
  a task is running, and keeps saying that failed tasks can't be seen.
- README: the "`server-health`: failed or stuck tasks" Roadmap item is removed, along with the now
  empty "Unfinished parts of existing skills" heading. Website: the server-health feature list
  mentions tasks that look stuck.
- Version bump to 0.6.0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dashboard`: "Built from the other report scripts" says `server_health.py` runs with
  `--stuck-wait 0`.
- `server-health`: "Options" adds `--stuck-wait`; "Partial results instead of failure" adds the stuck
  task check as an optional part; "Things worth a look" adds `task_not_progressing`; a new requirement
  defines how the two samples are compared.

## Impact

- `plugins/cinemetric/skills/server-health/scripts/server_health.py`: second `/activities` sample,
  comparison, new option and new `worth_a_look` kind. No new Plex paths (`/activities` is already
  allowed).
- `plugins/cinemetric/skills/server-health/SKILL.md`: option, new field and presentation.
- `tests/test_server_health.py` and its fixtures: cover moving, stuck, finished and no-progress tasks,
  the option, and a failed second sample. The wait is replaced in tests so they stay fast.
- `README.md` Roadmap and `website/index.html` server-health feature list.
- `VERSION` in all five scripts, `plugin.json` and `marketplace.json`.
- `plugins/cinemetric/skills/dashboard/scripts/dashboard.py`: passes `--stuck-wait 0` to
  `server_health.py`, so dashboard builds are never slowed by the check. Nothing else in the dashboard
  changes; it already ignores `worth_a_look` kinds it doesn't know.
