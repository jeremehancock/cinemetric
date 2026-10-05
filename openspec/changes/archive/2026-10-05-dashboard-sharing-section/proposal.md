## Why

The dashboard is meant to be the one page that shows the state of the server, and who can reach the
server is part of that state. Since 0.8.0, `users-and-shares` can report it, but the dashboard still
only combines the library report, server health and watch activity, so the owner has to ask
separately to see who it's shared with.

## What Changes

- The dashboard also runs `users_and_shares.py`, side by side with the other three reports, and adds
  a **Sharing** section: how many people can reach the server (by Plex Home, managed and friends),
  pending invites, how many people can see each library, and the report's "worth a look" items (old
  invites, inactive people, "all libraries" shares, friends who can download).
- With names shown, the section also lists people (name, type, number of libraries, last played).
  With names hidden, it shows only counts: no names anywhere in the section.
- Sharing items are shown in the Sharing section, not in the server's "Needs a look" list, and don't
  change the page's overall status. They're often deliberate, and a healthy server shouldn't show
  "Mostly fine" because a friend can download.
- If the sharing report fails (for example `OWNER_ONLY` when connected to someone else's server), the
  section shows the reason in plain words and the rest of the page is built as before.
- `SKILL.md`: the first-time online publishing note mentions that the page also lists the people the
  server is shared with, and the summary can mention sharing items.
- README, website dashboard copy and the dashboard screenshot (rebuilt from made-up data) mention
  sharing. Version bump to 0.9.0.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dashboard`: "Built from the other report scripts" adds `users_and_shares.py`; "Rule-based page"
  extends hidden names to the sharing section; a new requirement describes the Sharing section.

## Impact

- `plugins/cinemetric/skills/dashboard/scripts/dashboard.py`: new source and section.
- `plugins/cinemetric/skills/dashboard/SKILL.md`: description, publishing note, summary.
- `tests/test_dashboard.py`: sharing section, escaping, hidden names, failed sharing report.
- `README.md`, `website/index.html`, `website/screens/dashboard.jpg`, `.claude-plugin/marketplace.json`.
- `VERSION` in all six scripts, `plugin.json` and `marketplace.json`.
- No change to `users_and_shares.py` or any other report script.
