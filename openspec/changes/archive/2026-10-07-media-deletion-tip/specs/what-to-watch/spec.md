## MODIFIED Requirements

### Requirement: Sources used
The script `skills/what-to-watch/scripts/what_to_watch.py` SHALL request only `/`,
`/library/sections`, `/library/sections/{id}/all`, `/library/sections/{id}/genre`, `/library/onDeck`
and `/:/prefs` from the user's Plex server, reading library items in pages of 500. `/:/prefs` SHALL be read only for the media deletion setting (see "Media deletion setting" in the conventions spec). It SHALL NOT contact Tautulli, plex.tv or any other address.

#### Scenario: Building a shortlist
- **WHEN** the script builds a shortlist
- **THEN** every request goes to the configured Plex server, to one of the six allowed paths, with
  `GET`

#### Scenario: Tautulli is set up
- **WHEN** Tautulli is configured
- **THEN** the script still makes no Tautulli request
