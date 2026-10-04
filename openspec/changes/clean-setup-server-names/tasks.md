## 1. Add the helper

- [x] 1.1 Copy `MAX_TITLE_LENGTH` and `clean` into `setup.py`, word for word from `library_report.py`

## 2. Clean outside text where it comes in

- [x] 2.1 `cmd_finish`: clean each server's `name` before storing and printing it
- [x] 2.2 `test_server`: clean the server's `friendlyName`, keeping `?` when it's missing
- [x] 2.3 `test_tautulli`: clean the version, keeping `?` when it's missing

## 3. Verify

- [x] 3.1 With a fake plex.tv server list containing a name with control characters and over 120 characters, confirm `finish` prints it cleaned
- [x] 3.2 With fake server and Tautulli responses, confirm `select` and `tautulli-auto` print cleaned names and versions, and `?` when missing
- [x] 3.3 Confirm `clean` in `setup.py` is identical to the copies in the report scripts

## 4. Release

- [x] 4.1 Bump the version to 0.3.2 in all five scripts, `plugin.json` and `marketplace.json`
