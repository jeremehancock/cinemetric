# users-and-shares Specification

## Purpose

A read-only overview of who can reach a Plex server: friends, Plex Home members, managed users and
pending invites, which libraries each person can see, and when they last played something. Who a
server is shared with is only stored in the owner's plex.tv account, so this is the one report that
also reads from plex.tv. Script: `skills/users-and-shares/scripts/users_and_shares.py`. How Claude
presents it is in the skill's `SKILL.md`.
## Requirements
### Requirement: What the script requests
The script `skills/users-and-shares/scripts/users_and_shares.py` SHALL request only `/`,
`/library/sections` and `/status/sessions/history/all` from the user's Plex server, and only these
plex.tv addresses, each with `GET`:
- `https://plex.tv/api/users` (everyone the owner shares with or has in Plex Home),
- `https://plex.tv/api/servers/<machine id>/shared_servers` (which libraries each person can see on
  this server),
- `https://plex.tv/api/invites/requested` (invites the owner sent that haven't been accepted).

`<machine id>` SHALL come from the `machineIdentifier` that the user's server reports at `/`, and
SHALL contain only letters and digits. These addresses SHALL be listed in the script's
`PLEX_TV_RULES`, and any other plex.tv address SHALL be refused before it is sent. When Tautulli is
set up, the script SHALL run only the Tautulli commands `get_users_table` and `get_history`.

#### Scenario: Building the report
- **WHEN** the script builds a report
- **THEN** every request goes to an allowed path on the configured server, to one of the three
  plex.tv addresses, or to Tautulli's `get_users_table` or `get_history`, and every request is a `GET`

#### Scenario: A strange machine id
- **WHEN** the server's `/` reports a `machineIdentifier` containing `/` or `?`
- **THEN** the script stops with an error and makes no plex.tv request

### Requirement: plex.tv connection rules
Requests to plex.tv SHALL send the configured Plex token only in the `X-Plex-Token` header, SHALL
always check plex.tv's HTTPS certificate (even when `verify_tls` is `false` for the user's own
server), SHALL NOT follow redirects, and SHALL time out like requests to the user's server. Responses
SHALL be read as XML only after refusing any response that contains a `<!DOCTYPE` or `<!ENTITY`
declaration or is larger than 5 MB.

#### Scenario: verify_tls is off for the user's server
- **WHEN** the config has `"verify_tls": false`
- **THEN** requests to the user's server skip the certificate check, but requests to plex.tv still
  check it

#### Scenario: A response with an entity declaration
- **WHEN** a plex.tv response contains `<!ENTITY`
- **THEN** it is not parsed, and that part of the report is treated as failed

### Requirement: Owner only
Only the server owner's account can see who a server is shared with. If `/` works but plex.tv answers
401 or 403 for the shared servers address, the script SHALL fail with `error: OWNER_ONLY: ...`,
explaining that only the server owner can see who it's shared with. A 401 from the user's own server
at `/` SHALL be reported as a rejected token, as in the other skills.

#### Scenario: Connected to someone else's server
- **WHEN** the user is connected to a server a friend shared with them, and plex.tv answers 403 for
  that server's shared servers
- **THEN** the script stops with `error: OWNER_ONLY: ...` and prints no report

### Requirement: Other people's private details are dropped
For each person, the script SHALL keep only: display name (their Plex username, or their Plex Home
name when they have no username), kind, status, libraries, download permission, whether content
restrictions are set, when they were invited, and when they last played something. Email addresses,
access tokens, user ids, avatar addresses and the content of restriction filters SHALL be discarded
when the response is read and SHALL NOT appear in the output or in any error. A pending invite with
no username SHALL be named `invited by email` instead of showing the address.

#### Scenario: A friend's entry includes an access token
- **WHEN** a shared server entry from plex.tv contains `accessToken` and `email` attributes
- **THEN** neither value appears anywhere in the script's output

#### Scenario: Invite sent to an email address
- **WHEN** a pending invite has an email address but no username
- **THEN** that person's name in the report is `invited by email`

### Requirement: Who counts as a person with access
`people` SHALL list everyone in the shared servers response for this server, matched to their entry
in `https://plex.tv/api/users` by user id, plus invites from `https://plex.tv/api/invites/requested`
that share this server (`server="1"`, and naming this server if the invite lists servers) and
aren't already listed. A shared server entry with no
`acceptedAt` date, or whose users entry marks this server `pending`, SHALL have `status` `pending`.
Invites that don't share the server (plain friend requests, `server="0"`) SHALL be left out, because
they give no access. The owner SHALL NOT be listed.

#### Scenario: A friend request with no server
- **WHEN** the owner sent a friend request that doesn't share any server
- **THEN** that person is not in `people`

#### Scenario: An invite to share the server
- **WHEN** an invite shares this server and hasn't been accepted
- **THEN** that person is in `people` with `status` `pending` and `libraries` `null`

### Requirement: Last played
Each accepted person SHALL have `last_played` (date of their most recent play on this server, or null
if none is known) and `last_played_source`:
- `tautulli`: Tautulli is set up and its `get_users_table` gives a last-seen date for that person,
  matched by Plex user id. Tautulli counts any play, including ones not finished.
- `plex`: otherwise, the most recent entry in the server's own watch history for that person
  (`/status/sessions/history/all` filtered by their account id, newest first, one entry). Plex only
  records plays that were finished or nearly finished.
- `null`: no play was found in either.

If Tautulli is set up but `get_users_table` fails, the script SHALL use Plex's history for everyone
and list "Tautulli last played dates" in `unavailable`. If a Plex history request fails, that person's
`last_played` is null and `unavailable` lists "Plex watch history" once. Pending people SHALL have
`last_played` null and `last_played_source` null, with no requests made for them. plex.tv's
`lastSeenAt` SHALL NOT be used: it was found to show the current day for every user.

#### Scenario: Tautulli knows the person
- **WHEN** Tautulli is set up and its users table has a last-seen date for a friend
- **THEN** that friend's `last_played` is Tautulli's date and `last_played_source` is `tautulli`, and
  no Plex history request is made for them

#### Scenario: No Tautulli
- **WHEN** Tautulli isn't set up and a friend last finished something 40 days ago
- **THEN** their `last_played` is that date and `last_played_source` is `plex`

#### Scenario: Tautulli is down
- **WHEN** Tautulli is set up but `get_users_table` times out
- **THEN** every accepted person's date comes from Plex's history and `unavailable` lists "Tautulli
  last played dates"

### Requirement: Report contents
The JSON report SHALL contain:
- `server`: name, version and number of libraries.
- `people`: one entry per person, with `name`, `kind` (`friend`, `home` for a Plex Home member with
  their own account, or `managed` for a managed user), `status` (`accepted` or `pending`),
  `libraries` (`"all"` when they were given all libraries, a sorted list of library names, or `null`
  when unknown), `allow_downloads` (true, false or null when unknown), `content_restrictions` (true
  when any restriction filter is set), `invited`, `last_played` and `last_played_source`. People SHALL
  be sorted by kind (home, managed, friend), then name.
- `libraries`: one entry per library on the server, with its `title`, `type`, `shared_with` (names of
  accepted people who can see it, sorted, counting `"all"` as every library; pending people can't
  see anything yet), `shared_with_count`, `played_by` (the names in `shared_with` who played
  something from it in the last `--inactive-days` days, sorted, or null when unknown) and
  `played_by_count` (or null).
- `library_activity`: where library plays came from and the window they cover (see "Library
  activity").
- `totals`: number of people by kind and by status.
- `worth_a_look`: flagged facts (see "Things worth a look").
- `unavailable`: parts that couldn't be read, each with a reason.

Library names SHALL come from the user's server, matched by section key. A library that plex.tv lists
for a person but that the server no longer has SHALL be left out of that person's list.

#### Scenario: A friend with two libraries
- **WHEN** a friend has accepted a share of "Movies" and "TV Shows" only
- **THEN** their entry has `kind` `friend`, `status` `accepted`, `libraries` `["Movies", "TV Shows"]`,
  and both libraries list them in `shared_with`

#### Scenario: A friend with all libraries
- **WHEN** a friend was given all libraries
- **THEN** their `libraries` is `"all"`, and every library lists them in `shared_with`

#### Scenario: A library shared with nobody
- **WHEN** no one but the owner can see "Home Videos"
- **THEN** that library's `shared_with` is empty, `shared_with_count` is 0, `played_by` is empty and
  `played_by_count` is 0

#### Scenario: Nobody to share with
- **WHEN** the owner hasn't shared the server with anyone and has no Plex Home members
- **THEN** `people` is empty, every library's `shared_with_count` is 0, and the script exits 0

### Requirement: Partial results instead of failure
`/`, `/library/sections`, `https://plex.tv/api/users` and the shared servers address are required:
if any fails, the script SHALL stop with an error. The invites address, Tautulli and Plex's watch
history are optional: if one fails, the report is built without it and `unavailable` lists the part
with the reason.

#### Scenario: Invites can't be read
- **WHEN** `https://plex.tv/api/invites/requested` times out
- **THEN** the report still lists everyone else, and `unavailable` lists "pending invites"

### Requirement: Options
The script SHALL accept `--inactive-days N` (days without a play that count as inactive, and the
window used for library activity; default 90, at least 1), `--check` (test the connections to the
user's server and to plex.tv, and print the server name and version without building a report),
`--since DAYS` (which snapshot `since_snapshot` compares with, limited to 1–90; see "Reading
snapshots" in the conventions spec) and `--snapshot-items` (add the `snapshot` block).

#### Scenario: Custom inactive threshold
- **WHEN** run with `--inactive-days 30`
- **THEN** people whose last play was more than 30 days ago are flagged as inactive, and each
  library's `played_by` covers the last 30 days

#### Scenario: Testing the connection
- **WHEN** run with `--check`
- **THEN** it requests `/` and `https://plex.tv/api/users` once each and prints the server name and
  version

### Requirement: Things worth a look
The script SHALL flag facts for Claude to explain in `worth_a_look`, each with a `kind` and either the
names of the people involved (`people`) or, for `unused_library`, the titles of the libraries involved
(`libraries`):
- `old_pending_invite`: people still pending more than 30 days after they were invited.
- `inactive`: accepted people whose `last_played` is more than `--inactive-days` days ago, or who have
  no play at all and were invited more than `--inactive-days` days ago. People whose `last_played` and
  `invited` are both null SHALL NOT be flagged.
- `all_libraries`: people given all libraries, so any library added later is shared with them too.
- `downloads_allowed`: friends who can download from the server.
- `unused_library`: libraries with at least one person in `shared_with`, an empty `played_by`, and at
  least one person in `shared_with` who was invited more than `--inactive-days` days ago or has no
  invite date. It carries `days`. It SHALL be left out when `played_by` is unknown or
  `library_activity.complete` is false.

Each kind SHALL appear at most once, listing everyone (or every library) it applies to. A kind with
nothing to list SHALL be left out.

#### Scenario: An invite from last year
- **WHEN** an invite was sent 200 days ago and is still pending
- **THEN** `worth_a_look` has an `old_pending_invite` item listing that person

#### Scenario: Never played, shared long ago
- **WHEN** a friend accepted a share 300 days ago and has never played anything
- **THEN** they are flagged as `inactive`

#### Scenario: Nothing known
- **WHEN** an accepted person has no `last_played` and no `invited` date
- **THEN** they are not flagged as `inactive`

#### Scenario: Two friends can download
- **WHEN** two friends have downloads allowed
- **THEN** `worth_a_look` has one `downloads_allowed` item listing both names

#### Scenario: A shared library nobody plays from
- **WHEN** "Fitness" is shared with two friends invited a year ago and neither played anything from
  it in the last 90 days
- **THEN** `worth_a_look` has one `unused_library` item with `days` 90 listing "Fitness"

#### Scenario: Shared only recently
- **WHEN** "Kids" is shared only with a friend invited 10 days ago who hasn't played from it yet
- **THEN** "Kids" is not in an `unused_library` item

#### Scenario: Private libraries aren't flagged
- **WHEN** "Home Videos" is shared with nobody
- **THEN** it is not in an `unused_library` item

#### Scenario: History cut short
- **WHEN** the 100,000-play cap is reached before the start of the window
- **THEN** `library_activity.complete` is false and there is no `unused_library` item

### Requirement: Library activity
The script SHALL work out, for each library, which of the accepted people who can see it played
something from it in the last `--inactive-days` days, by reading watch history newest first, in
pages of 1,000:
- `tautulli`: when Tautulli is set up, `get_history` with `after` set to the first day of the window,
  read once per library with `section_id` set to that library's key, because Tautulli's history rows
  don't say which library a play came from. Each row's `user_id` says who played. Unfinished plays
  count.
- `plex`: otherwise, `/status/sessions/history/all` sorted by `viewedAt` descending, read once for
  all libraries, using each entry's `accountID` and `librarySectionID`. Plex only records finished or
  nearly finished plays.

Each read SHALL stop at the first page that reaches past the start of the window or a page shorter
than asked for, and all reading SHALL stop after 100,000 plays in total. Plays SHALL be matched to people by the same user id used for last played,
and to libraries by section key compared as text. Plays with no library, from a library the server
no longer has, by the owner, or by anyone not in that library's `shared_with` SHALL be ignored.

The report SHALL include `library_activity` with `source` (`tautulli`, `plex` or null), `days` (the
window) and `complete` (false when the 100,000-play cap was reached before the start of the window).

If Tautulli is set up but `get_history` fails, the script SHALL read Plex's history instead and list
"Tautulli library activity" in `unavailable`. If Plex's history then fails too (or Tautulli isn't set
up and Plex's history fails), `source` SHALL be null, every library's `played_by` and
`played_by_count` SHALL be null, and `unavailable` SHALL list "library activity". This part is
optional: it SHALL NOT stop the report.

#### Scenario: A friend only watches TV
- **WHEN** a friend can see "Movies" and "TV Shows" and, in the last 90 days, only played episodes
  from "TV Shows"
- **THEN** "TV Shows" lists them in `played_by` and "Movies" does not

#### Scenario: Owner's plays don't count
- **WHEN** the only plays from "Home Videos" in the window are by the server owner
- **THEN** "Home Videos" has an empty `played_by` and `played_by_count` 0

#### Scenario: Tautulli is set up
- **WHEN** Tautulli is set up and its history shows a friend started, but didn't finish, a movie from
  "Movies" 10 days ago
- **THEN** "Movies" lists that friend in `played_by`, `library_activity.source` is `tautulli`, and
  there is one `get_history` read per library, each with that library's `section_id`

#### Scenario: Tautulli history fails
- **WHEN** Tautulli is set up but `get_history` times out and Plex's history works
- **THEN** `library_activity.source` is `plex` and `unavailable` lists "Tautulli library activity"

#### Scenario: No history at all
- **WHEN** Tautulli isn't set up and Plex's history request fails
- **THEN** every library's `played_by` is null, `library_activity.source` is null, `unavailable` lists
  "library activity", and the rest of the report is built as normal

#### Scenario: Reading stops at the window
- **WHEN** the first page of history already reaches back past the start of the window
- **THEN** no second page is requested and `library_activity.complete` is true

### Requirement: Sharing snapshot area
With `--snapshot-items`, the report SHALL include `snapshot`: `server_id` (the server's
`machineIdentifier` from `/`) and `area` with `people`, each with only `name`, `kind`, `status`,
`libraries` and `allow_downloads`, as in `people`. Last played dates, invite dates, content
restrictions, emails, ids and tokens SHALL NOT be in it. Without `--snapshot-items`, `snapshot` SHALL
NOT be in the output.

#### Scenario: What is kept about a friend
- **WHEN** the report has a friend with a last played date and content restrictions
- **THEN** that friend's snapshot entry has only `name`, `kind`, `status`, `libraries` and
  `allow_downloads`

### Requirement: Sharing changes since the last snapshot
The report SHALL include `since_snapshot`, comparing with the `sharing` area of the snapshot chosen as
in "Reading snapshots" (conventions spec), or `null` when there is none. People SHALL be matched by
`name` and `kind`. It SHALL contain `snapshot_date`, `days_ago` and:
- `added`: people now listed who weren't, with `kind` and `status`;
- `removed`: people listed before who aren't now;
- `accepted`: people whose `status` went from `pending` to `accepted`;
- `libraries_changed`: people whose `libraries` changed, with `gained` and `lost` library names, or
  `from` / `to` when either side is `"all"`. Unknown (null) on either side is not a change;
- `downloads_changed`: people whose `allow_downloads` changed between true and false, with `to`;
- `email_invites_change`: the change in the number of pending people named `invited by email`, since
  those can't be told apart.

#### Scenario: A new friend
- **WHEN** a friend is in today's report but not in the snapshot
- **THEN** `added` lists them with `kind` `friend`

#### Scenario: Given a new library
- **WHEN** a friend could see Movies before and can now see Movies and TV Shows
- **THEN** `libraries_changed` lists them with `gained` `["TV Shows"]` and `lost` `[]`

#### Scenario: Two email invites
- **WHEN** the snapshot had one `invited by email` and today there are three
- **THEN** `email_invites_change` is 2 and they are not listed in `added`

