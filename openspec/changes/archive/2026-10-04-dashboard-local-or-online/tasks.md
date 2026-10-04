## 1. Remove the scheduler from dashboard.py

- [x] 1.1 Delete `schedule install|status`, `scheduled_run`, `--scheduled`, `--data-dir`, `snapshot_scripts`, the install and "present" functions, `INTERVAL_SECONDS` and the `NO_SCHEDULER` error
- [x] 1.2 Keep only the per-platform remove functions (cron, launchd, Task Scheduler) and add `remove_old_schedule(state)`: runs only when the state has an `automation` record, removes the task, deletes `scheduled/`, `run-dashboard.cmd` and `dashboard.log`, drops the record; on failure keeps the record and returns the reason
- [x] 1.3 Update the module docstring and comments so they no longer describe automatic updates

## 2. Destinations and the online page link

- [x] 2.1 Add the `destination local|online|both` command that saves the choice and prints `destination` and `online_page`
- [x] 2.2 Add the `online-page --url URL | --forget` command, accepting only `https://claude.ai/artifact/<id>` or `https://claude.ai/code/artifact/<id>` links and refusing anything else with a plain error
- [x] 2.3 Make hide-names a saved preference: `--hide-names` / `--show-names` change it, otherwise the saved value is used
- [x] 2.4 Change the build output to `output`, `server`, `sections_missing`, `names_hidden`, `destination`, `online_page`, `ask`, `old_schedule_removed` (and `old_schedule_error` when removal failed); drop `automation` and `offer`

## 3. Skill and docs

- [x] 3.1 Rewrite SKILL.md: new description (no automatic updates), `Artifact` in `allowed-tools`, first-run destination question, build, publish/update the online page with the saved link (read the file first, private, save the link after a first publish), mention names before the first online publish, how to change the destination, what to do if the saved page can't be updated or the Artifact tool isn't available, and telling the user when an old schedule was removed
- [x] 3.2 SKILL.md rules: remove "don't publish" and the scheduled-task rules; add "publish only when the saved destination includes online", "never delete the online page unless asked", "the script writes only its own files in the data folder"
- [x] 3.3 README: update the `dashboard` row in the skills table, remove the scheduler-testing and "Dashboard as a claude.ai page" roadmap items
- [x] 3.4 Check SECURITY.md for anything about scheduled tasks or the dashboard log and update it

## 4. Verify

- [x] 4.1 With a temporary `CINEMETRIC_DATA_DIR`: first build has `ask: ["destination"]`; after `destination both` and `online-page --url ...`, the next build reports both and `ask` is empty
- [x] 4.2 `online-page --url https://example.com/x` and a claude.ai link with a non-artifact path are both refused, and the saved link is unchanged
- [x] 4.3 Hide-names is remembered across builds and no names appear on the page
- [x] 4.4 Old-schedule cleanup with a stand-in `crontab` on `PATH` and a fake `automation` record: the tagged line, `scheduled/` and `dashboard.log` are gone and `old_schedule_removed` is `true`; a build without a record runs no `crontab` at all
- [x] 4.5 Publish a real dashboard as a private artifact, run again and confirm the same link is updated; check the page renders with its title and in light and dark mode
- [x] 4.6 New and changed state files are `600`

## 5. Release

- [x] 5.1 Bump the version to 0.4.0 in every script's `VERSION`, `plugin.json` and `marketplace.json`
- [x] 5.2 Note in the commit message that automatic updates were removed and any existing scheduled task is removed on the next dashboard run
