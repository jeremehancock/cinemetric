## Context

"Allow media deletion" (Settings, Library) decides whether Plex will delete media files when an app
asks. With it off, no app can delete media through Plex, Claude included. It's Plex's own lock, so it
protects people even when the read-only guard isn't running (older Claude Code, mods switched off).

SECURITY.md and the website recommend switching it off. The plugin itself never checks it. The user
wants every skill to mention it when it's on, not only the server health check.

Each skill script is self-contained and has its own `ALLOWED_PATHS` list. `server-health` and
`playback-check` already read `/:/prefs`, and both keep only the settings they need, because the same
answer holds secrets such as `PlexOnlineToken`. `changes` and `dashboard` don't contact Plex
themselves; they run other scripts and combine their JSON.

## Goals / Non-Goals

**Goals:**
- Every report that reads from Plex knows whether media deletion is allowed.
- Claude mentions it in a short, friendly line when it's on, without nagging.
- Reading the setting can never break or slow down a report in a noticeable way.

**Non-Goals:**
- Changing the setting. Cinemetric stays read-only; the user switches it off in Plex.
- Checking at session start or in the background.
- Any change to the read-only guard.

## Decisions

### Each script reads the setting itself
Every script that talks to Plex adds a copied helper, `media_deletion_allowed(client)`, which requests
`/:/prefs`, looks for the `allowMediaDeletion` setting and returns `True`, `False` or `None`. The
result goes in a top-level `media_deletion_allowed` field.

*Alternative considered:* check once in `setup` and save the answer in the config file. Rejected: the
answer goes out of date the moment the user changes the setting, so a report could keep telling them
to switch off something they already switched off.

*Alternative considered:* a SessionStart hook. Rejected: it would contact Plex with the token every
time Claude Code starts, even when Cinemetric isn't used. The existing startup notice never touches the
network.

### Never fail, never report as unavailable
Any error (401/403 on a server the user doesn't own, a timeout, a server without the setting) gives
`null`. It isn't added to a script's `unavailable` list, since it isn't part of what the user asked
for. A `null` means Claude says nothing.

### One request per run
`server-health` and `playback-check` already read `/:/prefs`; they reuse that one answer. In
`playback-check`, `/:/prefs` is now requested even with `--max-bitrate`, because the tip needs it.
`--check` and `--now-playing` don't read it: `--check` tests the connection only, and `--now-playing`
runs every few seconds for the Now Playing panel.

### `changes` and `dashboard` reuse their child reports
They run several report scripts already. Each takes `media_deletion_allowed` from the first child
report that has a non-null value, so neither adds a request of its own. The dashboard shows it as a
quiet tip at the end of the Server card, not as a "needs a look" item: any item there turns the
overall status from "Healthy" to "Mostly fine", and with Plex's default most servers would show that
for a setting that isn't a problem.

### Wording and frequency
Every `SKILL.md` gets the same instruction: when `media_deletion_allowed` is `true`, end the reply
with one line, for example: "Tip: Cinemetric only reads from your server, but Plex is set to let apps
delete media files. To make sure Claude can't delete your movies, shows or music through Plex, switch
off Allow media deletion (Settings, Library). Plex then refuses deletions from every app, including
its own." Claude mentions it at most once per conversation, never in a headline, and never as a problem
with the server.

Once per conversation needs no saved state: Claude can see whether it already said it. Across
conversations it will come up again, which is the point, since the setting may still be on.

### `server-health` explains it a little more
`server-health` already reports settings as facts and never advises a change. This tip is the one
exception, because it's about what Claude itself can do to the server, not about how the owner runs
Plex. Its `SKILL.md` places the line under "Worth a look" instead of at the end, with a sentence on
why it matters. It isn't added to `worth_a_look` in the script, so the fact lives in one field.

## Risks / Trade-offs

- [Most servers have it on, so most users see the tip] → One line, once per conversation, at the end
  of the reply, and never in the headline. If users find it too much, a later change can add a way to
  dismiss it.
- [`/:/prefs` holds secrets] → Each helper reads only `allowMediaDeletion` and discards the rest, as
  `playback-check` already does. Tests check that no other setting's id or value reaches the output.
- [Plex renames or removes the setting] → The field becomes `null` and Claude says nothing; the
  SECURITY.md advice is unaffected.
- [Ten copies of the helper] → The conventions spec already requires a fix to one copy to be made to
  every copy; the helper is a few lines.
- [Shared (not owned) servers] → Plex refuses `/:/prefs` to non-owners, so the field is `null` and
  nothing is said. That's fine: only the owner can change the setting anyway.

## Open Questions

- Should the user be able to turn the tip off (for example a config key)? Left out for now; easy to
  add if it proves noisy.
