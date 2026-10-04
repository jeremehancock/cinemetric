## 1. Test foundation

- [x] 1.1 Create `tests/helpers.py` (no `__init__.py`, so `helpers` imports the same way however the tests are started) with a `load_script(name)` helper that loads a script from `plugins/cinemetric/skills/<name>/scripts/` by path under a unique module name
- [x] 1.2 Add a base test class in `tests/helpers.py` that blocks real network connections and points `XDG_CONFIG_HOME`, `XDG_DATA_HOME` and `HOME` at a per-test temporary folder, clearing the Plex and Tautulli environment variables
- [x] 1.3 Add a fake opener in `tests/helpers.py` that answers requests from fixture files (or inline data), records each request, and can simulate HTTP errors, redirects and connection failures
- [x] 1.4 Add a test that proves the network block works (a real connection attempt fails the test with a clear message)
- [x] 1.5 Add a short `tests/README.md` saying how to run the tests and the offline and no-real-data rules for fixtures

## 2. Shared security helpers (every script that has them)

- [x] 2.1 Test address checks: accept `http`/`https` with a host; refuse other schemes, missing host, username or password, `?` and `#`; strip a trailing slash (including `setup.clean_tautulli_url`)
- [x] 2.2 Test `looks_local` for private, loopback and link-local IPs, bare host names and `.local`/`.lan`/`.home.arpa`/`.internal`, and that public addresses are not local
- [x] 2.3 Test `clean`: control characters become spaces and text is cut to 120 characters
- [x] 2.4 Test the clients: a path outside the allowlist is blocked before any request, a Tautulli command outside the allowlist is blocked, every request is a GET, a redirect is refused, and the token or API key never appears in error messages
- [x] 2.5 Test HTTP 401, other HTTP errors and non-JSON replies give the expected safe error messages

## 3. library-report

- [x] 3.1 Test `resolution_bucket`, `is_ten_bit`, `is_unmatched` and `copies` with hand-built items
- [x] 3.2 Test `Tally` and `housekeeping` (missing posters, unmatched items, unavailable files, very large files)
- [x] 3.3 Test `library_duplicates` for movies and for episodes grouped by show, including the example limit
- [x] 3.4 Test `remember_guids` and `cross_library_duplicates` for the same title in two libraries
- [x] 3.5 Add small fixtures for `/`, `/library/sections` and `/library/sections/{id}/all` (movie and show libraries) and test `build_report` end to end, including totals, `--library` filtering, paging across more than one page, and a library name that matches nothing

## 4. server-health

- [x] 4.1 Test `worth_a_look` for each flag (update available, remote access not working, slow transcode, scheduled scans not running, automatic scans off, important maintenance disabled, high CPU, high memory) and for a report with nothing to flag
- [x] 4.2 Test `playback_method`, `stream_title` and the small helpers (`as_int`, `as_bool`, `days_ago`)
- [x] 4.3 Test `build_report` with fixtures, including a case where one part fails and is listed under `unavailable` instead of stopping the report

## 5. watch-activity

- [x] 5.1 Test `trend`, `stat_rows` and `hours` with hand-built data
- [x] 5.2 Test choosing a source: Tautulli when it is configured, Plex history otherwise, and the `OWNER_ONLY` and `TAUTULLI_NOT_CONFIGURED` errors
- [x] 5.3 Test `tautulli_report` and `plex_report` with fixtures

## 6. dashboard

- [x] 6.1 Test that `render` HTML-escapes every value taken from a report (titles, server name, user names) using a sample containing `<script>` and quotes
- [x] 6.2 Test `attention_items`, `overall_status` and `nice_step` with hand-built inputs
- [x] 6.3 Test that a failed report source shows an "unavailable" note instead of breaking the page, and that `collect` raises `NOT_CONFIGURED` when every source reports it (with `run_source` replaced by a fake)
- [x] 6.4 Test that the saved state and written page land in the temporary data folder with private permissions on POSIX

## 7. setup

- [x] 7.1 Test `write_private` and `read_private`: files are created readable only by the owner, and a damaged file raises `DamagedFile`
- [x] 7.2 Test `test_tautulli` and `tautulli_call` with a faked opener: success returns the version, a rejected key and a login request give the expected errors, and the API key is hidden in error messages
- [x] 7.3 Test that server names listed by `finish` are cleaned (control characters removed, cut to 120 characters) using a faked plex.tv response

## 8. Wrap up

- [x] 8.1 Run `python3 -m unittest discover -s tests` and confirm everything passes (Python 3.8 isn't installed here, so the test files were checked against Python 3.8's grammar instead)
- [x] 8.2 Check every fixture for real tokens, addresses or names
- [x] 8.3 Confirm no script changed, or that any change keeps behavior identical and was applied to every copy of a shared helper
- [x] 8.4 Add a one-line note to the README's Roadmap about optionally running the tests on GitHub (no version bump: nothing users see changes)
