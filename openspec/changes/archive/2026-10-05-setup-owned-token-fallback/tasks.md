## 1. Script

- [x] 1.1 In `cmd_finish`, fall back to the account token only when the resource is `owned`, and skip a shared server that has no `accessToken`

## 2. Tests

- [x] 2.1 Add offline tests in `tests/test_setup.py`: an owned server without `accessToken` is saved with the account token, and a shared server without one is left out and the account token is not saved for it
- [x] 2.2 `python3 -m unittest discover -s tests` passes

## 3. Verify

- [x] 3.1 `openspec validate setup-owned-token-fallback` passes

## 4. Release

- [x] 4.1 Bump the version to 0.10.1 in all six scripts, `plugin.json` and `marketplace.json`
