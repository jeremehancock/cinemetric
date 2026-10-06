# library-status-line Specification

## Purpose
The library status line: a mod, off by default, that shows one dim line above Claude Code's prompt
with the library's size and when Cinemetric last checked it, read from the snapshots on the user's
computer, without contacting the server.
## Requirements
### Requirement: Off by default, can be switched on
The library status line SHALL be a mod in the `cinemetric` plugin (see the `mods` spec) named
`status`, with its own switch, `library_status_line`, defaulting to off. When it is off it SHALL show
nothing and add no hooks except one that clears its line, so switching it off removes the line right
away. Anyone may switch it on or off, including Claude.

#### Scenario: Fresh install
- **WHEN** a user installs Cinemetric and changes no settings
- **THEN** no Cinemetric status line is shown

#### Scenario: Switching it on
- **WHEN** the user types `/cinemetric-mods status on`
- **THEN** the line appears above the prompt without a restart

#### Scenario: Switching it off
- **WHEN** the user types `/cinemetric-mods status off`
- **THEN** the line disappears without a restart

### Requirement: What the line shows
The mod SHALL show one dimmed line in its own row just above Claude Code's prompt, built from the
newest snapshot that the `changes` skill or the dashboard saved. It SHALL draw the row itself rather
than use Claude Code's status entry, which is shown with a notice icon that makes it look like a
warning. It SHALL draw nothing while Claude Code shows a survey in that row. The line reads:

`Plex: <movies> movies · <shows> shows · <albums> albums · <size> · checked <when>`

- `<movies>`, `<shows>` and `<albums>` SHALL be the totals of the `movies`, `shows` and `albums`
  counts across the snapshot's libraries, with thousands separators. A part whose total is zero or
  missing SHALL be left out.
- `<size>` SHALL be the total of the libraries' `size_gb`: in TB with one decimal at 1,000 GB or more,
  otherwise in GB with no decimals. It SHALL be left out when no library has a size.
- `<when>` SHALL be `today`, `yesterday` or `<n> days ago`, from the snapshot's file name (its date)
  and today's local date.

No text from the server (library names, titles, the server's name) SHALL appear in the line, so
nothing from the server can change what it says beyond the numbers.

#### Scenario: A typical library
- **WHEN** the newest snapshot, saved three days ago, has a movie library with 1,970 movies
  (20,078.8 GB), a TV library with 417 shows (38,907.7 GB) and a music library with 512 albums
  (412.0 GB)
- **THEN** the line is `Plex: 1,970 movies · 417 shows · 512 albums · 59.4 TB · checked 3 days ago`

#### Scenario: Only movies
- **WHEN** the newest snapshot, saved today, has one movie library with 240 movies (812.4 GB)
- **THEN** the line is `Plex: 240 movies · 812 GB · checked today`

### Requirement: Which snapshot it reads
The mod SHALL look in `<data folder>/snapshots/`, where the data folder is `CINEMETRIC_DATA_DIR` when
set; otherwise `%LOCALAPPDATA%\cinemetric` on Windows; otherwise `$XDG_DATA_HOME/cinemetric`, or
`~/.local/share/cinemetric` when `XDG_DATA_HOME` isn't set. Across every server folder in it, it
SHALL use the snapshot file (named `<YYYY-MM-DD>.json`) with the newest date. Folder and file names
that don't match the `changes` skill's patterns SHALL be ignored.

#### Scenario: Two servers
- **WHEN** one server folder's newest snapshot is from 2026-10-01 and another's is from 2026-10-05
- **THEN** the line is built from the 2026-10-05 snapshot

### Requirement: When there's nothing to show
When there is no snapshot, the line SHALL say `Plex: no snapshot yet · ask Claude "what changed on
Plex?"`. When the newest snapshot can't be read (too large for the mod to read, not valid JSON, not
format 1, or no library part), the line SHALL still say when it was checked, as
`Plex: checked <when>`. None of these SHALL be an error.

#### Scenario: Never run
- **WHEN** there is no snapshots folder
- **THEN** the line is `Plex: no snapshot yet · ask Claude "what changed on Plex?"`

#### Scenario: Damaged snapshot
- **WHEN** the newest snapshot file isn't valid JSON and is dated yesterday
- **THEN** the line is `Plex: checked yesterday`

### Requirement: Staying up to date
The mod SHALL build the line when a session starts and again after every turn ends, so a snapshot the
`changes` skill or the dashboard just saved shows up straight away, and the day count moves on in a
long session. It SHALL re-read a snapshot file only when the newest file changes.

#### Scenario: After a dashboard refresh
- **WHEN** the user asks Claude to refresh the dashboard, which saves today's snapshot
- **THEN** when that turn ends the line shows the new numbers and `checked today`

### Requirement: The status line's own safety rules
The mod SHALL make no network requests, start no programs and write no files. It SHALL read only the
snapshots folder.

#### Scenario: Building the line
- **WHEN** the line is built
- **THEN** the only files read are in the snapshots folder

