## MODIFIED Requirements

### Requirement: The privacy section mentions the guard
The "Look, don't touch" section's intro SHALL mention that the read-only guard, on by default, can also stop
Claude from running its own commands that would change the server, and keeps Claude from seeing or
passing on the user's Plex token and Tautulli API key. The cards SHALL stay as they were, so they keep similar lengths.
The wording SHALL call it an extra safety net and SHALL NOT claim it catches everything.

#### Scenario: Reading the privacy section
- **WHEN** a visitor reads "Look, don't touch"
- **THEN** they see a short mention of the guard, covering both changes to the server and the token,
  that links to the Mods section

## ADDED Requirements

### Requirement: The guard's card mentions token protection
The read-only guard's card in the Mods section SHALL say, in plain words, that the guard also hides
the user's Plex token and Tautulli API key from what Claude sees, and stops Claude from putting
them in files, issues or pages. It SHALL NOT claim the token can never be seen, and SHALL keep the
card's length close to the other mod cards.

#### Scenario: Reading the guard's card
- **WHEN** a visitor reads the read-only guard's card
- **THEN** they learn it protects both the server and the token, worded as a safety net
