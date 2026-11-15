## 1. Minimum Python

- [x] 1.1 `.github/workflows/tests.yml`: test on Python 3.10 and 3.x, both on `ubuntu-latest`, and drop the Ubuntu 24.04 special case
- [x] 1.2 `plugins/cinemetric/hooks/now-playing-rules.ts`: the "Couldn't start Python" message says 3.10
- [x] 1.3 `README.md`, `website/index.html`, `tests/README.md` and `openspec/config.yaml` say Python 3.10

## 2. Check

- [x] 2.1 Run the full test suite and the mods' tests (on 2026-11-15 locally: 1183 Python tests on 3.14 and 119 mods tests passed, shared helpers match; this computer has no Python 3.10, so the 3.10 run is GitHub's on the pull request)
- [x] 2.2 Search the repository (outside archived changes) for any remaining mention of Python 3.8

## 3. Version

- [x] 3.1 Bump the version to 0.33.1 in every script's `VERSION`, `plugin.json` and `marketplace.json`
