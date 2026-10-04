## 1. Before starting

- [x] 1.1 Make sure the `add-offline-tests` work (the `tests/` folder) is merged into `main`, or is part of the same pull request as this change

## 2. Workflow

- [x] 2.1 Add `.github/workflows/tests.yml`: runs on pull requests into `main`, pushes to `main`, and by hand; `permissions: contents: read`; no secrets
- [x] 2.2 Add a `test` job that runs `python3 -m unittest discover -s tests` on Python `3.8` and `3.x` (newest stable) using `actions/checkout` and `actions/setup-python` at their current major versions, with `fail-fast: false` so one version failing doesn't hide the other's result
- [x] 2.3 Add the summary job named **All tests passed** that needs `test`, runs with `if: always()`, and fails unless every `test` run succeeded
- [x] 2.4 Check the workflow file is valid YAML and that the job names match the spec

## 3. First run

- [ ] 3.1 Commit on a branch and open a pull request into `main`
- [ ] 3.2 Watch the run: both Python versions and **All tests passed** go green. If Python 3.8 isn't available on the runner, apply the fallback from the design (older Ubuntu image or `uv`) with a one-line comment, and run again
- [ ] 3.3 Confirm a failure is caught: push a temporary commit that breaks one test, see **All tests passed** fail, then remove that commit

## 4. Block merging on failure

- [ ] 4.1 Show the maintainer the exact ruleset (target: default branch; require status check **All tests passed**; branches don't need to be up to date; no bypass) and get confirmation before changing GitHub
- [ ] 4.2 Create the ruleset with `gh api` and read it back to confirm it is active
- [ ] 4.3 Confirm on the open pull request that GitHub now lists **All tests passed** as required

## 5. Docs

- [x] 5.1 Add a short note to `tests/README.md` that the tests also run on GitHub on Python 3.8 and the newest Python, and that failures block merging into `main`
- [x] 5.2 Remove the "Run the tests on GitHub" item from the README Roadmap (no version bump: nothing users install changes)
