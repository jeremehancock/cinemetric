## Context

Cinemetric's five scripts (`dashboard.py`, `library_report.py`, `server_health.py`, `setup.py`,
`watch_activity.py`) are plain standard-library Python, each self-contained, with shared helpers
copied between them (see the `conventions` spec). There are no tests today. Checking a change means
running the skills against a real Plex server by hand.

The code is already shaped in a way that suits testing:

- Each script guards `main()` with `if __name__ == "__main__":`, so importing it runs nothing.
- Network access goes through one place per script: `PlexClient`, `TautulliClient` or
  `tautulli_call`, each of which sends requests through a `urllib` "opener" object.
- Most logic (for example `library_duplicates`, `resolution_bucket`, `worth_a_look`, `trend`) takes
  plain dictionaries and returns plain dictionaries, with no network involved.
- Settings are found through `XDG_CONFIG_HOME` and environment variables, which tests can point
  somewhere safe.

## Goals / Non-Goals

**Goals:**
- A test suite anyone can run with one command and no installs.
- Catch quiet mistakes in counting, duplicate detection and flagging.
- Catch any loosening of the security rules, in every script's copy of the shared helpers.
- Never touch the network or the developer's real settings.

**Non-Goals:**
- Tests against a real Plex or Tautulli server.
- Running tests on GitHub automatically (a later change can add a small workflow).
- Measuring test coverage or adding coverage tools.
- Testing the website's `script.js`, or testing `SKILL.md` wording.
- Testing the Tautulli key form's local web server end to end, or the dashboard's schedule clean-up
  commands (`crontab`, `launchctl`, `schtasks`). These are hard to test without touching the system
  and are left for later.

## Decisions

### Use `unittest`, not `pytest`
`unittest` ships with Python, so the "standard library only" rule holds for tests too and there is
nothing to install. `pytest` gives nicer output, but it would be the project's first outside
dependency. `pytest` can still run `unittest` tests if someone prefers it locally.

### Load scripts by file path
Script folders have hyphens (`library-report`) and aren't Python packages, so normal `import` won't
work. A small helper in `tests/helpers.py` loads each script with `importlib.util` from its path and
gives it a unique module name (for example `cinemetric_library_report`). This also avoids clashing
with other modules called `setup`.

Alternative considered: adding `sys.path` entries per test file. Rejected because two scripts share
helper names and a module named `setup` is easy to confuse with other things.

### Fake the network at the opener, not the client
For whole-report tests, the test builds the script's real `PlexClient` (or `TautulliClient`) and then
replaces its `_opener` with a fake opener. The fake opener looks at the requested path, returns the
matching fixture file, and records every request it saw.

This means the real client code still runs: the path allowlist, the GET-only rule, the headers, the
error handling and the token hiding are all exercised. A test can then check, for example, that every
recorded request was a GET to an allowed path.

For `setup.py`, which builds its opener inside `_opener()` instead of storing it, tests replace that
function for the duration of the test using `unittest.mock.patch`.

Alternative considered: a fake client class with its own `get()` method. Simpler, but it skips the
code that enforces the security rules, which is exactly the code most worth testing.

### Block real network connections
`tests/helpers.py` provides a base test class that, for each test, patches
`socket.socket.connect` and `socket.create_connection` to raise an error with a clear message
("a test tried to open a real network connection"). If a test forgets to fake the network, it fails
straight away instead of quietly calling a real server.

### Keep the user's settings out of reach
The same base class creates a temporary folder per test, points `XDG_CONFIG_HOME`, `XDG_DATA_HOME`
and `HOME` at it, and clears `PLEX_URL`, `PLEX_TOKEN`, `TAUTULLI_URL` and `TAUTULLI_API_KEY`. Settings
are restored and the folder is deleted after the test. Tests that need a config file write one into
the temporary folder.

### Small fixtures, mostly hand-written
Most tests build a few items inline (for example two movies sharing a `guid`). Whole-report tests use
JSON files in `tests/fixtures/<script>/`, named after the path they answer (for example
`library_sections.json` for `/library/sections`). Fixtures stay small (a handful of items) and use
obviously fake values (`"token-for-tests"`, `"Test Server"`, `192.0.2.10`). Real responses may be used
as a starting point but are trimmed and scrubbed first.

### Run every shared-helper check against every copy
Shared helpers (`validate_url`, `looks_local`, `clean`, the no-redirect handler, token hiding) are
tested with a loop over each script that has a copy, using `subTest` so a failure names the script.
`watch_activity.validate_url` takes an extra `name` argument and `setup.py` uses
`clean_tautulli_url`; the loop handles those differences.

### No script changes expected
Everything above works with the scripts as they are. If a function turns out to be untestable without
a change, the change will be the smallest one that keeps behavior identical, and it must be applied
to every copy of a shared helper.

## Risks / Trade-offs

- [Fixtures drift from what Plex really sends] → Keep fixtures modeled on real responses, and keep
  the occasional manual run against a real server as part of checking a change.
- [Tests depend on private details like `_opener`] → Only the client's opener is replaced, which is a
  stable, single point per script. If it's renamed, a few tests fail clearly and are easy to fix.
- [The network block patches `socket`, which might hide a real bug] → It only turns a real
  connection into a test failure. It never makes a test pass.
- [Python 3.8 compatibility] → Tests avoid syntax newer than 3.8 (no `match`, no `X | Y` type hints,
  no parenthesized context managers), matching the scripts.

## Open Questions

- Should a small GitHub Actions workflow run the tests on each pull request? Left out for now, and
  easy to add later.
