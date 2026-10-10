## Context

`export` is the first skill whose main result is a file for a spreadsheet program rather than an
answer in the chat. It saves one Excel workbook with six tabs: an overview of the server, the full
library list, and four tabs of things worth tidying up. The chat only gets a short summary: where the
file is, how many rows each tab has, and anything that couldn't be built.

The first version of this proposal saved a CSV file. CSV can't hold more than one table, so it was
changed to a workbook (`.xlsx`) when the user asked for tabs. Excel, Numbers, LibreOffice and Google
Sheets all open `.xlsx`.

It follows every existing rule: read-only toward Plex, standard library only, one self-contained
script, only the configured Plex server, server text cleaned, and private files. Three things are new
for Cinemetric and drive most of the decisions below:

- The file will be opened in spreadsheet programs, which can run formulas and follow links.
- The file may be saved in a folder the user names, which Cinemetric doesn't own.
- It combines its own library read with five other skills' reports, like the dashboard does.

Facts carried over from earlier checks against a real server (in the `collections-and-playlists`,
`watch-mix` and `what-to-watch` designs): library listings carry no `Collection` tags, so collections
need their own requests (206 collections took about 10 seconds); show listings carry `leafCount` and
`viewedLeafCount`, which `what-to-watch` already uses for watched status.

## Goals / Non-Goals

**Goals:**
- One workbook per run that opens cleanly in common spreadsheet programs, with plain-English tab and
  column names, numbers that sort as numbers and dates that sort as dates.
- Nothing in the file can run or reach out when it's opened.
- Every tab other than `Movies` and `TV Shows` says exactly what the matching skill says, because it comes from
  that skill's own script.
- The file is private by default, and Cinemetric never changes a folder or file the user owns
  without being asked.
- The lists stay in the file. The chat gets counts, not titles.

**Non-Goals:**
- A CSV option. The user chose a workbook only.
- Music and photo tabs. Their natural rows (tracks, albums, photos) and columns
  are different; could be a later option. They do appear in the `Server` tab's libraries table.
- Other people's viewing: no "last watched by", plays across everyone, transcodes by person or
  device, or users and shares. Those would put names in a file that may be shared. A possible
  `--with-people` option stays in `openspec/ideas.md`.
- Watch activity, unwatched titles, collections and playlists, watch mix or year in review tabs. Not
  asked for; easy to add later on the same plumbing.
- Genres and HDR on the `Movies` and `TV Shows` tabs (listings show at most two genres and have no HDR flag).
- Charts, colours or conditional formatting. The `dashboard` is the visual view.
- Uploading the file anywhere, or publishing it as a claude.ai page.

## Decisions

**Workbook built by hand with `zipfile`.** An `.xlsx` file is a zip of a few XML files: a content
types list, the workbook (tab names), one sheet file per tab, and a small styles file (bold for
column names, a date format). Python's `zipfile` and string building cover it, with no package to
install, which the "Standard library only" rule requires. Alternatives considered: OpenDocument
(`.ods`), which is the same idea but opens less smoothly in Excel and Numbers; and a folder of CSV
files, which loses the "one file with tabs" the user asked for.

**Text stored as inline strings, so nothing can run.** In a CSV, a spreadsheet program decides
whether a cell is a formula by looking at its first character, so titles starting with `=`, `+`, `-`
or `@` need escaping. In a workbook, each cell says what it is. Every text value is written as an
inline string (`<c t="inlineStr"><is><t>…</t></is></c>`), which spreadsheet programs show as text and
never run. A title like `-30-` therefore shows exactly as written, which the CSV plan couldn't do.
The script never writes a formula element, and the workbook has no macros (`.xlsx` can't hold them;
`.xlsm` can), external links, hyperlinks, data connections or embedded objects. The remaining risk is
the XML itself: a title made to close the cell early (for example containing `</t>`) is escaped like
any other text, and characters XML doesn't allow (some control characters, `U+FFFE`, `U+FFFF`, lone
surrogates) are removed, since a file containing them won't open. Inline strings were chosen over a
shared string table because they're simpler to write and check, and the size difference doesn't
matter at this scale once the zip compresses repeated text.

**Numbers and dates as real numbers and dates.** Sizes, counts and lengths are numbers, so sorting by
`Size (GB)` works. Dates are stored as spreadsheet date numbers with a `YYYY-MM-DD` format, so they
sort by date and the user can change the format. The column names row is frozen and has filter
buttons, which is what people expect from a list in a spreadsheet.

**`Server` first, as a cover page.** A workbook opens on its first tab. The server overview is short
and explains the rest (when it was made, whose watched status, which tabs were left out), so it comes
first, then the `Movies` and `TV Shows` lists, then the issue tabs from the most general (`Issues`) to the most
specific.

**The other tabs come from the other skills' scripts.** Like the dashboard, the export runs
`server_health.py`, `library_report.py`, `episode_gaps.py`, `playback_check.py` and
`subtitles_and_languages.py` side by side and turns their JSON into rows. That keeps one set of rules
per fact: an episode gap in the workbook is exactly what `episode-gaps` would report. Alternative
considered: working everything out inside `export.py`. That would copy hundreds of lines of rules
(duplicates, playback causes, language labels) that would then drift apart. The options passed to
each script:
- `--limit 500` (or `--duplicate-examples 500 --upgrade-examples 500`), the highest each allows, so
  the tabs list as much as possible. When a report has more, a note row says how many were left out.
- `library_report.py` with `--recent 0 --growth-months 0 --music-examples 0`, since those parts
  aren't used.
- `server_health.py` with `--stuck-wait 0`, so the export doesn't wait 15 seconds to recheck tasks.
- `playback_check.py` with `--days 0`, which skips its Tautulli part, so no person or device names
  come back and Tautulli isn't contacted.
A failed report leaves a note in its tab, not a failed export, as on the dashboard.

**Some issues come from the export's own read, not `library-report`.** `library-report` lists at
most 15 examples of files Plex can't find, unmatched titles and missing posters, which suits a chat
answer but not a spreadsheet meant to list everything. The export already reads every movie, show and
episode for the `Movies` and `TV Shows` tabs, and those three checks are one-line rules on fields it already has
(`deletedAt`, `guid`, `thumb`), using the same rules as `library-report`. So the `Issues` tab lists
every one of them. Duplicates, titles in more than one library and low-resolution titles have more
involved rules, so they come from `library-report`, up to 500 each.

**Nothing that changes moment to moment.** `server_health.py` reports the streams playing right now
(with people's names, devices and titles), CPU and memory use, and running tasks, and flags a slow
transcode, high CPU or memory, and tasks that may be stuck. The user chose to leave all of that out:
a spreadsheet is kept and looked at later, and a reading from the minute it was made would be out of
date by then (and, for streams, about someone's viewing). The Worth a look items about that moment
(`transcode_too_slow`, `high_cpu`, `high_memory`, `task_not_progressing`) go too, since they're drawn
from the same readings. The server's *settings* (hardware transcoding, remote limits, maintenance
hours) stay, since they describe how the server is set up and only change when someone changes them.

**Only named fields are copied from reports.** The
spec lists exactly which fields each tab uses, so a new field in another report can't slip into the
workbook unnoticed.

**A `Movies` tab and a `TV Shows` tab.** The first version had one `Library` tab with a `Type`
column; the user asked for movies and TV on separate tabs. The split is by kind, not one tab per Plex
library: every movie library goes on `Movies` and every TV library on `TV Shows`, told apart by the
`Library` column. Alternative considered: one tab per Plex library. Tab names are limited to 31
characters, can't contain `/`, `?` or `*`, and must differ from `Server` and `Issues`, so library
names would need changing to fit, and a server with many small libraries would get many tabs. Each tab
has only the columns that fit it (no empty `Season` column on `Movies`, no `Length` for whole shows),
and a tab is only there when a library of its kind is included.

**Shows by default, episodes on request.** A TV library is a list of shows to most people; a big
library has tens of thousands of episodes. `--tv episodes` gives one row per episode. A show row
summarizes its episodes: size is their total, and the media columns hold the value most episodes
have, because a show's episodes can differ and one "best" episode would mislead.

**Media details from the best version Plex can still find.** Highest resolution, then highest
bitrate, with versions that have `deletedAt` left out, as in `unwatched` and `watch-mix`. Size counts
every version still there, since that's what's on disk. Codecs and container are written as Plex
gives them (`hevc`, `eac3`, `mkv`), so they match what people see in Plex.

**Watched status for the signed-in account only.** The listing's `viewCount`, `viewOffset`,
`viewedLeafCount` and `lastViewedAt` describe the account Cinemetric signed in with, usually the
server owner. That gives a useful "have I seen it" column without reading anyone's history. The
`Server` tab and the summary say whose status it is.

**Collections read as `collections-and-playlists` reads them.** One list per library, then each
collection's children. A show row lists collections holding the show or any of its seasons or
episodes, and an episode row those holding the episode, its season or its show, so filtering on a
collection name finds everything in it in either mode. If collections can't be read, the export goes
ahead without them.

**Where the file goes.** By default, the data folder (`~/.local/share/cinemetric` on Linux), which is
private and where the dashboard and recap pages already go. That folder is hidden on most systems,
so SKILL.md tells Claude to give the full path and offer `--output` (for example to Documents or
Downloads).

- **A folder the user names is left alone.** The shared `write_page` helper creates its folder and
  sets it to `700`. Doing that to `~/Documents` would change the user's own folder, so the export has
  its own writer: for `--output` the folder must already exist and only the file is made `600`.
- **A file the user names is never replaced by surprise.** If it's there, the script stops with
  `FILE_EXISTS` before contacting Plex or running anything, and Claude asks the user before running
  again with `--replace`. In the data folder, Cinemetric's own file for the same day and libraries is
  simply replaced, like the dashboard.
- **Writing.** The zip is written to a temporary file in the same folder, created `600`, then moved
  over the target in one step. Without `--replace`, the move fails if a file has appeared at the
  target since the check (an `os.link` of the temporary file to the target, then removing the
  temporary name, falling back to a check and `os.replace` where hard links aren't supported). On any
  failure the temporary file is removed.

**File names never contain raw server text.** With `--library`, the name includes each library in
lower case with everything other than letters and digits turned into `-`, so a library called
`../Kids/Movies` can't send the file into another folder.

**The summary has no titles.** Printing thousands of titles into the chat would be slow and would put
the whole library in the conversation. The summary gives rows per tab and library, the path, and what
couldn't be read. SKILL.md tells Claude not to read the workbook back into the chat unless the user
asks about something in it.

## Risks / Trade-offs

- [Running five reports takes a while, the playback and subtitle checks most] → They run side by
  side. Measured on a real server (1,970 movies, 419 shows with 18,939 episodes) on 2026-10-09:
  `server_health.py` 1 second, `episode_gaps.py` 28, `library_report.py` 39, `playback_check.py` 151
  and `subtitles_and_languages.py` 156, so about 2.5 minutes in all; the export's own episode listing
  took 17 seconds. SKILL.md tells Claude to say it may take a few minutes, and
  `--skip playback --skip subtitles` gives a quick export.
- [A hand-built workbook a program won't open, or "repairs"] → Kept to the smallest set of parts
  that Excel requires; tested by opening real files in Excel or LibreOffice and Google Sheets (task
  1.3), and the tests check every part is valid XML and listed in the content types.
- [The file is copied, emailed or uploaded later] → It holds no one's name or viewing history, only
  the library, the server's details and the signed-in account's own watched status. SKILL.md says the
  workbook lists the whole library, so the user knows what they're sharing. The server's public
  address is left out, as `server-health` already does.
- [The user saves the workbook as CSV later and reopens it] → Then the spreadsheet program decides
  again what's a formula. Outside Cinemetric's control; noted in SKILL.md only if the user asks about
  CSV.
- [People's names inside a report the export reads] → Checked on a real server: besides the live
  streams, `server_health.py`'s `transcode_too_slow` item carries the person's name and title. Both
  are left out entirely, as is everything else about streams now.
- [Another report's JSON changes shape] → The export's tests use those scripts' own output shapes
  from fixtures, and the spec names every field used, so a change shows up as a failing test.
- [Data folder is hard to find] → The full path is always in the summary, and `--output` is offered.

## Open Questions

- Should the default place be the user's Downloads folder instead of the data folder, since that's
  where people look for a file they just made? Going with the data folder, as `ideas.md` decided,
  with Claude offering `--output`.
