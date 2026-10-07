## MODIFIED Requirements

### Requirement: Sources used
The script `skills/episode-gaps/scripts/episode_gaps.py` SHALL request only `/`, `/library/sections`,
`/library/sections/{id}/all` and `/:/prefs` from the user's Plex server, reading library items in
pages of 500. `/:/prefs` SHALL be read only for the media deletion setting (see "Media deletion setting" in the conventions spec).
It SHALL NOT contact Tautulli, plex.tv, Plex's online metadata service or any other address. It
SHALL NOT use any source of how many episodes a season or show is meant to have.

#### Scenario: Building a report
- **WHEN** the script builds a report
- **THEN** every request goes to the configured Plex server, to one of the four allowed paths, with
  `GET`

#### Scenario: Tautulli is set up
- **WHEN** Tautulli is configured
- **THEN** the script still makes no Tautulli request
