# Cinemetric roadmap

What's planned for Cinemetric. Plans can change; feedback and ideas are welcome via GitHub issues.

What the existing skills do, and the rules every skill follows, are written down as specs in
[openspec/specs/](openspec/specs/). New work starts as an OpenSpec change proposal (`/opsx:propose`)
before any code is written.

## Unfinished parts of existing skills

- [ ] **`server-health`: failed or stuck tasks.** Plex doesn't report task failures through its API, so
      this needs another source (for example its logs) before it can be added.
- [ ] **`dashboard`: test the macOS and Windows schedulers on real machines** (so far tested with
      stand-ins on Linux).

## Ideas for later

- [ ] **Dashboard as a claude.ai page**: publish the dashboard and keep it updated automatically. On hold:
      Claude Code's background mode (`claude -p`) didn't have the page-publishing tool on the account
      it was tested with, so scheduled runs couldn't update the page.
- [ ] **`duplicates`**: titles with more than one copy or version, and how much space the extras use
- [ ] **`quality-upgrades`**: titles only available in SD or 720p that may be worth replacing
- [ ] **`users-and-shares`**: who has access to your server and which libraries are shared with whom
