## MODIFIED Requirements

### Requirement: When a check fails
A failed check SHALL NOT be an error in Claude Code. The panel SHALL keep showing the last good
result, if there is one, with a line saying the last check failed and why, in plain words:

- the script's own message when it explains the problem (for example that Cinemetric isn't set up
  yet), using only its first line, cut to 200 characters;
- `Couldn't start Python. Now Playing needs Python 3.10 or newer.` when neither `python3` nor `python`
  starts;
- `Plex took too long to answer.` when a check is stopped after 20 seconds;
- `Couldn't read Plex's answer.` when the output isn't what the mod expects.

The next check SHALL go ahead as normal, and a good result SHALL clear the line.

#### Scenario: Not set up
- **WHEN** Cinemetric isn't connected to a Plex server and the panel is opened
- **THEN** the panel says the check failed with the script's message about running setup

#### Scenario: Server briefly unreachable
- **WHEN** one check fails after earlier ones worked
- **THEN** the panel still shows the earlier streams, with a line saying the last check failed
