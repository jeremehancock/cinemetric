## MODIFIED Requirements

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

## ADDED Requirements

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
