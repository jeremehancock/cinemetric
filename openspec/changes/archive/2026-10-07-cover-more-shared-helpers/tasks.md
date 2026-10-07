## 1. Line up drifted copies

- [x] 1.1 Copy `as_bool` from `server-health` into every script that has one
- [x] 1.2 Copy `get_all` from `episode-gaps` into every script that has one
- [x] 1.3 Copy `day` from `show-progress` into `unwatched` and `what-to-watch` (already the same) and leave `users-and-shares` as an allowed exception
- [x] 1.4 Copy `PersonError` from `show-progress` and `when` from `server-health`

## 2. Extend the list

- [x] 2.1 Add the page, playback, title matching, history, stream and script-running helpers and the lined-up helpers to `SHARED`, with the allowed exceptions and reasons
- [x] 2.2 Add the `DIFFERENT_JOBS` note for same-name helpers that do different jobs

## 3. Check

- [x] 3.1 `python3 tools/shared_helpers.py` reports every helper matching
- [x] 3.2 `python3 -m unittest discover -s tests` passes
- [x] 3.3 Loosening `CSP` in `dashboard.py` alone makes the test fail
