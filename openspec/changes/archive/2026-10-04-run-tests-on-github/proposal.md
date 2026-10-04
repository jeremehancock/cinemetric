## Why

The offline tests (from `add-offline-tests`) only run when someone remembers to run them, and only on
that person's Python version. Cinemetric promises to work on Python 3.8 or newer, but no one's
computer here has 3.8, so the oldest supported version is never actually checked. Running the tests
on GitHub for every pull request closes both gaps, and making `main` require a passing run means a
change that breaks the tests can't be merged by accident.

## What Changes

- Add a GitHub Actions workflow, `.github/workflows/tests.yml`, that runs the existing offline tests
  (`python3 -m unittest discover -s tests`) on Python 3.8 and on the newest stable Python, for every
  pull request into `main` and every push to `main`. It can also be started by hand.
- The workflow has a final summary check, **All tests passed**, that is green only when every Python
  version passed. This is the single check GitHub is told to require.
- Add a ruleset on GitHub for the `main` branch that requires **All tests passed** before a pull
  request can be merged. It applies to everyone, including the repository owner.
- The workflow uses no secrets, only reads the repository, and the tests stay fully offline.
- Update `tests/README.md` to say the tests also run on GitHub, and remove the "Run the tests on
  GitHub" item from the README Roadmap once it's done.
- No change to the skills, their scripts, releases or how the plugin is published.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `testing`: adds requirements that the tests run on GitHub on the oldest and newest supported
  Python, and that a failing run blocks merging into `main`. (The `testing` spec is introduced by the
  `add-offline-tests` change; these requirements are added to it.)

## Impact

- New file: `.github/workflows/tests.yml` (the first workflow in this repository).
- GitHub repository settings: one new ruleset on `main`. This lives on GitHub, not in the repository.
- Direct pushes to `main` that haven't passed the check will be refused too, because a required
  check applies to every update of the branch. Changes go through pull requests, which is already
  how this repository works.
- Uses GitHub Actions minutes, which are free for public repositories.
- No version bump: nothing users install changes.
