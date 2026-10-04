## ADDED Requirements

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
