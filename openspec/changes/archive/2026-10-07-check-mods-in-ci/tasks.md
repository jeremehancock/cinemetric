## 1. Run the mods' tests on GitHub

- [x] 1.1 Add a `mods` job to `.github/workflows/tests.yml`: Node 22, `npm install -g @anthropic-ai/claude-code@2.1.293`, `claude plugin test plugins/cinemetric`, nonessential traffic off
- [x] 1.2 Make **All tests passed** wait for both jobs and fail if either didn't succeed
- [x] 1.3 Confirm the job passes on the pull request

## 2. Hooks and scripts agree on file locations

- [x] 2.1 Add `tests/test_hooks_match_scripts.py` comparing `guard.ts`, `status-line.tsx` and `status-line-rules.ts` with the scripts' `config_path`, `data_dir`, `snapshots_dir`, `SERVER_ID` and `SNAPSHOT_NAME`
- [x] 2.2 Confirm the test fails when the settings path or a snapshot pattern differs on one side

## 3. Docs

- [x] 3.1 `tests/README.md`: how to run the mods' tests and that GitHub runs them
