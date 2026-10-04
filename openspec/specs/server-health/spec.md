# server-health Specification

## Purpose

A read-only snapshot of how a Plex server is doing right now: version and updates, remote access, CPU
and memory, live streams, background tasks, library scans and maintenance. Script:
`skills/server-health/scripts/server_health.py`. How Claude presents it is in the skill's `SKILL.md`.

## Requirements

### Requirement: Plex paths used
The script SHALL request only `/`, `/updater/status`, `/myplex/account`, `/statistics/resources`,
`/status/sessions`, `/activities`, `/butler`, `/:/prefs` and `/library/sections`.

#### Scenario: Building the report
- **WHEN** the script builds a report
- **THEN** every request goes to one of those paths

### Requirement: Only maintenance settings are kept
From `/:/prefs` the script SHALL keep only the settings in `PREF_IDS` (maintenance window start and
end hour, scan on folder change, scheduled scans and their interval) and discard everything else
without printing it. The server's public address SHALL be left out of the remote access details.

#### Scenario: Reading server settings
- **WHEN** `/:/prefs` returns all of the server's settings
- **THEN** the report contains only the five maintenance settings

### Requirement: Partial results instead of failure
Only `/` is required. Every other part (update check, remote access, CPU and memory, live activity,
running tasks, library scans, maintenance tasks, maintenance settings) SHALL be optional: if it fails,
the part is `null` and listed in `unavailable` with a reason. A 401 or 403 on an optional part SHALL be
reported as "only available to the server owner's account", since the token already worked for `/`.

#### Scenario: Connected to a shared server
- **WHEN** the user isn't the server owner and `/updater/status` returns 403
- **THEN** `server.update` is `null` and `unavailable` lists "update check" as only available to the
  server owner's account

### Requirement: Options
The script SHALL accept `--stale-days N` (days without a library scan that count as overdue, default
7, at least 1).

#### Scenario: Custom threshold
- **WHEN** run with `--stale-days 14`
- **THEN** only libraries not scanned for more than 14 days count as overdue

### Requirement: Live streams
For each stream, the report SHALL give the user, title, type, player, platform, state, whether it's
Live TV, progress, source quality, bandwidth, LAN/WAN location and playback method: "direct play" (no
transcode session), "transcode" (video or audio is transcoded) or "direct stream" (anything else).
Transcodes SHALL also include the video and audio decisions, hardware use, speed and whether they're
throttled. Totals SHALL count streams by method and add up bandwidth overall and by LAN/WAN.

#### Scenario: Nothing playing
- **WHEN** no one is streaming
- **THEN** `live_activity.streams` is empty and the totals are zero

### Requirement: Things worth a look
The script SHALL flag facts for Claude to explain in `worth_a_look`, each with a `kind`:
- `update_available`: Plex reports a newer release.
- `remote_access_not_working`: remote access state is anything other than `mapped`.
- `transcode_too_slow`: a transcode is not throttled and runs below 1x speed.
- `scheduled_scans_not_running`: scheduled scans are on and a library, not scanning now, hasn't been
  scanned for more than `--stale-days` days.
- `automatic_scans_off`: both scheduled scans and scanning on folder change are off.
- `important_maintenance_disabled`: database backup, database optimization, old bundle cleanup or old
  cache cleanup is off.
- `high_cpu` (average host CPU ≥ 85%) and `high_memory` (average host memory ≥ 90%).

When only folder-change scanning is on, an old last-scanned date SHALL NOT be flagged, because those
small scans don't update it.

#### Scenario: Only folder-change scanning
- **WHEN** scheduled scans are off, scanning on folder change is on, and a library was last scanned a
  month ago
- **THEN** nothing about scans is flagged
