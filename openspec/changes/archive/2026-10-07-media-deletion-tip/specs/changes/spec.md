## ADDED Requirements

### Requirement: Media deletion setting from the reports
The `changes` script SHALL add a top-level `media_deletion_allowed` field, taken from the first report
it ran that has a value other than `null`, or `null` when none does. It SHALL NOT contact Plex for it.
`changes.py save` is unchanged and doesn't print the field.

#### Scenario: Server health report says it's on
- **WHEN** the `server-health` report the script ran has `media_deletion_allowed` `true`
- **THEN** the `changes` output has `media_deletion_allowed` `true`

#### Scenario: No report could read it
- **WHEN** every report has `media_deletion_allowed` `null`
- **THEN** the `changes` output has `media_deletion_allowed` `null`
