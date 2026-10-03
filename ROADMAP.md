# Cinemetric roadmap

What's planned for Cinemetric after the first two skills (`setup` and `library-report`). Plans can
change; feedback and ideas are welcome via GitHub issues.

## Ground rules for every skill

- **Read-only.** No skill ever changes anything on your Plex server (or Tautulli).
- **No extra installs.** Scripts use only the Python standard library, like the existing ones.
- **Same shape as today.** Each skill is a `SKILL.md` plus a script that prints a JSON report for
  Claude to turn into plain English (see `plugins/cinemetric/skills/library-report/`).
- **Reuse the safe parts.** New scripts use the same config loading, address checks and GET-only Plex
  client as `library_report.py` (`load_config`, `validate_url`, `PlexClient`), so tokens stay in the
  private config file and never appear in the chat.

## Planned skills

Listed in the order they're likely to be built.

### 1. `server-health` (done)

- [x] **Server basics**: Plex version, whether an update is available, platform, and whether remote
      access is working
- [x] **Live activity**: who's streaming right now, what they're watching, direct play vs transcode,
      and bandwidth use
- [x] **Background tasks**: scheduled maintenance, recent library scans, and tasks running now
- [ ] **Failed or stuck tasks**: Plex doesn't report task failures through its API, so this needs
      another source (for example its logs) before it can be added

### 2. `watch-activity` (done)

- [x] Use **Tautulli** when it's set up, for full watch history and stats
- [x] Fall back to **Plex's own watch history** when Tautulli isn't available (less detail)
- [x] Report most watched titles and users, recent plays, and watch time trends
- [x] Add an optional Tautulli step to `setup` (address and API key saved in the same private config
      file, never shown in the chat)

### 3. `dashboard` (done)

- [x] One comprehensive Plex dashboard combining the library report, server health and watch activity
- [x] A private HTML page on your computer
- [x] Kept up to date automatically using your computer's own scheduler (cron on Linux, launchd on
      macOS, Task Scheduler on Windows). Claude Code's scheduled tasks run in the cloud and can't reach
      a Plex server on a home network
- [ ] Test the macOS and Windows schedulers on real machines (so far tested with stand-ins on Linux)

## Ideas for later

- [ ] **Dashboard as a claude.ai page**: publish the dashboard and keep it updated automatically. On hold:
      Claude Code's background mode (`claude -p`) didn't have the page-publishing tool on the account
      it was tested with, so scheduled runs couldn't update the page.

- [ ] **`duplicates`**: titles with more than one copy or version, and how much space the extras use
- [ ] **`quality-upgrades`**: titles only available in SD or 720p that may be worth replacing
- [ ] **`users-and-shares`**: who has access to your server and which libraries are shared with whom
