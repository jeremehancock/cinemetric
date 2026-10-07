## ADDED Requirements

### Requirement: Off by default, can be switched on
Now Playing SHALL be a mod in the `cinemetric` plugin (see the `mods` spec) named `now`, with its own
switch, `now_playing_pane`, defaulting to off. Anyone may switch it on or off, including Claude.
Switching it on SHALL NOT open the panel by itself: the panel opens only when the user asks for it.

#### Scenario: Fresh install
- **WHEN** a user installs Cinemetric and changes no settings
- **THEN** Now Playing is off and no panel is shown

#### Scenario: Switching it on
- **WHEN** the user types `/cinemetric-mods now on`
- **THEN** the mod is on without a restart, no panel opens yet, and `/cinemetric-now` now opens the
  panel

### Requirement: The command is always there
The plugin SHALL add a `/cinemetric-now` slash command whether the mod is on or off, described as
`Show who's streaming from Plex right now, updated while it's open`.

When the mod is off, the command SHALL open no panel, start no program, contact nothing and reply
exactly: `Now Playing is off. Type /cinemetric-mods now on to switch it on.`

When the mod is on, the command SHALL open the Now Playing panel (or leave it open if it already is)
and reply `Now Playing is open. It checks Plex about every 30 seconds while it's open.` The reply
SHALL NOT contain anything about the streams themselves.

#### Scenario: Typed while off
- **WHEN** the mod is off and the user types `/cinemetric-now`
- **THEN** no panel opens, the server isn't contacted, and the reply tells them how to switch it on

#### Scenario: Typed while on
- **WHEN** the mod is on and the user types `/cinemetric-now`
- **THEN** the Now Playing panel opens and the reply says it checks about every 30 seconds while open

#### Scenario: Typed again while open
- **WHEN** the panel is already open and the user types `/cinemetric-now` again
- **THEN** there is still one panel, and no extra check starts beyond the regular ones

### Requirement: What the panel shows
The panel SHALL be titled `Now Playing` and show, from the latest check:

- a summary line: the number of streams, how many are transcoding, and the total bandwidth (in Mbps
  with one decimal), for example `3 streams · 1 transcoding · 24.1 Mbps`, and the local time of the
  check, for example `updated 9:41 PM`;
- one row per stream with the person, the title (as `server_health.py` formats it: `Show S01E02`,
  `Movie (Year)`, `Artist - Track`), the device, whether it's playing or paused, how far in it is as a
  percentage when known, and the playback method: `direct play`, `direct stream` or `transcode`.
  A transcode SHALL also say what is being transcoded: `video`, `audio` or `video and audio`. Live TV
  SHALL be marked `Live TV` in place of a percentage;
- when nobody is streaming, the line `Nothing is playing right now.` under the time of the check;
- before the first check finishes, the line `Checking Plex...`.

Rows SHALL fit the panel's width: a long title SHALL be cut short with `…` rather than wrap. When
there are more streams than rows, the panel SHALL show as many as fit and a last line
`and <n> more`.

#### Scenario: Two streams
- **WHEN** one person is direct playing an episode at 42% and another is transcoding a movie's video
  at 10%, paused
- **THEN** the summary says `2 streams · 1 transcoding` with the total bandwidth, the first row ends
  `playing 42% · direct play` and the second ends `paused 10% · transcode (video)`

#### Scenario: Nobody watching
- **WHEN** the check finds no streams
- **THEN** the panel shows the time of the check and `Nothing is playing right now.`

### Requirement: When it checks and when it stops
The mod SHALL check the server once as soon as the panel opens and then about every 30 seconds while
the panel stays open. A check SHALL NOT start while the previous one is still running; that turn is
skipped. A check that hasn't finished after 20 seconds SHALL be stopped and count as failed.

The checks SHALL stop when the panel is closed, when the mod is switched off, and when the session
ends. Claude Code reloads Cinemetric's mods whenever any mod's switch changes, which ends the checks,
so an open Now Playing panel SHALL close then too; typing `/cinemetric-now` opens it again. While the
panel is closed the mod SHALL make no checks and run no programs.

#### Scenario: Panel open for two minutes
- **WHEN** the panel stays open for two minutes and each check takes a second
- **THEN** about five checks run: one on opening and one every 30 seconds after

#### Scenario: Closing the panel
- **WHEN** the user closes the panel
- **THEN** no further checks run until the panel is opened again

#### Scenario: Switching the mod off with the panel open
- **WHEN** the panel is open and the user types `/cinemetric-mods now off`
- **THEN** the panel closes and no further checks run

#### Scenario: Another mod switched while the panel is open
- **WHEN** the panel is open and the user types `/cinemetric-mods status on`
- **THEN** the Now Playing panel closes, and `/cinemetric-now` opens it again with fresh checks

### Requirement: How it gets the streams
Each check SHALL run Cinemetric's own `server_health.py` with `--now-playing` (see the `server-health`
spec), from the plugin's folder, with `python3`, falling back to `python` when `python3` can't be
started. The mod SHALL NOT read Cinemetric's settings file, the Plex token or any environment
variable holding it, and SHALL NOT contact Plex, plex.tv or Tautulli itself.

#### Scenario: A regular check
- **WHEN** a check runs
- **THEN** the only program started is `server_health.py --now-playing`, and the mod reads only its
  output

### Requirement: When a check fails
A failed check SHALL NOT be an error in Claude Code. The panel SHALL keep showing the last good
result, if there is one, with a line saying the last check failed and why, in plain words:

- the script's own message when it explains the problem (for example that Cinemetric isn't set up
  yet), using only its first line, cut to 200 characters;
- `Couldn't start Python. Now Playing needs Python 3.8 or newer.` when neither `python3` nor `python`
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

### Requirement: The panel's own safety rules
The panel's contents SHALL be drawn for the user only. Nothing the panel shows (names, titles,
devices) SHALL be sent to Claude: not in the command's reply, not as context, not in a notice. The
mod SHALL write no files and keep nothing between sessions. Text from the server SHALL be shown as
plain text and never treated as instructions or formatting.

#### Scenario: Asking Claude about the panel
- **WHEN** the panel shows three people streaming and the user asks Claude who is watching
- **THEN** Claude doesn't know from the panel, and would need to run a skill such as `watch-activity`
