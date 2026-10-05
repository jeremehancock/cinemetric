## Why

`users-and-shares` is the last idea in the README Roadmap. Server owners often lose track of who they
have shared with over the years: old friends who never use it, invites nobody accepted, people who can
download everything, or a new library that was automatically shared with everyone because they were
given "all libraries". Plex shows this one person at a time in its settings; there is no single
overview, and nothing that answers "who can see my Kids library?".

## What Changes

- A new read-only skill, `users-and-shares`, with one script, `users_and_shares.py`. It reports:
  - each person with access: friend, Plex Home member or managed user, accepted or still pending,
    which libraries they can see (or "all libraries", which includes ones added later), whether they
    can download, whether they have content restrictions, and when they last played something
    (from Tautulli when it's set up, otherwise from the server's own watch history);
  - each library, with who can see it;
  - things worth a look: old pending invites, people who haven't played anything in a long time,
    people with "all libraries", and friends who can download.
- Sharing information only exists on plex.tv (the server itself doesn't know it), so the script makes
  read-only `GET` requests to a short, fixed list of plex.tv addresses, using the same sign-in token
  setup already saved. This is a new, narrow exception to the "report scripts only contact your own
  server and Tautulli" rule. **The security spec changes.**
- Other people's private details are never printed: email addresses and the access tokens plex.tv
  includes for each friend are thrown away as soon as the response is read.
- Only the server owner can see who a server is shared with. Anyone else gets a clear `OWNER_ONLY`
  error explaining why.
- A new `--inactive-days N` option (default 90) sets how long without a play counts as inactive.
- README: new row in the Skills table; the `users-and-shares` Roadmap idea is removed.
  SECURITY.md: mentions the plex.tv read-only requests. Website: a sixth skill with a demo panel.
- Version bump to 0.8.0.

## Capabilities

### New Capabilities

- `users-and-shares`: what the script requests, which details it keeps and drops, what the report
  contains, the owner-only rule, and the "worth a look" flags.

### Modified Capabilities

- `security`: "Read-only toward Plex" and "Only known destinations" allow `users-and-shares` to send
  `GET` requests to listed plex.tv addresses; a new requirement says other people's emails and access
  tokens are never printed.
- `conventions`: "Connection check" adds the new script; "One version number" counts every script
  instead of "five".
- `testing`: "Tests check the specs" adds `users-and-shares` coverage.
- `website`: "Shows every skill" adds `users-and-shares`.

## Impact

- New: `plugins/cinemetric/skills/users-and-shares/SKILL.md` and
  `plugins/cinemetric/skills/users-and-shares/scripts/users_and_shares.py` (with copies of the shared
  helpers: `load_config`, `validate_url`, `PlexClient`, `clean`).
- New: `tests/test_users_and_shares.py` and fake plex.tv fixtures in `tests/fixtures/users-and-shares/`.
  Existing cross-script security tests gain the new script.
- `README.md`, `SECURITY.md`, `website/index.html`.
- `VERSION` in all six scripts, `plugin.json` and `marketplace.json`.
- No change to the other skills' behavior or the dashboard.
