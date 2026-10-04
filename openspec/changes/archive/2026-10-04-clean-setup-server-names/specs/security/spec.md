## MODIFIED Requirements

### Requirement: Server text is treated as data
In every script, titles, names, version strings and other text from Plex, plex.tv or Tautulli SHALL
have control characters removed and be cut to 120 characters before they are printed. The dashboard
SHALL HTML-escape every value it puts on the page.

#### Scenario: A title with a newline in it
- **WHEN** a media title contains control characters
- **THEN** they are replaced with spaces in the script's output

#### Scenario: A shared server with a crafted name
- **WHEN** setup's `finish` lists a server whose name contains control characters or is longer than
  120 characters
- **THEN** the listed name has the control characters replaced with spaces and is cut to 120
  characters
