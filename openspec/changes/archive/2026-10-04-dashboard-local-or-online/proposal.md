## Why

The dashboard's automatic updates add a scheduled task to the user's computer (cron, launchd or Task
Scheduler) with three platform-specific code paths, a copied set of scripts that goes out of date with
every plugin update, and macOS and Windows support that has never been tested on real machines. The
user would rather refresh the dashboard by asking Claude, and wants the option to keep it as a private
claude.ai page (an "artifact") they can open from any device, which the old "on hold" roadmap item
blocked only because scheduled runs couldn't publish. Without a scheduler, that blocker is gone.

## What Changes

- **BREAKING** Remove automatic updates: the `schedule install|status|remove` command, `--scheduled`,
  `--data-dir`, the copied `scheduled` scripts folder, `dashboard.log` and the `NO_SCHEDULER` error.
  The dashboard is refreshed only when the user runs the skill.
- One-time cleanup: if a scheduled task from an older version is still installed, the next dashboard
  run removes it (and the copied scripts) and says so, so nothing keeps running in the background.
- New choice of where the dashboard goes: **on this computer** (local file), **online** (a private
  claude.ai page) or **both**. The first run asks; the answer is saved and reused on later runs, and
  the user can change it at any time by asking.
- Later runs update in place: the local file is rewritten at the same path, and the online page is
  republished to the same claude.ai link, so bookmarks keep working.
- The script saves the choice and the online page's link in its state file, and reports them so
  Claude knows whether to ask and which page to update.
- Hiding names (`--hide-names`) becomes a saved preference that applies to both copies, and Claude
  points out before the first online publish that the page includes viewer names unless hidden.
- SKILL.md: drop the automation instructions and the "don't publish" rule; add the destination
  question and the publish/update steps.
- README: describe the new behavior and remove the two dashboard roadmap items (scheduler testing,
  claude.ai page) that this change settles.
- Version bump to 0.4.0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dashboard`: removes "Automatic updates on the computer's own scheduler" and "Scheduled runs survive
  plugin updates"; replaces "Output" with "Build output" (new fields, no `automation`); adds requirements for choosing and
  remembering destinations, remembering the online page's link, and cleaning up an old schedule.
- `conventions`: "Output and errors" drops `NO_SCHEDULER` from the list of fixed error codes.
- `security`: adds "Dashboard goes online only by choice" (only when the user chose it, only as a
  private page, scripts never publish); "Private files" drops the dashboard log.

## Impact

- `plugins/cinemetric/skills/dashboard/scripts/dashboard.py`: delete the scheduler code (keeping only
  what's needed to detect and remove an old task), add the `destination` and `online-page` commands,
  and new fields in the JSON output.
- `plugins/cinemetric/skills/dashboard/SKILL.md`: rewritten run flow, `Artifact` added to
  `allowed-tools`, description updated (no more "keep itself up to date automatically").
- `README.md`: skills table, roadmap.
- Users who had automatic updates turned on lose them; their old task is removed on the next run.
- `VERSION` in every script, `plugin.json` and `marketplace.json`.
