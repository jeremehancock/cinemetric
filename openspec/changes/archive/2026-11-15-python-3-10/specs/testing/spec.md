## MODIFIED Requirements

### Requirement: Tests run on GitHub
A GitHub Actions workflow at `.github/workflows/tests.yml` SHALL run the full offline test suite with
`python3 -m unittest discover -s tests` for every pull request into `main` and every push to `main`,
and SHALL also be startable by hand. It SHALL run the suite once on Python 3.10 (the oldest version
Cinemetric supports) and once on the newest stable Python. The same workflow SHALL run the mods'
tests with `claude plugin test plugins/cinemetric`, using a pinned Claude Code version installed for
the run, with no login. The workflow SHALL use no repository secrets, SHALL have read-only access to
the repository, and SHALL install nothing beyond Python, and Node and Claude Code for the mods' tests.

#### Scenario: Opening a pull request
- **WHEN** a pull request into `main` is opened or updated
- **THEN** the tests run on Python 3.10 and on the newest stable Python, the mods' tests run, and the
  results show on the pull request

#### Scenario: Code that only works on newer Python
- **WHEN** a change uses a Python feature that doesn't exist in Python 3.10
- **THEN** the Python 3.10 run fails, even if the run on the newest Python passes

#### Scenario: A change breaks the read-only guard
- **WHEN** a change to `hooks/guard-rules.ts` lets a command that deletes media through
- **THEN** the mods' test run fails

### Requirement: One summary check
The workflow SHALL end with a check named **All tests passed** that succeeds only when the test run
succeeded on every Python version and the mods' tests passed, and fails if any run failed or was
cancelled. This is the check that branch rules refer to, so the list of Python versions and test
jobs can change without changing the rules.

#### Scenario: One Python version fails
- **WHEN** the tests pass on the newest Python but fail on Python 3.10
- **THEN** **All tests passed** fails

#### Scenario: Adding a Python version to the workflow
- **WHEN** another Python version is added to the workflow
- **THEN** the branch rules on `main` don't need to change

#### Scenario: Only the mods' tests fail
- **WHEN** every Python test passes but a mod test fails
- **THEN** **All tests passed** fails

### Requirement: One command runs everything
All tests SHALL run with `python3 -m unittest discover -s tests` from the repository root, on Python
3.10 or newer, using only the standard library. Nothing is installed with `pip`.

#### Scenario: Running the tests on a fresh checkout
- **WHEN** someone clones the repository and runs `python3 -m unittest discover -s tests`
- **THEN** every test runs without any extra setup, and the command exits 0 when all tests pass
