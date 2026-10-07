## MODIFIED Requirements

### Requirement: Tests check the specs
Tests SHALL check behavior that the specs in `openspec/specs/` require, and SHALL NOT check details
the specs leave open. At least the following SHALL be covered:
- `library-report`: duplicates within and across libraries, media breakdown (resolution buckets,
  10-bit), housekeeping, report totals, the snapshot area, and `since_snapshot` (titles, episodes,
  unavailable files, new, removed and renamed libraries).
- `security`: address checks, path and command allowlists, refusing redirects, hiding credentials in
  error messages, and cleaning server text, for every script that has these; and skipping bad
  snapshot files and cleaning snapshot text, for every script that reads snapshots.
- `server-health`: the "things worth a look" flags, partial results when one part fails, the
  snapshot area and `since_snapshot`.
- `watch-activity`: choosing a source and the report built from each source.
- `dashboard`: HTML escaping of every value from a report, handling a report source that failed,
  saving a snapshot through the changes script, the changes section (including names hidden), and
  the Trends section (too few days, gaps between dates, `null` values, a failed trends run).
- `setup`: Tautulli address cleaning and private file permissions.
- `users-and-shares`: the plex.tv address rules, the owner-only error, dropping emails and access
  tokens, the people and libraries in the report, the "things worth a look" flags, the snapshot area
  (only the allowed details) and `since_snapshot`.
- `unwatched`: choosing a source, which plays count (finished only, every account), which titles are
  listed (cutoff, show added dates), sizes, and the report totals.
- `what-to-watch`: watched status for movies and shows, each filter, merging the same title across
  libraries, sorting and the limit, and continue watching.
- `episode-gaps`: what counts as there (duplicates, unavailable files, multi-episode file names,
  unnumbered episodes), specials, gaps inside a season, late starts, numbering that carries on,
  missing seasons, date-numbered seasons, sorting and the limit, and the report totals.
- `playback-check`: each cause (image-based subtitles with and without a text alternative, forced
  tracks, TrueHD and DTS with and without a common track, bitrate with the server limit, the option
  and no limit), separate media versions, unavailable files, detail batches and titles missing from
  them, grouping transcodes by device and person, the reasons from stream data and the 200 cap,
  dropping private Tautulli fields, Tautulli missing or failing, sorting and the limit, and the report
  totals.
- `changes`: choosing which snapshot to compare with (earlier day, `--since`, missing area, other
  server), saving and merging the same day, pruning after 90 days, `save` without network, `list`,
  `forget`, file permissions, a report that fails, and `trends` (lining up with `dates`, missing areas,
  renamed and removed libraries, old and damaged files, no names, a bad server id).
- `year-in-review`: choosing a source, the year's edges and a partial year, each scope (`server`,
  `--me`, `--user`), hours with pauses left out and `null` hours from Plex, months and the busiest
  month and day (including ties and future months), top list ranking, `--min-viewers` and
  `held_back`, no names, ids or device names anywhere in a whole-server recap's JSON or page, HTML
  escaping and the Content Security Policy on the page, file names and permissions, nothing
  played, the saved destination (first run, saved choice, separate from the dashboard's), and each
  recap's online link (kept per recap, link and recap id checks, forget).
- `title-lookup`: exact and "contains" matches, narrowing by year, library and type, the same title
  in two libraries, several matches and no match, `--key`, finding an episode and an episode not on
  the server, collections and the cut summary, separate media versions and unavailable files, the
  same playback causes as `playback-check` for the same made-up files, the show's seasons and
  playback summary with detail batches, each history source with finished and unfinished plays and
  episodes finished, history refused without failing the report, and dropping private Tautulli
  fields.

#### Scenario: A shared helper is fixed in one script only
- **WHEN** a fix to `validate_url`, `clean` or the snapshot reading helper is applied to one script
  but not the others
- **THEN** a test for one of the other scripts fails, because the same checks run against every
  script's copy

#### Scenario: A change breaks duplicate detection
- **WHEN** a change to `library_report.py` stops two copies of the same movie from being reported as
  duplicates
- **THEN** a test fails

#### Scenario: A change leaks a friend's email
- **WHEN** a change to `users_and_shares.py` lets an email address from a plex.tv fixture into the
  output
- **THEN** a test fails

#### Scenario: A partly watched title counts as played
- **WHEN** a change to `unwatched.py` treats a Tautulli play with `watched_status` 0.5 as finished
- **THEN** a test fails

#### Scenario: A started show counts as unwatched
- **WHEN** a change to `what_to_watch.py` lets a show with some episodes watched match `--unwatched`
- **THEN** a test fails

#### Scenario: A snapshot copies more about people than allowed
- **WHEN** a change to `users_and_shares.py` puts a last played date or email into the sharing
  snapshot area
- **THEN** a test fails

#### Scenario: Specials show up as gaps
- **WHEN** a change to `episode_gaps.py` reports missing episodes for season 0, or for a season that
  continues the previous season's numbering
- **THEN** a test fails

#### Scenario: A text subtitle alternative is ignored
- **WHEN** a change to `playback_check.py` flags a file whose English PGS track also has an English
  SRT track, with neither forced nor default
- **THEN** a test fails

#### Scenario: A change puts a viewer's name in a whole-server recap
- **WHEN** a change to `year_in_review.py` lets a person's name, or a title only one person watched,
  into a whole-server recap's JSON or page
- **THEN** a test fails

#### Scenario: Playback rules drift apart
- **WHEN** a change to `title_lookup.py` or `playback_check.py` makes the two scripts give different
  playback causes for the same made-up file
- **THEN** a test fails
