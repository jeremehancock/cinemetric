## 1. Bring the oldest scripts onto the current helpers

- [x] 1.1 `library_report.py`: use `read_config_file`, `validate_url(url, name)`, `_NoRedirect`, `build_opener` and `fetch_json`, keeping a Plex-only `load_config`
- [x] 1.2 `server_health.py`: use `read_config_file`, `validate_url(url, name)`, `_NoRedirect` and `build_opener`, keeping its own `PlexClient.get`
- [x] 1.3 `library-report/SKILL.md`: word the 401 error as "rejected the credentials (401)"

## 2. Shared helper list and copy tool

- [x] 2.1 Add `tools/shared_helpers.py` with the list of shared helpers, the scripts allowed to differ and why, the check, and `copy NAME --from SKILL`
- [x] 2.2 Copy `clean` into `changes.py`, `library_report.py` and `setup.py` so every copy matches
- [x] 2.3 List the tool in `tools/README.md`

## 3. Tests

- [x] 3.1 Add `tests/test_shared_helpers.py`: copies match, every listed helper is in at least two scripts, exceptions exist, versions agree, `tests/helpers.py` lists every script
- [x] 3.2 `test_security.py`: find scripts with each helper instead of hand lists, and make a Tautulli client test class for every script with one
- [x] 3.3 `test_media_deletion.py`: find scripts with `media_deletion_allowed` instead of a hand list
- [x] 3.4 Run `python3 -m unittest discover -s tests` and confirm everything passes

## 4. Release

- [x] 4.1 Bump the version to 0.29.1 in every script, `plugin.json` and `marketplace.json`
