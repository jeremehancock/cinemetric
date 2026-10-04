## Context

Today `dashboard.py` builds `dashboard.html` in the Cinemetric data folder and can install a scheduled
task (cron, launchd or Task Scheduler) that rebuilds it without Claude. The scheduled task runs a
copy of the scripts kept in `scheduled/`, logs problems to `dashboard.log`, and its settings live in
`dashboard-state.json` under `automation`. Roughly a third of the script (about 230 lines) is
scheduler code. SKILL.md explicitly forbids publishing to claude.ai.

Publishing is something only Claude can do (with its `Artifact` tool); a Python script has no way to
create or update a claude.ai page. The "Dashboard as a claude.ai page" roadmap idea stalled because
scheduled runs (`claude -p`) couldn't publish. Once every refresh happens in a normal Claude session,
that problem disappears.

## Goals / Non-Goals

**Goals:**
- Remove the scheduler and everything that only exists to support it.
- Let the user choose local file, private online page, or both, once, and remember it.
- On every later run, refresh each chosen copy in place: same file path, same claude.ai link.
- Leave no background task behind on computers that had automation turned on.

**Non-Goals:**
- Any automatic refreshing, local or online. A refresh happens when the user runs the skill.
- Sharing the online page with others. It's published private; sharing is the user's call in claude.ai.
- Different content for the two copies (for example names shown locally but hidden online).
- Deleting the online page when the user switches to local only. Claude deletes a claude.ai page only
  when the user asks for that.

## Decisions

### The script remembers; Claude publishes
The script stays offline and rule-based. It stores two new things in `dashboard-state.json`:
`destination` and `online_page` (the claude.ai link), and reports both, plus `ask: ["destination"]`
when no choice is saved. Claude reads that output and does the rest:

1. No destination saved → ask "On this computer, online as a private claude.ai page, or both?", then
   run `destination <choice>`.
2. Build (always writes `dashboard.html`).
3. If the destination includes online: read the file, then publish it with the `Artifact` tool,
   passing the saved `online_page` as `url` when there is one so the same page is updated. After a
   first publish, run `online-page --url <link>` to save the new link.

*Alternative considered:* keeping the link only in Claude's memory or in the conversation. Rejected:
memory isn't guaranteed to be on, and a fresh session wouldn't know which page to update, so every
run would create a new page.

*Alternative considered:* Claude finding the page each time with the Artifact tool's `list` action by
title. Rejected as the main path: titles can change and the user might have several dashboards.
It's still a reasonable fallback if the saved link stops working.

### Online-only still writes the local file
The `Artifact` tool publishes a file from disk, so the page has to exist locally either way. For an
online-only choice Claude simply doesn't point the user at the file. This keeps one build path and
avoids a temporary file with server data in it somewhere else.

### Validate the saved link
`online-page --url` accepts only `https://claude.ai/artifact/<id>` or
`https://claude.ai/code/artifact/<id>` (id: letters, digits, `-`). The link is later handed back to
Claude as the page to update, so a strict shape check keeps a bad or crafted value from ever pointing
Claude somewhere else.

### If the saved page can't be updated
If publishing to the saved link fails because the page was deleted or isn't the user's any more,
Claude runs `online-page --forget`, tells the user, and asks before publishing a new page (then saves
the new link). It never publishes a new page silently, because that would leave the user with two
links without knowing why.

### Hide-names becomes a saved preference
Before, `--hide-names` was per run for manual builds and saved only for scheduled runs. Now it's saved
in the state file (`--hide-names` / `--show-names` change it), because an online page that quietly
switched between showing and hiding names from run to run would be surprising. One page serves both
destinations, so one preference covers both.

### One-time cleanup instead of a cleanup command
On a build, if the state has an `automation` record, the script removes the old task using the same
small per-platform remove functions it has today (`crontab` without the tagged line, `launchctl
unload` + delete plist, `schtasks /Delete`), deletes `scheduled/`, `run-dashboard.cmd` and
`dashboard.log`, and drops the record. Builds without a record never touch the scheduler. Only the
remove halves of the scheduler code stay; install, status and the scheduled-run entry point go.

*Alternative considered:* leaving old tasks alone and documenting how to remove them. Rejected: the
copied scripts would keep running silently (and keep rewriting the page) with no Cinemetric command
left to stop them.

*Alternative considered:* asking before removing. Not needed: the user agreed to the task only as
part of a feature that no longer exists, and removing it is what they'd get by turning it off.
Claude still tells them it happened.

### Version 0.4.0
Removing a feature is a breaking change for anyone who used it, so this is a minor bump rather than a
patch.

## Risks / Trade-offs

- [The `Artifact` tool isn't available (other Claude surfaces, accounts without it)] → SKILL.md tells
  Claude to offer only "on this computer" when it can't publish, and if `online`/`both` is saved, to
  build locally and explain why the online page wasn't updated, without changing the saved choice.
- [Viewer names go to claude.ai] → The page is private, and before the first online publish Claude
  points out that it includes viewer names and offers to hide them.
- [claude.ai wraps the published page in its own page shell, so the dashboard's `<head>` ends up
  inside the host's `<body>`] → Checked during implementation: styles, the tab title and dark mode
  all still work. The Content Security Policy tag is ignored there (browsers only honor it in
  `<head>`), so online it's claude.ai's own protections that apply. The page itself still has no
  scripts and no outside links, so there is nothing for the policy to block.
- [Users lose automatic refreshes] → Intended. The README and release notes say so.
- [Old task removal fails, e.g. `crontab` missing or permissions] → The build still finishes, the
  record is kept so it's retried, and Claude explains the reason.

## Migration Plan

1. Ship 0.4.0. On the first dashboard run, any old scheduled task is removed and reported.
2. The first run also asks where the dashboard should go, since no destination is saved yet.
3. Rollback: reinstall 0.3.3 and run `schedule install` again; the saved `destination` and
   `online_page` keys are ignored by the old version.

## Open Questions

(none)
