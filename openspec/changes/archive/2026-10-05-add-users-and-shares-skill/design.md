## Context

Every report script today talks only to the user's own Plex server (and Tautulli). That works because
the server knows its libraries, its streams and its history. It does not know who it's shared with:
shares, Plex Home members and invites are stored in the owner's plex.tv account. The server's own
`/accounts` list only shows people who have played something, with no library or permission details.

Setup already signs in through plex.tv and saves a token. For a server the user owns, that token is
the owner's account token, so it can read the owner's sharing information from plex.tv. For a server
someone shared with the user, plex.tv refuses, which is the right answer: only owners should see this.

Setup already has a pattern for talking to plex.tv safely: a `PLEX_TV_RULES` list of allowed
method-and-address pairs checked before anything is sent. This change reuses that pattern.

## Goals / Non-Goals

**Goals:**
- One overview of who can reach the server, what they can see, and what deserves a second look.
- Answer both directions: "what can Alex see?" and "who can see my Kids library?".
- Keep the plex.tv exception as small as possible: three `GET` addresses, one script.
- Never print anything about other people beyond what the owner needs to manage sharing.

**Non-Goals:**
- Changing anything: no inviting, removing, re-sharing or changing permissions. The skill points the
  user to Plex (**Settings → Manage Library Access** on app.plex.tv) for that.
- Watch history per person. `watch-activity` already covers who watches what; SKILL.md can suggest it.
- Showing shares on the dashboard. Could be a follow-up; the dashboard's "hide names" option would
  need to apply.
- Servers the user doesn't own. They get a clear `OWNER_ONLY` error.

## Decisions

**Source: plex.tv, read-only.** The user chose this over Tautulli-only or a plex.tv-plus-Tautulli
fallback. plex.tv is the only complete source (pending invites, current permissions, Plex Home), it
works for every owner without extra setup, and one code path is easier to test and to explain in
SECURITY.md. Tautulli's user list is only as fresh as its last sync and has no invites. (Tautulli is still used
for last played dates; see below.)

**Three plex.tv addresses, chosen for coverage:**
- `https://plex.tv/api/users`: everyone shared with or in Plex Home, with `home`/`restricted`
  (managed) markers, per-server `allLibraries`, `pending` and `lastSeenAt`, and filter attributes.
- `https://plex.tv/api/servers/<machine id>/shared_servers`: per person, the library sections shared
  on *this* server, `allowSync` (downloads), and invite/accept dates.
- `https://plex.tv/api/invites/requested`: outgoing invites not yet accepted, including ones to email
  addresses that aren't Plex accounts yet.

These are the older XML endpoints that the widely used `python-plexapi` library relies on. plex.tv's
API is not officially documented, so **the first implementation task confirmed each address and its
fields against a real owner account** before the parser was written (results below). Alternative considered: the newer `clients.plex.tv/api/v2/friends` JSON endpoints. They avoid
XML but, as far as is publicly known, don't give per-library shares in one call; if the check shows
otherwise, switching is a spec-level change to the allowlist and should be made then.

**What the confirmation step found (owner's real account, 2026-10-04).** Only shapes and counts were
printed, never names, emails or tokens.
- All three addresses answer `200` with XML and no `DOCTYPE`. `shared_servers` lists every library
  for each person with `shared="0"` or `"1"`, and every `Section` `key` matched a local section key.
  `shared_servers` carries `accessToken` and `email` for every person, as expected.
- Home and managed users appear in both responses (`home="1"`, managed also `restricted="1"`), and
  managed users have an empty `username`, so the name falls back to `title`/`name`.
- `lastSeenAt` showed "today" for all 11 people, including three with no play on the server for over
  500 days. It is useless for activity, so it isn't used.
- The one pending invite had `server="0"`: a plain friend request, giving no access to the server.
- A non-owner token couldn't be tested (no such account was available). The 401/403 handling follows
  what plex.tv returns for other owner-only calls and is covered by a test with a fake 403.

**Last played: Tautulli first, then Plex's own history.** Because `lastSeenAt` is useless, activity
comes from plays. The user chose to use Tautulli's `get_users_table` (one request, counts any play)
when it's set up, and the server's watch history otherwise: one request per accepted person to
`/status/sessions/history/all?accountID=<id>&sort=viewedAt:desc` with a page size of 1, about 0.1 s
each on the test server. plex.tv user ids match both the server's account ids and Tautulli's
`user_id`. Plex only records finished plays, so on the test server it gave older dates than Tautulli
for some people (for example 317 days against 23); `last_played_source` says which one was used so
SKILL.md can explain the difference. Alternatives considered: dropping activity entirely (simplest,
but loses the most useful flag), or Plex history only (no Tautulli path, less accurate).

**Matching libraries by section key.** plex.tv's `Section` entries carry the server's own section
`key` (confirmed), so each one is matched to `/library/sections` on the user's server and the
server's title is used. Unmatched sections (deleted libraries) are dropped.

**XML safety with the standard library.** `xml.etree.ElementTree` doesn't fetch external entities,
but very old expat versions can be slowed by nested entity tricks. Since plex.tv never needs a
`DOCTYPE`, the script refuses any response containing `<!DOCTYPE` or `<!ENTITY` and caps responses
at 5 MB before parsing. No third-party `defusedxml`, per the standard-library rule.

**Drop private fields while parsing, not when printing.** Each XML element is turned into a small dict
with only the allowed fields right away. Email, `accessToken` (plex.tv includes each friend's token
for the server in `shared_servers`), user ids, avatar URLs and the raw filter strings never enter the
report structure, so a later change to printing can't leak them. Tests feed fixtures full of fake
emails and tokens and assert none appear in stdout or stderr.

**plex.tv is always certificate-checked.** `verify_tls: false` exists for home servers with
self-signed certificates. plex.tv has a real certificate, so it never needs the exception, and
skipping it there would put the account token at risk.

**Owner check from plex.tv's answer.** The script reads `/` first (proves the token and gives the
machine id), then the shared servers address. A 401/403 there means the account doesn't own this
server, so it stops with `OWNER_ONLY`, reusing the existing error code and the SKILL.md wording style
from `watch-activity`.

**Flags kept short and factual.** `old_pending_invite` (30 days, fixed), `inactive` (configurable,
default 90 days), `all_libraries`, `downloads_allowed`. These are things an owner may want to act on,
but each can be perfectly intentional, so SKILL.md presents them as "worth a look", not problems.
"Library shared with nobody" is visible in `libraries` (`shared_with_count: 0`) but not flagged,
because that's the normal state for private libraries.

**Shared helpers copied, plus a small plex.tv client.** Per the conventions, `load_config`,
`validate_url`, `PlexClient` and `clean` are copied in. The plex.tv client is a small new function
modeled on setup's `plex_tv`, but `GET` only and with its own `PLEX_TV_RULES`.

## Risks / Trade-offs

- [plex.tv changes or retires the XML endpoints] → Each address is required or clearly optional in
  the spec; failures give a readable error rather than a wrong report. The first task verifies them
  against a real account, and tests pin the expected shapes with fixtures.
- [Widening the "only known destinations" rule worries users] → The exception is three exact `GET`
  addresses, in one script, enforced in code and covered by tests. SECURITY.md says so plainly.
- [Plex history only counts finished plays] → `last_played_source` says where each date came from,
  and SKILL.md says Plex-only dates can make someone look less active than they are.
- [One history request per person on servers shared with many people] → Each is a single small
  page; Tautulli replaces them all with one request when it's set up.
- [Plex Home owners see managed users with "all libraries" by default] → Flagging every managed user
  as `all_libraries` could be noisy; SKILL.md mentions it briefly for home and managed users.
- [Big friend lists] → Responses are small (one element per person); the 5 MB cap is generous.

## Migration Plan

Additive: a new skill and script. Existing skills, outputs and the dashboard are unchanged. Rollback
is removing the skill folder and reverting the spec, README, SECURITY.md and website edits.

## Open Questions

- Should the report have a `--hide-names` option like the dashboard? Not needed for a private,
  in-terminal report; revisit if shares are added to the dashboard.
- Is 30 days the right age for an "old" pending invite? Fixed for now; could become an option.
