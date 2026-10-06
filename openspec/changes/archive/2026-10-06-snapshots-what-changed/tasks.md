## 0. Confirm defaults

- [x] 0.1 Confirm with the user: snapshots always on (no opt-in), one per day, kept 90 days, and the dashboard compares with the previous day's snapshot. Update proposal, design and specs if any answer differs

## 1. Snapshot reading helper

- [x] 1.1 Write the shared helper (data folder with `CINEMETRIC_DATA_DIR` / `XDG_DATA_HOME` / `LOCALAPPDATA`, snapshots folder, server id check, list `YYYY-MM-DD.json` files, safe read: regular file, 50 MB limit, JSON object, `format` 1) and `choose_snapshot(server_id, area, since_days)` per "Reading snapshots"
- [x] 1.2 Add a small `clean_tree` step so every string read from a snapshot goes through `clean`
- [x] 1.3 Copy the helper into `library_report.py`, `server_health.py`, `users_and_shares.py` and the new `changes.py`, identical in each

## 2. library-report

- [x] 2.1 Add `--since` (1–90) and `--snapshot-items`; refuse `--snapshot-items` with `--library` before any request
- [x] 2.2 Keep `machineIdentifier` from `/`; build the library area while reading each library (items by `ratingKey`, episode counts per show, unavailable by `ratingKey`) using the existing labels
- [x] 2.3 Add the `snapshot` block only with `--snapshot-items`
- [x] 2.4 Build `since_snapshot` (new / removed / renamed libraries, counts and size change, added, removed, episodes added / removed, became unavailable, available again, `_count` plus up to 25 sorted examples, totals; `--library` compares only those libraries)

## 3. server-health

- [x] 3.1 Add `--since` and `--snapshot-items`; keep `machineIdentifier`
- [x] 3.2 Build the health area (`version`, `update_version`, `remote_access`) and `snapshot` block
- [x] 3.3 Build `since_snapshot.changes` (null on either side is not a change)

## 4. users-and-shares

- [x] 4.1 Add `--since` and `--snapshot-items`
- [x] 4.2 Build the sharing area with only `name`, `kind`, `status`, `libraries`, `allow_downloads`
- [x] 4.3 Build `since_snapshot` (added, removed, accepted, libraries changed with gained / lost or from / to, downloads changed, `email_invites_change`), matching by name and kind

## 5. changes skill

- [x] 5.1 Create `skills/changes/scripts/changes.py`: run the three reports side by side with `--snapshot-items` (and `--since`; `--stuck-wait 0` for health), 30-minute timeout, `sections_missing`, fail with the first error (keeping its code) when all fail
- [x] 5.2 Save: check every block names the same letters-and-digits server id, merge with today's file, write `600` via a temp file and rename, folders `700`
- [x] 5.3 Prune files dated more than 90 days ago in every server folder, touching only `YYYY-MM-DD.json` names
- [x] 5.4 `save` subcommand (stdin, 50 MB limit, no network, prints `snapshot_saved`), `list` and `forget`
- [x] 5.5 Print the report: `server`, `snapshot_saved`, `library`, `health`, `sharing`, `sections_missing`
- [x] 5.6 Write `skills/changes/SKILL.md`: triggers ("what changed on my Plex", "what's new since last week", "did anything go missing", "who did I share with lately", "forget the snapshots"), mapping "this week" / "this month" to `--since`, how to present each area, first-run wording, facts only (a removed-and-added pair with the same name usually means Plex re-added it), never suggest deleting or unsharing, the standard safety instructions, `allowed-tools` only `Read` and its own script

## 6. Dashboard

- [x] 6.1 Add `--snapshot-items` to the library, health and sharing runs; drop `snapshot` blocks from the page data
- [x] 6.2 After the reports, pipe the successful library, health and sharing reports to `changes.py save`; a failure gives `snapshot_saved` null without stopping the build; add `snapshot_saved` to the build output
- [x] 6.3 Add the "Since <date>" section (library totals and per-library examples, server change lines, sharing changes as counts when names are hidden, first-build and nothing-changed wording, every value escaped)

## 7. Tell Claude about it in the reports

- [x] 7.1 library-report `SKILL.md`: describe `since_snapshot` and `--since`; add a short "Since <date>" part to the report; when null, one line saying the changes skill or dashboard saves snapshots
- [x] 7.2 server-health `SKILL.md`: same for server changes
- [x] 7.3 users-and-shares `SKILL.md`: same for sharing changes, facts only
- [x] 7.4 dashboard `SKILL.md`: mention the new section and `snapshot_saved`

## 8. Tests

- [x] 8.1 Snapshot helper tests run against every copy: bad JSON, too large, wrong format, symlink, bad server id, odd file names, crafted text cleaned
- [x] 8.2 Choosing: earlier day only, `--since` newest old-enough, oldest when none old enough, missing area, other server
- [x] 8.3 library-report: snapshot area contents, no `snapshot` without the flag, refusal with `--library`, each `since_snapshot` scenario
- [x] 8.4 server-health and users-and-shares: snapshot areas (sharing keeps only allowed details) and each `since_snapshot` scenario
- [x] 8.5 `tests/test_changes.py`: first run, normal run, same-day merge, strange server id, pruning at 90 / 91 days and other files left alone, `save` with no network, `list`, `forget`, `600` / `700` permissions, OWNER_ONLY and NOT_CONFIGURED handling
- [x] 8.6 Dashboard: snapshot saved through `changes.py save`, failed save doesn't stop the build, changes section with names hidden, first build, HTML escaping
- [x] 8.7 `python3 -m unittest discover -s tests` passes

## 9. Docs

- [x] 9.1 README: add the `changes` skill; turn the Roadmap snapshots item into a weekly digest item
- [x] 9.2 `openspec/ideas.md`: shrink the snapshots note to the weekly digest and trend charts
- [x] 9.3 SECURITY.md: mention snapshot files (what's in them, where, private, `forget`)
- [x] 9.4 Website: add the `changes` feature with an example request and a terminal demo panel using made-up data

## 10. Verify

- [x] 10.1 Run `changes.py` twice against the real server on different days (or with a back-dated copy of today's snapshot) and check the output looks right
- [x] 10.2 Run each of the three reports and confirm `since_snapshot`, and that the existing fields are unchanged
- [x] 10.3 Build the dashboard and check the "Since" section, then take a fresh screenshot with `tools/dashboard_screenshot.py` if the website demo needs it
- [x] 10.4 `openspec validate snapshots-what-changed` passes

## 11. Release

- [x] 11.1 Bump the version to 0.18.0 in all nine scripts, `plugin.json` and `marketplace.json`
