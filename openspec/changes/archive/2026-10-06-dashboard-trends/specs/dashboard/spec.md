## MODIFIED Requirements

### Requirement: Built from the other report scripts
The dashboard SHALL get its data by running `library_report.py` (with `--snapshot-items`),
`server_health.py` (with `--stuck-wait 0 --snapshot-items`; the dashboard doesn't show the stuck task
check and shouldn't wait for it), `watch_activity.py` (with `--days 30 --top 8 --recent 10`),
`users_and_shares.py` (with `--snapshot-items`), `unwatched.py` (with `--limit 10`),
`episode_gaps.py` (with `--limit 10`) and `playback_check.py` (with `--limit 0`) side by side, so it has exactly their read-only behavior. It SHALL never contact Plex, plex.tv or Tautulli itself.
A report that fails or runs longer than 30 minutes SHALL leave its section out, with the reason shown
on the page and in `sections_missing`. If every report fails, the dashboard SHALL fail with the first
error.

After the reports finish, the dashboard SHALL pass the library, server health and sharing reports
that succeeded to `changes.py save` on stdin, so a snapshot is saved without fetching anything again.
A failed save SHALL NOT stop the build; the page is still written and `snapshot_saved` is null.
Then, when the reports' `snapshot` blocks name one server id, the dashboard SHALL run
`changes.py trends --server-id <that id>` (whether or not the save worked) and use its output for the
Trends section. A trends run that fails, takes longer than 2 minutes or prints something that isn't a
JSON object SHALL NOT stop the build; the Trends section is then left out, and nothing is added to
`sections_missing`. The `snapshot` blocks SHALL NOT be put on the page.

#### Scenario: Watch activity fails
- **WHEN** the watch-activity script exits with an error
- **THEN** the page is still written, the watch section shows the reason, and `sections_missing` has
  a `watch` entry

#### Scenario: A Plex task is running while the dashboard builds
- **WHEN** the dashboard is built while Plex is scanning a library
- **THEN** `server_health.py` is run with `--stuck-wait 0` and the build doesn't wait for a second
  task check

#### Scenario: Connected to someone else's server
- **WHEN** `users_and_shares.py` fails with `OWNER_ONLY`
- **THEN** the page is still written with the other sections, the Sharing section explains that only
  the server owner can see who it's shared with (without the `OWNER_ONLY` code), and
  `sections_missing` has a `sharing` entry

#### Scenario: Unwatched report fails
- **WHEN** `unwatched.py` exits with an error
- **THEN** the page is still written with the other sections, the Unwatched section shows the reason,
  and `sections_missing` has an `unwatched` entry

#### Scenario: Episode gaps report fails
- **WHEN** `episode_gaps.py` exits with an error
- **THEN** the page is still written with the other sections, the Episode gaps section shows the
  reason, and `sections_missing` has an `episode_gaps` entry

#### Scenario: Playback report fails
- **WHEN** `playback_check.py` exits with an error
- **THEN** the page is still written with the other sections, the Playback section shows the reason,
  and `sections_missing` has a `playback` entry

#### Scenario: Saving the snapshot
- **WHEN** the dashboard is built and the library, server health and sharing reports succeed
- **THEN** `changes.py save` receives those three reports, today's snapshot is saved, and the build
  output has `snapshot_saved` with today's date

#### Scenario: Reading trends
- **WHEN** the dashboard is built and its reports' `snapshot` blocks name server id `abc123`
- **THEN** `changes.py trends --server-id abc123` runs after `changes.py save`

#### Scenario: Trends fail
- **WHEN** `changes.py trends` exits with an error
- **THEN** the page is still written without a Trends section, and `sections_missing` doesn't
  mention trends

## ADDED Requirements

### Requirement: Trends section
The page SHALL have a Trends section right after the Changes section, built from the output of
`changes.py trends`, with a subtitle giving the number of snapshot days and the first and last date.
It SHALL show up to three blocks:
- **Storage over time:** `library.total_size_gb` per date;
- **Titles per library:** for each listed library, its main count per date (`movies` for a movie
  library, `episodes` for TV, `albums` for music, `photos` for photos); a library with none of these
  counts, or whose count is 0 on every day, is left out;
- **People with access:** `sharing.people` per date, with that date's pending invites in the point's
  tooltip.

Each block SHALL show the first and latest value and the change between them next to its heading.
Charts SHALL be inline SVG with a wide and a narrow version, like the other charts. Points SHALL be
placed by date, so a longer gap between snapshots is a longer gap on the chart. Each point SHALL have
a tooltip with its date and value. A `null` value SHALL have no point and SHALL break the line. A
block whose series has fewer than two non-null values SHALL be left out. When every block is left
out, the section SHALL say in one line that trends appear once snapshots from two different days
exist.

The section SHALL state facts only, SHALL NOT add anything to the server's "Needs a look" list and
SHALL NOT change the page's overall status. Hiding names SHALL NOT change it, since it contains no
person's name. Library names SHALL be HTML-escaped.

#### Scenario: A month of snapshots
- **WHEN** trends has 30 dates with library and sharing values
- **THEN** the Trends section shows the storage chart, one chart per library and the people chart,
  each with its first value, latest value and change

#### Scenario: Only one day
- **WHEN** trends has one date
- **THEN** the Trends section says trends appear once snapshots from two different days exist, with
  no chart

#### Scenario: A gap in the snapshots
- **WHEN** trends has dates 10, 9 and 1 days ago
- **THEN** the space between the first two points is an eighth of the space between the last two

#### Scenario: Sharing missing on some days
- **WHEN** the people series is `null` on every day but the latest
- **THEN** the people block is left out and the other blocks are shown

#### Scenario: An empty library
- **WHEN** a DVR library's `movies` count is 0 on every day
- **THEN** it has no chart, and the other libraries do

#### Scenario: Nothing added to Needs a look
- **WHEN** storage went down between the first and latest date and the server has no other issues
- **THEN** the page's overall status is still "Healthy"

#### Scenario: A library name with HTML in it
- **WHEN** a library in trends is named `<b>Films</b>`
- **THEN** it appears as text on the page, not as markup
