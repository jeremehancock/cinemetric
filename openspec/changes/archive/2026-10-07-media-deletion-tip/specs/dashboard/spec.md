## ADDED Requirements

### Requirement: Media deletion tip
The dashboard SHALL take `media_deletion_allowed` from the first report it ran that has `true` or
`false`, without contacting Plex for it, and SHALL include it in the build output (`null` when no
report has it). When it is `true`, the Server card SHALL end with a short tip saying that Plex is set
to let apps delete media files and that switching off "Allow media deletion" (Settings, Library) makes
sure Claude can't delete the user's media files through Plex. The tip SHALL NOT be a "needs a look" item and SHALL NOT change the overall
status, because Plex has the setting on by default. When it is `false` or `null`, no tip SHALL be
shown.

#### Scenario: Media deletion allowed
- **WHEN** the dashboard is built and a report has `media_deletion_allowed` `true`
- **THEN** the Server card ends with the tip, and the overall status and "needs a look" list are the
  same as without it

#### Scenario: Media deletion switched off
- **WHEN** the reports have `media_deletion_allowed` `false`
- **THEN** no tip is shown
