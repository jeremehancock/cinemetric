## MODIFIED Requirements

### Requirement: Sources used
The script `skills/unwatched/scripts/unwatched.py` SHALL request only `/`, `/library/sections`,
`/library/sections/{id}/all`, `/status/sessions/history/all` and `/:/prefs` from the user's Plex
server, reading library items in pages of 500. `/:/prefs` SHALL be read only for the media deletion setting (see "Media deletion setting" in the conventions spec). With Tautulli it SHALL run only `get_tautulli_info` and `get_history`.
The library itself SHALL always come from Plex; only the plays can come from Tautulli.

#### Scenario: Building a report with Tautulli
- **WHEN** the report is built with Tautulli as the source of plays
- **THEN** every Tautulli request is `get_history`, and every Plex request is to one of the five
  allowed paths

#### Scenario: Tautulli only, no Plex
- **WHEN** Tautulli is set up but Plex isn't
- **THEN** the script stops with `error: NOT_CONFIGURED: ...`, because the library list only comes
  from Plex
