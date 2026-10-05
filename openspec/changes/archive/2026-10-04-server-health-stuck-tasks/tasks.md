## 1. Check tasks twice in the script

- [x] 1.1 Add a small `pause(seconds)` helper around `time.sleep` so tests can replace it
- [x] 1.2 Keep each activity's `uuid`, raw progress and `subtitle` from the first `/activities` sample so it can be compared (the printed `running_now` fields stay as they are)
- [x] 1.3 If any task has a progress value and `--stuck-wait` is above 0, pause and read `/activities` again as the optional part "stuck task check"
- [x] 1.4 Match tasks by `uuid` (or type and title when there's no `uuid`) and set `progress_moved` to `true`, `false` or `null` as the spec says; ignore tasks that only appear in the second sample
- [x] 1.5 Add `task_not_progressing` to `worth_a_look` with each task's title and progress and `seconds_between_checks`
- [x] 1.6 Add `--stuck-wait SECONDS` (default 15, limited to 0–300)

## 2. Tell Claude about it

- [x] 2.1 `SKILL.md`: document `--stuck-wait`, the new `progress_moved` field, and that the report takes about 15 seconds longer when a task is running
- [x] 2.2 `SKILL.md`: explain `task_not_progressing` under "Worth a look" as "possibly stuck" (may just be slow or waiting to start; check again in a few minutes or with a longer wait), never as failed
- [x] 2.3 `SKILL.md`: update the "What the script cannot see" rule so it still says failures can't be seen, while allowing "possibly stuck" when `progress_moved` is `false`
- [x] 2.4 `SKILL.md`: say that if the user wants a surer answer about a task, run again with a longer wait such as `--stuck-wait 60`

## 3. Dashboard

- [x] 3.1 `dashboard.py`: pass `--stuck-wait 0` to `server_health.py` in `SOURCES`

## 4. Docs

- [x] 4.1 README: remove the "`server-health`: failed or stuck tasks" Roadmap item and the now empty "Unfinished parts of existing skills" heading
- [x] 4.2 Website: mention tasks that look stuck in the server-health feature list in `website/index.html`

## 5. Verify

- [x] 5.1 Tests in `tests/test_server_health.py` with the pause replaced: nothing running (no wait, one request), task moving, same progress but new detail text, task not moving (flagged), task finished during the wait, `--stuck-wait 0`, out-of-range wait clamped, second request fails (listed in `unavailable`, nothing flagged)
- [x] 5.2 Existing tests still pass, including the allowed-paths test: `python3 -m unittest discover -s tests`
- [x] 5.3 Run against a real server (if available) while a scan is running; output is valid JSON and existing fields are unchanged (no scan was running; the server had a Live TV recording and three DVR "Refreshing Sub" tasks, which led to skipping DVR and Live TV tasks. After that: valid JSON, existing fields unchanged, no false alarm, no wait)
- [x] 5.4 Test in `tests/test_dashboard.py` that `server_health.py` is run with `--stuck-wait 0`
- [x] 5.5 `openspec validate server-health-stuck-tasks` passes

## 6. Release

- [x] 6.1 Bump the version to 0.6.0 in all five scripts, `plugin.json` and `marketplace.json`
