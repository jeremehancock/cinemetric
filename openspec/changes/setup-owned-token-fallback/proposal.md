## Why

When `setup finish` lists the account's servers, each server's token is taken from plex.tv's
`accessToken` field. If that field is missing, setup falls back to the user's account-wide Plex token.
For a server the user owns that's correct. For a server someone else shared with the user, it means
`select` would send the user's account token (which can act on their whole Plex account) to a server
run by someone else. plex.tv normally always includes `accessToken` for shared servers, so this is
unlikely, but the account token should never go to a server the user doesn't own.

## What Changes

- `finish` uses the account token only for servers the user owns. A shared server without its own
  `accessToken` is left out of the list, because Cinemetric has no safe token to use for it.
- If that leaves no servers, `finish` stops with the existing "no servers it can access" error.
- Version bump to 0.10.1.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `setup`: "Choosing and testing a server" says the account token is only used for owned servers, and
  adds a scenario for a shared server without its own token.

## Impact

- `plugins/cinemetric/skills/setup/scripts/setup.py`: `cmd_finish`.
- `tests/test_setup.py`: offline tests for the new scenario and the owned fallback.
- `VERSION` in all six scripts, `plugin.json` and `marketplace.json`.
