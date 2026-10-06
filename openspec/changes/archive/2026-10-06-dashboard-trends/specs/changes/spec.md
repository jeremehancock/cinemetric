## ADDED Requirements

### Requirement: Trends
`changes.py trends --server-id ID` SHALL read that server's snapshot files dated within the last 90
days (today included) and print, oldest first. Without `--server-id` it SHALL use the server whose
folder has the most recent snapshot. It SHALL print:
- `server_id` (null when it isn't letters and digits) and `dates`: the date of every readable
  snapshot (see "Snapshots are read as data" in the security spec);
- `library`: `total_size_gb` (the sum of every library's `size_gb` that day) and `libraries`, one
  entry per library in the newest snapshot that has a `library` area, in that snapshot's order, each
  with `key`, `name` and `type` from that snapshot, `size_gb`, and `counts` holding one list per count
  name that library has in that snapshot;
- `sharing`: `people` (the number of entries in that day's sharing area), `home`, `managed` and
  `friend` (those entries by `kind`) and `pending` (those whose `status` is `pending`).

Every list SHALL have one value per date, lined up with `dates`. A value SHALL be `null` when that
day's snapshot has no such area, or has a library area without that library, or without that count.
Libraries SHALL be matched by key, so a renamed library keeps its earlier values. The output SHALL
contain no titles and no people's names. A server id that isn't letters and digits, or a server
with no readable snapshots, SHALL give empty `dates` and lists, not an error. The script SHALL make no
network requests and run no other script.

#### Scenario: A month of snapshots
- **WHEN** snapshots exist for 30 different days and `trends` runs with that server's id
- **THEN** `dates` has 30 dates, oldest first, and every library and sharing list has 30 values

#### Scenario: A day without the sharing area
- **WHEN** one day's snapshot has `library` and `health` but no `sharing`
- **THEN** that day's values in every `sharing` list are `null` and its library values are filled in

#### Scenario: A renamed library
- **WHEN** library key `3` was called "Films" in older snapshots and "Movies" in the newest
- **THEN** one library entry with key `3` and name "Movies" holds the values from every day

#### Scenario: A removed library
- **WHEN** a library is in older snapshots but not in the newest one
- **THEN** it has no entry in `libraries`, and its sizes still count toward the older days'
  `total_size_gb`

#### Scenario: Old and damaged files
- **WHEN** the folder has a snapshot dated 95 days ago and one that isn't valid JSON
- **THEN** neither date appears in `dates` and the command succeeds

#### Scenario: No names
- **WHEN** `trends` runs for a server shared with a friend called "Sam"
- **THEN** "Sam" appears nowhere in the output

#### Scenario: No server id given
- **WHEN** snapshots exist for two servers, the newest one for server `def456`, and `trends` runs
  without `--server-id`
- **THEN** it prints `def456`'s trends

#### Scenario: A strange server id
- **WHEN** `trends` runs with `--server-id ../x`
- **THEN** it prints empty `dates` and lists, exits 0, and reads nothing outside the snapshots folder
