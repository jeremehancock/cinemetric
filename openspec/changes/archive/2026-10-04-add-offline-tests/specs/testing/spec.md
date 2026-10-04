## ADDED Requirements

### Requirement: Where the tests live
Automated tests SHALL live in a `tests/` folder at the repository root, outside `plugins/`, so they are
not part of what users install. Sample server responses used by the tests SHALL live in
`tests/fixtures/`.

#### Scenario: Installing the plugin
- **WHEN** a user installs Cinemetric from the marketplace
- **THEN** the installed plugin contains no test files or fixtures

### Requirement: One command runs everything
All tests SHALL run with `python3 -m unittest discover -s tests` from the repository root, on Python
3.8 or newer, using only the standard library. Nothing is installed with `pip`.

#### Scenario: Running the tests on a fresh checkout
- **WHEN** someone clones the repository and runs `python3 -m unittest discover -s tests`
- **THEN** every test runs without any extra setup, and the command exits 0 when all tests pass

### Requirement: Tests are offline
Tests SHALL NOT contact Plex, plex.tv, Tautulli or any other network address. Code that would
normally make a network request SHALL be given a fake network layer that answers from fixtures. Any
attempt to open a real network connection during a test SHALL make that test fail.

#### Scenario: A test forgets to fake the network
- **WHEN** a test runs code that tries to open a real connection
- **THEN** the test fails with a message saying a real network connection was attempted

#### Scenario: Running the tests with no Plex server
- **WHEN** the tests run on a computer with no Plex server and no internet connection
- **THEN** they all run and pass

### Requirement: Tests leave the user's files alone
Tests SHALL NOT read or change the user's real Cinemetric settings, dashboard files or any other file
outside a temporary folder. Before a test runs code that reads settings or data folders,
`XDG_CONFIG_HOME` and `XDG_DATA_HOME` SHALL point to a temporary folder, and the `PLEX_URL`,
`PLEX_TOKEN`, `TAUTULLI_URL` and `TAUTULLI_API_KEY` environment variables SHALL be cleared or set by
the test. The temporary folder SHALL be removed afterwards.

#### Scenario: The developer has Cinemetric set up
- **WHEN** the tests run on a computer that has a real `~/.config/cinemetric/config.json`
- **THEN** no test reads it, changes it or depends on what is in it

### Requirement: Fixtures contain no real personal data
Fixture files SHALL contain no real tokens, API keys, server addresses, user names or other personal
details. Any value copied from a real server SHALL be replaced with an obviously fake one.

#### Scenario: Adding a fixture from a real server
- **WHEN** a sample response is saved from a real Plex server for use as a fixture
- **THEN** tokens, machine IDs, addresses, user names and account details in it are replaced with
  fake values before it is committed

### Requirement: Tests check the specs
Tests SHALL check behavior that the specs in `openspec/specs/` require, and SHALL NOT check details
the specs leave open. At least the following SHALL be covered:
- `library-report`: duplicates within and across libraries, media breakdown (resolution buckets,
  10-bit), housekeeping, and report totals.
- `security`: address checks, path and command allowlists, refusing redirects, hiding credentials in
  error messages, and cleaning server text, for every script that has these.
- `server-health`: the "things worth a look" flags and partial results when one part fails.
- `watch-activity`: choosing a source and the report built from each source.
- `dashboard`: HTML escaping of every value from a report, and handling a report source that failed.
- `setup`: Tautulli address cleaning and private file permissions.

#### Scenario: A shared helper is fixed in one script only
- **WHEN** a fix to `validate_url` or `clean` is applied to one script but not the others
- **THEN** a test for one of the other scripts fails, because the same checks run against every
  script's copy

#### Scenario: A change breaks duplicate detection
- **WHEN** a change to `library_report.py` stops two copies of the same movie from being reported as
  duplicates
- **THEN** a test fails
