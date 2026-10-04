## Context

The `add-offline-tests` change added 166 offline tests in `tests/`, run with
`python3 -m unittest discover -s tests`. They use only the standard library and never touch the
network, so they need nothing installed and no secrets. The repository
(`jeremehancock/cinemetric`) is public, has no `.github` folder and no branch rules yet, and changes
arrive on `main` through pull requests.

Cinemetric promises Python 3.8 or newer. Python 3.8 is officially retired and isn't installed on the
maintainer's computer, so it is currently never tested.

## Goals / Non-Goals

**Goals:**
- Run the tests automatically on the oldest and newest supported Python for every pull request.
- Make a failing run block merging into `main`, for everyone.
- Keep the workflow small, readable, and free of secrets.

**Non-Goals:**
- Publishing releases, building the plugin or deploying the website from GitHub Actions.
- Testing on Windows or macOS runners (possible later; the scripts are plain Python).
- Requiring pull request reviews or other branch rules beyond the test check.
- Running tests against a real Plex server.

## Decisions

### GitHub Actions with GitHub's own `setup-python`
The workflow uses `actions/checkout` and `actions/setup-python`, both maintained by GitHub, pinned to
their current major version. Nothing else is installed: the tests use only the standard library.

Alternative considered: `uv` (`astral-sh/setup-uv`), which can always fetch Python 3.8. It's a
third-party action, so it is only the fallback if GitHub's runners stop offering 3.8 (see Risks).

### Test on 3.8 and the newest stable Python only
3.8 is the oldest promise; the newest version catches deprecations and removals early. Versions in
between are very unlikely to fail when both ends pass, and skipping them keeps runs short. The newest
version is written as `3.x`, which `setup-python` resolves to the latest stable release, so the
workflow doesn't need editing for each new Python.

### A summary job is the required check
The test runs are one job repeated per Python version (a "matrix"). GitHub names each run after its
version (for example `test (3.8)`), so requiring those names directly would mean editing the branch
rules whenever the version list changes. A final job, **All tests passed**, waits for every run and
fails unless all of them succeeded. It uses `if: always()` so it still reports, as a failure, when a
run fails or is cancelled; without that, GitHub would mark it "skipped", and a skipped required check
can let a merge through.

### A ruleset, not classic branch protection
GitHub offers two ways to protect a branch. Rulesets are the newer one: they can be viewed by
anyone with read access, can be created and checked with `gh api`, and can apply to administrators
with an empty bypass list. The ruleset targets the default branch, requires the **All tests passed**
check, and leaves "require branches to be up to date before merging" off, so a passing pull request
doesn't have to be re-run every time something else merges first.

### Settings on GitHub are changed only after confirmation
Creating the ruleset changes the live repository and affects how merges work, so the apply step
shows the exact ruleset and asks the maintainer before creating it. It is created only after the
workflow has run once on a pull request, so the check name is known to exist; a required check that
never reports would block every merge.

### Read-only permissions
The workflow sets `permissions: contents: read`. It only needs to read the code. This also limits
what a pull request from a fork could do through the workflow.

## Risks / Trade-offs

- [GitHub's newest Ubuntu runners may not offer Python 3.8] → Check the first run. If 3.8 isn't
  available, run the 3.8 job on an older Ubuntu image that has it, or switch that job to `uv`.
  Whichever is used is recorded in the workflow with a one-line comment.
- [A required check that never runs blocks every merge] → The ruleset is created only after the
  workflow has reported **All tests passed** once. The workflow runs on every pull request into
  `main`, with no path filters, so the check always reports.
- [Owner can't bypass in an emergency] → The ruleset can be switched off or edited in the repository
  settings at any time. That's a deliberate, visible step, which is the point.
- [Direct pushes to `main` are refused unless they've passed the check] → Changes already arrive
  through pull requests, so day-to-day work is unchanged.

## Migration Plan

1. Merge `add-offline-tests` (the tests must be on `main` for the workflow to have something to run).
2. Add the workflow on a branch and open a pull request. The workflow runs on that pull request.
3. Once it's green, merge it, then create the ruleset (after confirmation).
4. To roll back: delete or disable the ruleset in Settings → Rules, and delete the workflow file.

## Open Questions

- None.
