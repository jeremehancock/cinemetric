## Context

`server_health.py` reads `/activities` once and lists each running task with its progress in
`background.running_now`. `SKILL.md` tells Claude not to claim anything failed or got stuck, because
the data can't show it. Plex has no API that reports task failures or stuck tasks. Its log files do,
but logs contain user names, IP addresses, file paths and possibly tokens, which the security spec
keeps out of every report. The README Roadmap carries "failed or stuck tasks" as unfinished, and this
change is meant to close it.

## Goals / Non-Goals

**Goals:**
- Report, for each running task, whether it made visible progress over a short window.
- Flag tasks that didn't, in words that say "possibly stuck", not "failed".
- Add no new Plex paths, no new private data, and no wait when nothing is running.

**Non-Goals:**
- Detecting failed tasks, or anything that needs Plex's logs.
- Tracking tasks across separate runs (no saved state between reports).
- Showing the result on the dashboard. It ignores `worth_a_look` kinds it doesn't know.

## Decisions

### Two samples in one run, not saved history
The script waits and reads `/activities` again in the same run. *Alternative considered:* saving the
last sample to a file and comparing on the next run. Rejected: runs can be days apart, so "didn't
move" would mean nothing, and it would add a state file to a skill that has none today.

### Only wait when there's something to watch
The wait happens only when the first sample has at least one task with a progress value. Most health
checks run while nothing is happening, so most reports stay as fast as today. *Alternative
considered:* always wait. Rejected: a pause with nothing to compare.

### 15 seconds by default, adjustable
A normal health check takes a few seconds, so the wait is the biggest cost of this feature. 15 seconds
keeps that cost modest. It's enough for most working tasks to show movement, helped by counting a
change of item (below) as movement, since busy scans switch items within seconds. *Alternative
considered:* 30 seconds. Rejected: twice the wait for a small gain in certainty. *Alternative
considered:* only checking when the user asks about stuck tasks. Rejected: the user would never get a
heads-up they didn't ask for. `--stuck-wait` lets a user who suspects a slow task
wait longer (up to 5 minutes), and `0` turns the check off. The upper limit keeps a typo from hanging
the script.

### "Moved" means progress or detail text changed
Plex's progress can sit on one number while a scan works through many items; the `subtitle` (the
item currently being processed) still changes. Counting either as movement avoids flagging busy scans.

### DVR and Live TV tasks aren't checked
Tasks whose type starts with `provider.subscription.` (DVR subscription refreshes) or `grabber.`
(recordings and Live TV sessions) are left out. They follow a recording in real time: on a real server
with a Live TV session running, three "Refreshing Sub" tasks sat at "Grabbing" around 50% for the
whole wait, which is normal for them. *Alternative considered:* flag them and rely on careful
wording. Rejected: anyone who records TV would see a false alarm on almost every check.
*Alternative considered:* skip them only while a recording is running. Rejected: more complex, and
how Plex reports these tasks outside a recording isn't known well enough to get right.

### Match by `uuid`, fall back to type and title
Plex gives each activity a `uuid`, which survives title or progress changes. If an older server
leaves it out, type plus title is a reasonable match for the few tasks that run at once.

### Second sample is its own optional part
If the second request fails, the report keeps the first sample, leaves `progress_moved` as `null`
and lists "stuck task check" in `unavailable`, the same pattern every other optional part uses. A
flaky network shouldn't cost the user the whole report or produce a false "stuck".

### The dashboard turns the check off
`dashboard.py` runs `server_health.py` with `--stuck-wait 0`. The dashboard doesn't display
`task_not_progressing`, so waiting would slow every build that happens while a task runs, for nothing.

### Tests replace the wait
The wait goes through one small function (for example `pause(seconds)` wrapping `time.sleep`) so
tests can replace it and run instantly, and so the fake network layer can return a different
`/activities` answer the second time.

## Risks / Trade-offs

- [A shorter wait makes a slow but healthy task more likely to look stuck] → counting a change of
  item as movement covers busy scans; wording says it may just be slow; `--stuck-wait 60` gives a
  more certain answer when the user asks.
- [A slow but healthy task is flagged as possibly stuck] → wording in `SKILL.md` says it may just be
  slow, suggests checking again in a few minutes or with a longer `--stuck-wait`, and never says
  "failed".
- [A DVR task that really is stuck is never flagged] → accepted; the trade-off for not crying wolf
  during every recording.
- [Tasks waiting at 0% (queued) look stuck] → same wording; the task's progress is shown so Claude can
  say it may simply not have started yet.
- [Health reports take ~15 seconds longer while a task runs] → only when something is running;
  documented in `SKILL.md`; the dashboard skips the check entirely.
- [Failed tasks are still invisible] → accepted. `SKILL.md` keeps saying what can't be checked and
  points to Plex's Settings → Troubleshooting. The Roadmap item is closed because no further work on
  it is planned.
