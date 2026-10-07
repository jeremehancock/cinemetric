## Context

Every skill script keeps its own copy of the shared helpers ("Self-contained scripts" in the
conventions spec). Comparing the copies found real drift: `library-report` and `server-health` (the
oldest scripts) still have an older `load_config`, `validate_url(url)`, `_NoRedirect` and a Plex
client that does its own error handling, and `clean` has three docstrings. The security tests list
scripts by hand and have missed `changes.py`'s `clean`.

## Goals / Non-Goals

**Goals:**
- Make drift between copies fail a test, with a message that says how to fix it.
- Make fixing a helper everywhere one command.
- Bring the two oldest scripts onto the current helpers.

**Non-Goals:**
- Moving helpers into a shared module. That changes the "Self-contained scripts" rule and is a
  separate decision.
- Making helpers that only share a name (`check`, `need_plex`, `choose_sections`, `as_bool`, ...)
  the same. They do different jobs in each script and aren't in the list.

## Decisions

**The list lives in `tools/shared_helpers.py`, and the test imports it.** The tool and the test then
can't disagree about which helpers must match. Alternative: the list in the test file. Rejected
because the copy tool would need its own list.

**Compare source text, after taking out the client name.** Comparing the text (found with `ast`)
catches every change, including messages and comments, and needs no running code. The only allowed
difference is the `"cinemetric-<skill>"` client name, which the comparison replaces with a
placeholder and the copy tool fills back in. Alternative: running the same behavior tests against
every copy. That's already done for the security helpers, but can't cover every helper.

**Exceptions are listed with a reason.** `setup` has its own `config_path` and `_NoRedirect`;
`library-report`, `server-health` and `users-and-shares` have their own `load_config`;
`server-health` has its own `PlexClient.get` (it accepts empty replies and `/butler`, which has no
`MediaContainer`). Each is named in the list so it's a decision, not drift.

**`library-report` and `server-health` keep a Plex-only `load_config`** returning
`(url, token, verify_tls)`, but built on the shared `read_config_file` and `validate_url`. Their
callers stay the same. `server-health` keeps its own `PlexClient.get` because `fetch_json` refuses
an empty reply.

**Tests find scripts by looking for the helper** (`hasattr` on each loaded script), with a check that
known scripts are found, so a renamed helper can't leave a check running against nothing.

## Risks / Trade-offs

- [Error wording in `library-report` and `server-health` changes] → The meaning is the same;
  `library-report/SKILL.md` is updated for the 401 wording, and `server-health`'s 401 message is
  unchanged because it keeps its own `get`.
- [Text comparison fails on a harmless difference, like a comment] → That's intended: the copy tool
  fixes it in one command.
