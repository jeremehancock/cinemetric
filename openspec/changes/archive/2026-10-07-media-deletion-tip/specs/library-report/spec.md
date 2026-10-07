## MODIFIED Requirements

### Requirement: Plex paths used
The script SHALL request only `/`, `/library/sections`, `/library/sections/{id}/all` and `/:/prefs`,
reading items in pages of 500. `/:/prefs` SHALL be read only for the media deletion setting (see "Media deletion setting" in the conventions spec).

#### Scenario: Large library
- **WHEN** a library has more than 500 items of a type
- **THEN** the script fetches them page by page until it has them all
