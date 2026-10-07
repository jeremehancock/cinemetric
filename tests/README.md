# Cinemetric tests

Run every test from the repository root:

```bash
python3 -m unittest discover -s tests
```

This needs Python 3.8 or newer and nothing else: the tests use only the standard library.

The mods (read-only guard, status line, Now Playing) have their own tests in
`plugins/cinemetric/tests/`, written in TypeScript. Run them with Claude Code:

```bash
claude plugin test plugins/cinemetric
```

GitHub runs the Python tests on Python 3.8 and the newest Python, and the mods' tests with a pinned
Claude Code version, for every pull request into `main` (see `.github/workflows/tests.yml`). A pull
request can't be merged until the **All tests passed** check is green.

## The rules

- **Offline.** No test contacts Plex, plex.tv, Tautulli or anything else. Code that would make a
  request gets a `FakeServer` (in `helpers.py`) that answers from canned replies. A test that
  tries a real connection fails.
- **Your settings are safe.** Each test points the settings and data folders at a temporary folder
  and clears `PLEX_URL`, `PLEX_TOKEN`, `TAUTULLI_URL` and `TAUTULLI_API_KEY`, so your real
  `~/.config/cinemetric` and dashboard files are never read or changed.
- **No real data in fixtures.** Sample responses in `fixtures/` use made-up values only: fake
  tokens, `Test Server`, addresses like `192.0.2.10` (reserved for examples), invented user names. If
  you start from a real Plex response, replace every token, ID, address and name before committing.

## Writing a test

- Inherit from `helpers.OfflineTestCase`. It sets up the network block and the temporary folder, and
  collects stderr in `self.stderr`.
- Load a script with `helpers.load_script("library-report")`.
- For code that makes requests, build a `FakeServer({path: reply})` and attach it to the script's
  opener (`server.attach(client._opener)`). Afterwards, `server.requests` lists every request it saw.
