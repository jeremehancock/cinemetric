# testing Specification

## Purpose
How Cinemetric's automated tests are organized and run: where they live, the rules they follow
(offline, standard library only, never touching the user's real settings or real data), what they
must cover, and how GitHub runs them and blocks merging into `main` when they fail. What the scripts
themselves must do is in each skill's spec and the `security` and `conventions` specs.
## Requirements
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
  10-bit), housekeeping, report totals, the snapshot area, and `since_snapshot` (titles, episodes,
  unavailable files, new, removed and renamed libraries).
- `security`: address checks, path and command allowlists, refusing redirects, hiding credentials in
  error messages, and cleaning server text, for every script that has these; and skipping bad
  snapshot files and cleaning snapshot text, for every script that reads snapshots.
- `server-health`: the "things worth a look" flags, partial results when one part fails, the
  snapshot area and `since_snapshot`.
- `watch-activity`: choosing a source and the report built from each source.
- `dashboard`: HTML escaping of every value from a report, handling a report source that failed,
  saving a snapshot through the changes script, and the changes section (including names hidden).
- `setup`: Tautulli address cleaning and private file permissions.
- `users-and-shares`: the plex.tv address rules, the owner-only error, dropping emails and access
  tokens, the people and libraries in the report, the "things worth a look" flags, the snapshot area
  (only the allowed details) and `since_snapshot`.
- `unwatched`: choosing a source, which plays count (finished only, every account), which titles are
  listed (cutoff, show added dates), sizes, and the report totals.
- `what-to-watch`: watched status for movies and shows, each filter, merging the same title across
  libraries, sorting and the limit, and continue watching.
- `episode-gaps`: what counts as there (duplicates, unavailable files, multi-episode file names,
  unnumbered episodes), specials, gaps inside a season, late starts, numbering that carries on,
  missing seasons, date-numbered seasons, sorting and the limit, and the report totals.
- `changes`: choosing which snapshot to compare with (earlier day, `--since`, missing area, other
  server), saving and merging the same day, pruning after 90 days, `save` without network, `list`,
  `forget`, file permissions, and a report that fails.

#### Scenario: A shared helper is fixed in one script only
- **WHEN** a fix to `validate_url`, `clean` or the snapshot reading helper is applied to one script
  but not the others
- **THEN** a test for one of the other scripts fails, because the same checks run against every
  script's copy

#### Scenario: A change breaks duplicate detection
- **WHEN** a change to `library_report.py` stops two copies of the same movie from being reported as
  duplicates
- **THEN** a test fails

#### Scenario: A change leaks a friend's email
- **WHEN** a change to `users_and_shares.py` lets an email address from a plex.tv fixture into the
  output
- **THEN** a test fails

#### Scenario: A partly watched title counts as played
- **WHEN** a change to `unwatched.py` treats a Tautulli play with `watched_status` 0.5 as finished
- **THEN** a test fails

#### Scenario: A started show counts as unwatched
- **WHEN** a change to `what_to_watch.py` lets a show with some episodes watched match `--unwatched`
- **THEN** a test fails

#### Scenario: A snapshot copies more about people than allowed
- **WHEN** a change to `users_and_shares.py` puts a last played date or email into the sharing
  snapshot area
- **THEN** a test fails

#### Scenario: Specials show up as gaps
- **WHEN** a change to `episode_gaps.py` reports missing episodes for season 0, or for a season that
  continues the previous season's numbering
- **THEN** a test fails

### Requirement: Tests run on GitHub
A GitHub Actions workflow at `.github/workflows/tests.yml` SHALL run the full offline test suite with
`python3 -m unittest discover -s tests` for every pull request into `main` and every push to `main`,
and SHALL also be startable by hand. It SHALL run the suite once on Python 3.8 (the oldest version
Cinemetric supports) and once on the newest stable Python. The workflow SHALL use no repository
secrets, SHALL have read-only access to the repository, and SHALL install nothing beyond Python
itself.

#### Scenario: Opening a pull request
- **WHEN** a pull request into `main` is opened or updated
- **THEN** the tests run on Python 3.8 and on the newest stable Python, and the result shows on the
  pull request

#### Scenario: Code that only works on newer Python
- **WHEN** a change uses a Python feature that doesn't exist in Python 3.8
- **THEN** the Python 3.8 run fails, even if the run on the newest Python passes

### Requirement: One summary check
The workflow SHALL end with a check named **All tests passed** that succeeds only when the test run
succeeded on every Python version, and fails if any run failed or was cancelled. This is the check
that branch rules refer to, so the list of Python versions can change without changing the rules.

#### Scenario: One Python version fails
- **WHEN** the tests pass on the newest Python but fail on Python 3.8
- **THEN** **All tests passed** fails

#### Scenario: Adding a Python version to the workflow
- **WHEN** another Python version is added to the workflow
- **THEN** the branch rules on `main` don't need to change

### Requirement: Failing tests block merging
The `main` branch SHALL have a GitHub ruleset that requires the **All tests passed** check to succeed
before a pull request can be merged. The ruleset SHALL apply to everyone, including repository
administrators, with no one allowed to bypass it.

#### Scenario: A pull request with failing tests
- **WHEN** a pull request's **All tests passed** check fails
- **THEN** GitHub doesn't allow it to be merged into `main`

#### Scenario: The repository owner tries to merge anyway
- **WHEN** the repository owner tries to merge a pull request whose tests failed
- **THEN** GitHub doesn't allow it either

