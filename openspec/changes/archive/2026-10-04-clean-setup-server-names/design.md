## Context

The report scripts each carry a `clean(text)` helper: it replaces control characters with spaces,
trims the ends, and cuts the text to `MAX_TITLE_LENGTH` (120). `setup.py` has no such helper. It
takes in outside text in three places and later prints it:

- `cmd_finish` stores `res.get("name")` for each server from `clients.plex.tv`, then prints it and
  reuses it in `select`'s "could not reach" error.
- `test_server` returns the server's `friendlyName`, which `select` prints.
- `test_tautulli` returns Tautulli's `tautulli_version`, which is printed by `tautulli-auto` and
  `tautulli`, saved into the form status file, and printed again by `tautulli-wait`.

## Goals / Non-Goals

**Goals:**
- Every piece of outside text that setup prints has been cleaned the same way as in the report scripts.
- The fix stays easy to check: one helper, applied where the text comes in.

**Non-Goals:**
- Cleaning values setup saves to the config file. Those are addresses and credentials, which must
  stay exact.
- Changing the form page, which already HTML-escapes everything it shows.

## Decisions

**Clean where the text comes in, not where it's printed.** Cleaning in `cmd_finish`, `test_server` and
`test_tautulli` covers every later use: printed output, the error message, the pending sign-in file
and the form status file. Cleaning at each output point instead would mean five or six call sites, and
a new output added later could easily miss one.

**Copy the helper, don't share it.** The conventions spec requires each script to run on its own, with
shared helpers copied into each script that needs them. `setup.py` gets the same `clean` and
`MAX_TITLE_LENGTH` as the report scripts, word for word.

**Keep the placeholders.** A missing name or version still shows as `?`, as today. `clean` turns a
missing value into an empty string, so apply the `or "?"` after cleaning.

## Risks / Trade-offs

- [A sign-in started before the update has an uncleaned name in its pending file] → That file only
  lasts until `select` or `cancel`; the next `finish` writes cleaned names. Not worth handling.
- [Two servers whose names differ only after the 120th character look the same in the list] →
  Unlikely, and the list is numbered and shows ownership, so the user can still tell them apart.
