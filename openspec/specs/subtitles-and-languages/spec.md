# subtitles-and-languages Specification

## Purpose

A read-only check of the audio and subtitle languages on a Plex server: files with audio in another
language and no full subtitles in the user's language, files with no full subtitles in that language,
tracks with no language set, and how many files have audio or subtitles in each language. It goes by
each track's language label and states facts only, never suggesting changes to files. Script:
`skills/subtitles-and-languages/scripts/subtitles_and_languages.py`. How Claude presents it is in the
skill's `SKILL.md`.

## Requirements
### Requirement: Sources used
The script `skills/subtitles-and-languages/scripts/subtitles_and_languages.py` SHALL request only `/`,
`/library/sections`, `/library/sections/{id}/all`, `/library/metadata/{ids}` and `/:/prefs` from the
user's Plex server, all with `GET`, reading library items in pages of 500. `{ids}` SHALL be 1 to 100
numeric rating keys separated by commas, and any other form SHALL be refused by the path allowlist.
From `/:/prefs` the script SHALL read only `allowMediaDeletion` (see "Media deletion setting" in the
conventions spec), requesting it at most once per run; no other setting SHALL appear in its output.
The script SHALL NOT contact Tautulli, plex.tv or any other address.

#### Scenario: Building a report
- **WHEN** the script builds a report, with or without Tautulli set up
- **THEN** every request goes to the configured Plex server, to one of the five allowed paths, with
  `GET`, and no Tautulli request is made

#### Scenario: Asking for too many titles at once
- **WHEN** the script tries to request `/library/metadata/` with 101 rating keys
- **THEN** it stops with the blocked request error and nothing is sent

### Requirement: Libraries and files checked
Only movie and TV libraries SHALL be checked; other libraries SHALL be named in `skipped_libraries`
with their type. Movies SHALL be read with the movie listing (`type=1`) and episodes with the episode
listing (`type=4`); in TV libraries each show's title and year SHALL come from the show listing
(`type=2`). Each media version of a title SHALL be checked as a separate file. A media version with a
`deletedAt` value SHALL be counted in `unavailable` and not checked. `--library NAME` (repeatable,
case-insensitive) SHALL limit the libraries checked, and SHALL stop the script with an error if
nothing matches, or if only libraries other than movie and TV libraries match.

Audio and subtitle tracks SHALL be read from the detail listing `/library/metadata/{ids}`, asking for
at most 100 titles per request. Tracks inside the file and separate subtitle files SHALL both count. A
title the detail listing doesn't return SHALL be counted in `details_missing`, and its files SHALL NOT
be checked for any finding or counted in the language summary.

#### Scenario: Music library
- **WHEN** the server has a music library
- **THEN** it is not checked and appears in `skipped_libraries` with type `artist`

#### Scenario: Asking for a music library
- **WHEN** run with `--library Music` and "Music" is a music library
- **THEN** the script stops with an error saying only movie and TV libraries are checked

#### Scenario: Requests in batches
- **WHEN** a TV library has 250 episodes
- **THEN** their details are read in 3 requests

#### Scenario: A title missing from the details
- **WHEN** the detail listing doesn't return one of the movies asked for
- **THEN** that movie is counted in `details_missing` and isn't listed under any finding

### Requirement: Reading a track's language
A track's language SHALL be the part of its `languageTag` before the first `-`, in lower case (so
`en-US` and `en` are both `en`), or, when `languageTag` is missing, its `languageCode` in lower case.
A track with neither, or whose language would be empty or one of the codes that mean "no particular
language" (`und`, `unk`, `mul`, `mis`, `zxx`), or that isn't 2 to 8 letters, SHALL have no
language. A language the user asks for
SHALL match a track when it equals the track's language or the track's `languageCode` (both in lower
case).

A file's main audio track SHALL be chosen with the rule in the `playback-check` spec's "TrueHD and DTS
audio" requirement: the track marked selected, otherwise the one marked default, otherwise the first.

A subtitle track SHALL count as full subtitles unless it is marked forced. Forced tracks usually only
cover signs or lines in another language, so they SHALL NOT count as subtitles for the findings, and
SHALL be shown separately. Subtitle tracks for the hearing impaired SHALL count as full subtitles.

#### Scenario: Region in the tag
- **WHEN** one track's `languageTag` is `en-US` and another's is `en`
- **THEN** both have the language `en`

#### Scenario: Asking with a three-letter code
- **WHEN** run with `--language eng` and a track has `languageTag` `en` and `languageCode` `eng`
- **THEN** the track matches

#### Scenario: No language on a track
- **WHEN** an audio track has neither `languageTag` nor `languageCode`
- **THEN** it has no language and counts toward `unknown_language`

#### Scenario: Labelled as unknown
- **WHEN** an audio track has `languageTag` `unk` and an empty `languageCode`
- **THEN** it has no language, counts toward `unknown_language`, and doesn't make the file count as
  `foreign_no_subtitles`

### Requirement: The user's language
`--language CODE` (repeatable, up to 5) SHALL set the user's languages for every library checked.
Each value SHALL be 2 or 3 letters, optionally followed by `-` or `_` and a region, which SHALL be
dropped. A three-letter bibliographic code that differs from Plex's code (for example `fre` for
`fra`, `ger` for `deu`, `chi` for `zho`) SHALL be turned into Plex's code. Any other value SHALL stop
the script with an error.

Without `--language`, each library SHALL use its own metadata language (the section's `language`,
read the same way as a track's `languageTag`). A library whose language is missing, isn't 2 or 3
letters, or is Plex's `xn` (no language) SHALL have `language` `null` and `language_problem`
explaining that `--language` is needed; its `foreign_no_subtitles`, `no_subtitles` and `forced_only`
counts and its `foreign_no_subtitles` and `no_subtitles` entries in `listed` and `more` SHALL be
`null`, and its other counts and summary SHALL still be reported.

Each library SHALL report `language`: `{"codes": [...], "source": "option"}` or
`{"codes": [...], "source": "library"}`.

#### Scenario: No option
- **WHEN** run without `--language` and the Movies library's language is `en-US`
- **THEN** Movies has `language` `{"codes": ["en"], "source": "library"}`

#### Scenario: Two languages asked for
- **WHEN** run with `--language en --language es`
- **THEN** every library has `language` `{"codes": ["en", "es"], "source": "option"}`, and a file with
  Spanish audio is never flagged under `foreign_no_subtitles`

#### Scenario: A bad value
- **WHEN** run with `--language english`
- **THEN** the script stops with an error saying a 2 or 3 letter language code is needed

#### Scenario: A library with no language
- **WHEN** run without `--language` and a library has no `language`
- **THEN** that library has `language` `null`, a `language_problem`, `null` for the two
  language findings and `forced_only`, and its unknown-language count and language summary are
  still given

### Requirement: Findings
Each checked file SHALL be tested for these findings, using the library's languages:
- `foreign_no_subtitles`: the file has at least one audio track with a language, none of its audio
  tracks is in the user's languages, and it has no full subtitle track in the user's languages.
- `no_subtitles`: the file has no full subtitle track in the user's languages, whatever its audio.
  Every file with `foreign_no_subtitles` also has `no_subtitles`.
- `unknown_language`: at least one of the file's audio or subtitle tracks has no language.

A file with no audio tracks SHALL NOT have `foreign_no_subtitles`. A file whose only subtitle tracks
in the user's languages are forced SHALL be counted in `forced_only` as well as in `no_subtitles`.

#### Scenario: A Japanese film with English subtitles
- **WHEN** the user's language is `en` and a file has only Japanese audio and an English SRT track
- **THEN** it has no `foreign_no_subtitles` and no `no_subtitles`

#### Scenario: A Japanese film with no English subtitles
- **WHEN** the user's language is `en` and a file has only Japanese audio and a French subtitle track
- **THEN** it has `foreign_no_subtitles` and `no_subtitles`

#### Scenario: An English dub
- **WHEN** the user's language is `en` and a file has Japanese audio, an English audio track and no
  subtitles
- **THEN** it has `no_subtitles` but not `foreign_no_subtitles`

#### Scenario: Only forced subtitles
- **WHEN** the user's language is `en` and a file has only Japanese audio and a forced English track
- **THEN** it has `foreign_no_subtitles` and `no_subtitles`, and is counted in `forced_only`

#### Scenario: Audio with no language
- **WHEN** a file's only audio track has no language and it has no subtitles
- **THEN** it has `unknown_language` and `no_subtitles`, but not `foreign_no_subtitles`

#### Scenario: An English film without subtitles
- **WHEN** the user's language is `en` and a file has English audio and no subtitles
- **THEN** it has `no_subtitles` only

### Requirement: Language summary
Each library SHALL give `audio_languages`: for each language, the number of checked files whose main
audio track is in it, and `subtitle_languages`: for each language, the number of checked files with at
least one full subtitle track in it. Tracks with no language SHALL count under `unknown`. Each SHALL
list at most 15 languages, most files first and then by code, with the rest added together under
`other`. The report SHALL give `language_names`: for each language code that appears anywhere in the
report, the language name Plex gives for it (its `language` field, cleaned), or `null` when Plex gives
none.

#### Scenario: A mostly English library
- **WHEN** a library has 90 files with English main audio, 8 Japanese and 2 with no language
- **THEN** `audio_languages` is `{"en": 90, "ja": 8, "unknown": 2}` and `language_names` has
  `"en": "English"` and `"ja": "Japanese"`

#### Scenario: Many subtitle languages
- **WHEN** a library's files have subtitles in 20 languages
- **THEN** `subtitle_languages` lists 15 of them and `other` adds up the files counted for the rest

### Requirement: Report contents
The JSON report SHALL contain `cinemetric_version`, `generated_at`, `server` (name, version),
`limits` (a fixed sentence saying the report goes by the language labels on each track, which can be
wrong or missing, that forced tracks aren't counted as full subtitles, and that a film mostly in the
user's language can still have short scenes in another language that this can't see), `libraries`,
`skipped_libraries`, `language_names`, `totals` and `media_deletion_allowed`.

Each entry in `libraries` SHALL have `name`, `type`, `language` (and `language_problem` when it
applies), `titles`, `files`, `unavailable`, `details_missing`, one count of files per finding
(`foreign_no_subtitles`, `no_subtitles`, `unknown_language`), `forced_only`, `audio_languages`,
`subtitle_languages`, `listed` and `more`. The counts SHALL cover every file checked.

`listed` and `more` SHALL each have one key per finding. In a movie library each list SHALL hold
movies with at least one file that has the finding, each with `title`, `year` (or `null`) and `files`:
the files with the finding, each with `resolution`, `main_audio_language`, `audio_languages` (every
audio track's language, `unknown` for none), `subtitle_languages` (full subtitle tracks),
`forced_subtitle_languages`, `unknown_audio_tracks` and `unknown_subtitle_tracks`. In a TV library each
list SHALL hold shows with at least one episode that has the finding, each with `title`, `year` (or
`null`), `episodes`, `episodes_flagged` and `audio_languages` (the main audio languages of the flagged
episodes, with counts). File paths SHALL NOT appear in the report.

Movies SHALL be sorted by title, and shows by `episodes_flagged` (most first) and then by title. Each
list SHALL hold at most `--limit` entries, and `more` SHALL say how many were left out of each.

`totals` SHALL give `titles`, `files`, `unavailable`, `details_missing`, one count per finding and
`forced_only` over all libraries checked; a library whose language findings are `null` SHALL count as
0 for them.

#### Scenario: A clean library
- **WHEN** no file in a library has any finding
- **THEN** each of its lists is empty, each `more` is 0, `limits` is still present and the script
  exits 0

#### Scenario: A show with some foreign episodes
- **WHEN** a show has 20 episodes and 3 of them have only Spanish audio and no English subtitles
- **THEN** its entry under `foreign_no_subtitles` has `episodes` 20, `episodes_flagged` 3 and
  `audio_languages` `{"es": 3}`

#### Scenario: Two versions of a movie
- **WHEN** a movie has one file with English subtitles and one without, and the user's language is `en`
- **THEN** it is listed under `no_subtitles` with only the file without subtitles

### Requirement: Options
The script SHALL accept `--language CODE` (repeatable, up to 5), `--library NAME` (repeatable),
`--limit N` (titles listed per finding per library, default 25, limited to 0–500) and `--check`.

#### Scenario: Counts only
- **WHEN** run with `--limit 0`
- **THEN** every list is empty and every count and summary is still filled in

#### Scenario: Too many languages
- **WHEN** run with six `--language` values
- **THEN** the script stops with an error saying at most 5 languages can be given

#### Scenario: Checking the connection
- **WHEN** run with `--check`
- **THEN** the script tests Plex once, prints the server name and version, and doesn't request
  `/:/prefs`
