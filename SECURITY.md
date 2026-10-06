# Security

Cinemetric is designed so you can hand it your Plex token without worrying about what it will do with it.
In short: every skill is read-only, talks only to Plex and (if you add it) Tautulli, and never shows
your token or API key in the chat. The one exception to "only Plex and Tautulli" is plex.tv: setup uses
it to sign you in, and `users-and-shares` reads your share list from it, because that list is only
stored in your plex.tv account. `users-and-shares` sends read-only requests to three fixed plex.tv
addresses and never shows the email addresses or access tokens of the people you share with. Cinemetric's scripts never publish anything. If you choose to put
the dashboard online, Claude publishes it as a private claude.ai page that only you can see unless you
share it.

When you run the `changes` skill or build the dashboard, it saves a small snapshot on your computer
(at most one per day, in `~/.local/share/cinemetric/snapshots`, or
`%LOCALAPPDATA%\cinemetric\snapshots` on Windows), readable only by you, so it can show what changed
since then. A snapshot holds titles, library names and sizes, the Plex version, and each person's
name, kind, status, libraries and download setting. No emails, account ids, tokens or watch history.
Snapshots older than 90 days are deleted automatically; ask the `changes` skill to forget them to
delete them all.

## What the skills do

The full list of safety rules, and exactly how each one is enforced, is in
[openspec/specs/security/spec.md](openspec/specs/security/spec.md).

## What the skills do not protect against

- Anyone who can read your config file or environment can use your token. Keep your user account secure.
- A Plex token has the same access as the account it belongs to. Read-only behavior is enforced by
  Cinemetric's code, not by Plex.

## Reporting a problem

Please open a GitHub issue for general bugs. For anything security-sensitive, use GitHub's
"Report a vulnerability" (private security advisory) on this repository instead of a public issue.
