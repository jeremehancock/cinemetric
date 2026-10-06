## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: Options
The script SHALL accept `--inactive-days N` (days without a play that count as inactive, and the
window used for library activity; default 90, at least 1) and `--check` (test the connections to the
user's server and to plex.tv, and print the server name and version without building a report).

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
