## ADDED Requirements

### Requirement: Media deletion setting
Every script that reads from the user's Plex server (`setup`, `library-report`, `server-health`,
`watch-activity`, `users-and-shares`, `unwatched`, `what-to-watch`, `episode-gaps`, `playback-check`
and `year-in-review`) SHALL report whether Plex's "Allow media deletion" setting is on, in a
top-level `media_deletion_allowed` field. The script SHALL request `/:/prefs` at most once per run and
take the value of the `allowMediaDeletion` setting as a boolean. Every other setting in that answer
SHALL be discarded without being printed. The field SHALL be `null` when Plex isn't configured, when
the request fails for any reason (including 401 or 403 on a server the user doesn't own), or when the
setting is missing. A `null` SHALL NOT stop the report, change its exit code or add an entry to
`unavailable`. `--check` and `server-health`'s `--now-playing` mode SHALL NOT request `/:/prefs`.
The helper that reads it, `media_deletion_allowed`, is a shared helper as described in
"Self-contained scripts".

#### Scenario: Media deletion allowed
- **WHEN** a report script runs and `/:/prefs` has `allowMediaDeletion` set to `true`
- **THEN** the report has `media_deletion_allowed` `true`

#### Scenario: Media deletion switched off
- **WHEN** `/:/prefs` has `allowMediaDeletion` set to `false`
- **THEN** the report has `media_deletion_allowed` `false`

#### Scenario: Not the server owner
- **WHEN** `/:/prefs` answers 403
- **THEN** `media_deletion_allowed` is `null`, the rest of the report is built as usual, the script
  exits 0 and nothing about it is added to `unavailable`

#### Scenario: Secrets in the settings answer
- **WHEN** `/:/prefs` also returns `PlexOnlineToken` and other settings
- **THEN** none of their ids or values appear anywhere in the output

#### Scenario: Connection check
- **WHEN** a script runs with `--check`
- **THEN** `/:/prefs` isn't requested

### Requirement: Mentioning media deletion
Every `SKILL.md` whose output can include `media_deletion_allowed` (directly or, for `changes` and
`dashboard`, through the reports they run) SHALL tell Claude: when it is `true`, end the reply with one
short, friendly line saying that Plex is set to let apps delete media files and that switching off
"Allow media deletion" (Settings, Library) makes sure Claude can't delete the user's media files through
Plex (Plex then refuses deletions from every app, including its own). The line SHALL make clear that
stopping Claude is the reason for the tip. Claude SHALL mention it at most
once per conversation, SHALL NOT put it in a headline or call it a problem, and SHALL say nothing about
it when the field is `false` or `null`. `server-health`'s `SKILL.md` MAY place the line under "Worth a
look" instead of at the end.

#### Scenario: First report in a conversation
- **WHEN** the user runs a skill and the report has `media_deletion_allowed` `true`
- **THEN** Claude's reply ends with the one-line tip

#### Scenario: Second report in the same conversation
- **WHEN** Claude already gave the tip earlier in the conversation
- **THEN** the next report doesn't repeat it

#### Scenario: Setting unknown
- **WHEN** `media_deletion_allowed` is `null`
- **THEN** Claude doesn't mention media deletion
