## 1. Library activity in the script

- [x] 1.1 Add `get_history` to `TAUTULLI_COMMANDS` and add page size (1,000) and cap (100,000) constants
- [x] 1.2 Add a Tautulli sweep: `get_history` with `after` = first day of the window and `section_id` = each library's key (rows don't carry the library), newest first, paged; collect `(user_id, library key)` pairs; stop on a short page, a page reaching past the window, or the cap
- [x] 1.3 Add a Plex sweep: `/status/sessions/history/all` sorted `viewedAt:desc`, paged; collect `(accountID, librarySectionID)` pairs for plays inside the window; same stop rules
- [x] 1.4 Pick the source (Tautulli, else Plex; Tautulli failure falls back to Plex with "Tautulli library activity" in `unavailable`; both failing gives "library activity" and null source) and build `library_activity` (`source`, `days`, `complete`)
- [x] 1.5 Add `played_by` / `played_by_count` to each library: names from `shared_with` whose user id played from that section key; null when activity is unknown
- [x] 1.6 Add the `unused_library` worth-a-look item (shared with someone, nobody played, at least one person invited before the window or with no invite date; skipped when unknown or incomplete), carrying `libraries` and `days`

## 2. Tests

- [x] 2.1 Extend the users-and-shares fixtures with per-library history for Plex and Tautulli (including an owner play, an unfinished Tautulli play, a play with no library key and a play from a deleted library)
- [x] 2.2 Add tests in `tests/test_users_and_shares.py` for each new spec scenario: friend only watches TV, owner plays ignored, Tautulli source, Tautulli fallback, no history at all, stops at the window, cap reached, `--inactive-days 30` window
- [x] 2.3 Add tests for `unused_library`: flagged library, shared only recently, private library not flagged, incomplete history not flagged
- [x] 2.4 Check only allowed Plex paths and Tautulli commands are used, and existing fields are unchanged
- [x] 2.5 Dashboard: add a `share_note()` branch for `unused_library` showing the count and library titles (also when names are hidden), with a test in `tests/test_dashboard.py`
- [x] 2.6 `python3 -m unittest discover -s tests` passes

## 3. Tell Claude about it

- [x] 3.1 `SKILL.md`: add "which shared libraries does nobody use / who uses which library" to the `description` triggers, and note `--inactive-days` also sets the library window
- [x] 3.2 `SKILL.md`: describe `played_by`, `played_by_count` and `library_activity`; in the Libraries part of the report, say how many of the people who can see each library played from it recently
- [x] 3.3 `SKILL.md`: explain `unused_library` under Worth a look as a neutral fact (could be seasonal, a new library, or intentional), mention the Plex "finished plays only" caveat once when the source is `plex`, and never suggest unsharing or removing anyone

## 4. Docs

- [x] 4.1 README: remove the `users-and-shares` item from Roadmap "Ideas for later"
- [x] 4.2 `openspec/ideas.md`: remove the `users-and-shares` note
- [x] 4.3 Website: mention which shared libraries get used in the users-and-shares feature list in `website/index.html`

## 5. Verify

- [x] 5.1 Run against the real server: output is valid JSON, existing fields unchanged, history entries carry a library key, and `played_by` looks right for the libraries people actually use
- [x] 5.2 Run `dashboard.py` against the new report and confirm the Sharing section builds and shows the new note when present
- [x] 5.3 `openspec validate users-and-shares-unused-libraries` passes

## 6. Release

- [x] 6.1 Bump the version to 0.17.0 in all eight scripts, `plugin.json` and `marketplace.json`
