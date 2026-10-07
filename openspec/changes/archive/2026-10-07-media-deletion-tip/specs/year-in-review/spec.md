## MODIFIED Requirements

### Requirement: Sources used
With Plex, the script SHALL request only `/`, `/accounts`, `/status/sessions/history/all` and
`/:/prefs`. `/:/prefs` SHALL be read only for the media deletion setting (see "Media deletion setting" in the conventions spec). When Plex isn't configured, the setting isn't read and
`media_deletion_allowed` is `null`. With
Tautulli, it SHALL run only `get_tautulli_info`, `get_history` and `get_users`. Source choice SHALL
work as in `watch-activity`: `--source auto` (the default) uses Tautulli if it's configured and falls
back to Plex otherwise, recording why in `fallback_reason`; `--source tautulli` fails with
`TAUTULLI_NOT_CONFIGURED` if it isn't set up and never falls back; `--source plex` uses Plex only.

#### Scenario: Building a recap from Tautulli
- **WHEN** the recap is built from Tautulli
- **THEN** only commands from that list are sent to Tautulli and no Plex path outside the list is
  requested

#### Scenario: Tautulli is down
- **WHEN** Tautulli is configured but can't be reached and `--source` is `auto`
- **THEN** the recap comes from Plex and `fallback_reason` says Tautulli failed and why
