## MODIFIED Requirements

### Requirement: Sources used
With Plex, the script SHALL request only `/`, `/accounts`, `/status/sessions/history/all`,
`/status/sessions` and `/:/prefs`. `/:/prefs` SHALL be read only for the media deletion setting (see "Media deletion setting" in the conventions spec). When Plex isn't configured, the setting isn't read
and `media_deletion_allowed` is `null`. With Tautulli, it SHALL run only `get_tautulli_info`, `get_home_stats`,
`get_history`, `get_plays_by_date` and `get_users`. Current sessions SHALL always come from Plex's
`/status/sessions`, whichever source the history comes from.

#### Scenario: Building a Tautulli report
- **WHEN** the report is built from Tautulli
- **THEN** only commands from that list are sent to Tautulli

#### Scenario: Current sessions with Tautulli as the source
- **WHEN** the history comes from Tautulli and Plex is set up
- **THEN** current sessions are read from Plex's `/status/sessions`, not from Tautulli
