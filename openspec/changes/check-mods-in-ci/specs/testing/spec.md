## MODIFIED Requirements

### Requirement: Tests run on GitHub
A GitHub Actions workflow at `.github/workflows/tests.yml` SHALL run the full offline test suite with
`python3 -m unittest discover -s tests` for every pull request into `main` and every push to `main`,
and SHALL also be startable by hand. It SHALL run the suite once on Python 3.8 (the oldest version
Cinemetric supports) and once on the newest stable Python. The same workflow SHALL run the mods'
tests with `claude plugin test plugins/cinemetric`, using a pinned Claude Code version installed for
the run, with no login. The workflow SHALL use no repository secrets, SHALL have read-only access to
the repository, and SHALL install nothing beyond Python, and Node and Claude Code for the mods' tests.

#### Scenario: Opening a pull request
- **WHEN** a pull request into `main` is opened or updated
- **THEN** the tests run on Python 3.8 and on the newest stable Python, the mods' tests run, and the
  results show on the pull request

#### Scenario: Code that only works on newer Python
- **WHEN** a change uses a Python feature that doesn't exist in Python 3.8
- **THEN** the Python 3.8 run fails, even if the run on the newest Python passes

#### Scenario: A change breaks the read-only guard
- **WHEN** a change to `hooks/guard-rules.ts` lets a command that deletes media through
- **THEN** the mods' test run fails

### Requirement: One summary check
The workflow SHALL end with a check named **All tests passed** that succeeds only when the test run
succeeded on every Python version and the mods' tests passed, and fails if any run failed or was
cancelled. This is the check that branch rules refer to, so the list of Python versions and test
jobs can change without changing the rules.

#### Scenario: One Python version fails
- **WHEN** the tests pass on the newest Python but fail on Python 3.8
- **THEN** **All tests passed** fails

#### Scenario: Adding a Python version to the workflow
- **WHEN** another Python version is added to the workflow
- **THEN** the branch rules on `main` don't need to change

#### Scenario: Only the mods' tests fail
- **WHEN** every Python test passes but a mod test fails
- **THEN** **All tests passed** fails

## ADDED Requirements

### Requirement: Hooks and scripts agree on file locations
A test SHALL check that the hooks find Cinemetric's settings file, data folder and snapshot folders
the same way the scripts do: the environment variables they look at (`XDG_CONFIG_HOME`,
`CINEMETRIC_DATA_DIR`, `XDG_DATA_HOME`, `LOCALAPPDATA`), the folder and file names under each base
folder, and the patterns for server folder and snapshot file names. The expected values SHALL come
from running the scripts' own helpers, not from copies written into the test.

#### Scenario: The scripts move the settings file
- **WHEN** the scripts' `config_path` changes to put the settings file somewhere else but
  `hooks/guard.ts` doesn't
- **THEN** a test fails, naming `guard.ts`

#### Scenario: The snapshot file name changes in one place
- **WHEN** the scripts' snapshot file name pattern changes but `hooks/status-line-rules.ts` doesn't
- **THEN** a test fails
