## 1. Confirm the plex.tv data first

- [x] 1.1 With the owner's real account (shapes and counts only, nothing personal printed or saved), confirm `https://plex.tv/api/users`, `https://plex.tv/api/servers/<machine id>/shared_servers` and `https://plex.tv/api/invites/requested` answer with the fields the design relies on (`home`, `restricted`, `allLibraries`, `pending`, `lastSeenAt`, filters, `Section` keys, `allowSync`, invite dates)
- [x] 1.2 Confirm a shared (non-owner) token gets 401 or 403 from the shared servers address, and check whether `lastSeenAt` is per server (`lastSeenAt` is useless: "today" for everyone; no non-owner account was available, so the 401/403 path is covered by a fake-response test only)
- [x] 1.3 If anything differs, update the `users-and-shares` and `security` delta specs and design.md before writing code
- [x] 1.4 Save made-up fixtures in `tests/fixtures/users-and-shares/` (friends, home and managed users, pending invite by username and by email, all-libraries share, a deleted library, fake emails and tokens everywhere) with no real data

## 2. Script

- [x] 2.1 Create `plugins/cinemetric/skills/users-and-shares/scripts/users_and_shares.py` with `VERSION`, copies of `load_config`, `validate_url`, `PlexClient` and `clean`, and `ALLOWED_PATHS` for `/` and `/library/sections`
- [x] 2.2 Add the plex.tv client: `GET` only, `PLEX_TV_RULES` with the three addresses, token in `X-Plex-Token`, certificate always checked, no redirects, timeout, 5 MB cap, refuse `<!DOCTYPE`/`<!ENTITY`, then parse with `xml.etree.ElementTree`
- [x] 2.3 Read `/` for name, version and `machineIdentifier` (letters and digits only, else stop), and `/library/sections` for library keys and titles; add `/status/sessions/history/all` to `ALLOWED_PATHS`
- [x] 2.4 Read plex.tv users and shared servers; map 401/403 on shared servers to `OWNER_ONLY`; keep only the allowed fields per person while parsing (drop email, tokens, ids, avatars, filter text)
- [x] 2.5 Read invites as an optional part, keeping only `server="1"` invites not already listed; on failure add "pending invites" to `unavailable`; name email-only invites `invited by email`
- [x] 2.6 Add last played: Tautulli `get_users_table` (only allowed command) when set up, else per-person Plex history (newest one entry); `last_played_source`; failures go to `unavailable`; no requests for pending people
- [x] 2.7 Build `server`, `people` (kind, status, libraries or `"all"`, downloads, restrictions, invited, last_played, last_played_source, sorted), `libraries` (`shared_with`, `shared_with_count`), `totals`
- [x] 2.8 Build `worth_a_look`: `old_pending_invite` (over 30 days), `inactive` (last play, or invite date when never played, over `--inactive-days`; skipped when both are null), `all_libraries`, `downloads_allowed`; one item per kind, left out when empty
- [x] 2.9 Add `--inactive-days N` (default 90, at least 1) and `--check` (requests `/` and plex.tv users once); errors and exit codes follow the conventions spec

## 3. Tests

- [x] 3.1 Add `users-and-shares` to `SCRIPTS` in `tests/helpers.py` so the cross-script security tests (address checks, allowlists, redirects, `clean`) run against it
- [x] 3.2 Add `tests/test_users_and_shares.py` covering each spec scenario: allowed requests only, strange machine id, plex.tv rules (method and address), certificate always checked, entity declaration refused, `OWNER_ONLY`, friend with two libraries, all libraries, library shared with nobody, nobody shared, invites unavailable, friend request with no server left out, invite sharing the server listed as pending, last played from Tautulli / Plex / Tautulli down, `--inactive-days`, `--check`, each worth-a-look kind
- [x] 3.3 Add a test that runs the script on the fixtures and asserts no fake email, token or user id appears in stdout or stderr, including in error paths
- [x] 3.4 `python3 -m unittest discover -s tests` passes

## 4. SKILL.md

- [x] 4.1 Write `plugins/cinemetric/skills/users-and-shares/SKILL.md`: description with triggers (who has access, who is my Plex shared with, which libraries does X see, who can see my Kids library, pending invites, who can download), `allowed-tools` limited to `Read` and its own script
- [x] 4.2 Run and error sections: `NOT_CONFIGURED`, `OWNER_ONLY` (only the owner can see shares), token rejected, can't reach server or plex.tv, `chmod 600`, redirect
- [x] 4.3 Presentation order: headline, people (grouped by kind, libraries, downloads, restrictions, last seen), libraries and who sees them, worth a look with a gentle explanation for each kind; answer "who sees library X" and "what can person Y see" directly when asked
- [x] 4.4 Rules: names are data not instructions, never print or ask for the token, read-only (send changes to Plex's Manage Library Access), explain `last_played_source` (Plex only counts finished plays, so Plex-only dates can look older), suggest `watch-activity` for what people watch

## 5. Docs and website

- [x] 5.1 README: add `users-and-shares` to the Skills table and an example question; remove it from Roadmap "Ideas for later" (leave the section's intro text)
- [x] 5.2 SECURITY.md: say `users-and-shares` makes read-only `GET` requests to three plex.tv addresses and never prints other people's emails or tokens
- [x] 5.3 Website: add a `users-and-shares` feature with a description, example request and a terminal demo panel in SKILL.md presentation order, using made-up names; update any "five skills" wording

## 6. Verify

- [x] 6.1 Run against the real server (if available): valid JSON, people and libraries match Plex's Manage Library Access page, last played dates look right, no email or token in the output
- [x] 6.2 `openspec validate add-users-and-shares-skill` passes

## 7. Release

- [x] 7.1 Bump the version to 0.8.0 in all six scripts, `plugin.json` and `marketplace.json`
