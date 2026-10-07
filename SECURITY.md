# Security

Cinemetric is designed so you can hand it your Plex token without worrying about what it will do with it.
In short: every skill is read-only, talks only to Plex and (if you add it) Tautulli, and never shows
your token or API key in the chat. The one exception to "only Plex and Tautulli" is plex.tv: setup uses
it to sign you in, and `users-and-shares` reads your share list from it, because that list is only
stored in your plex.tv account. `users-and-shares` sends read-only requests to three fixed plex.tv
addresses and never shows the email addresses or access tokens of the people you share with. Cinemetric's scripts never publish anything. If you choose to put
the dashboard or your year-in-review recaps online, Claude publishes them as private claude.ai pages
that only you can see unless you share them. A whole-server recap names no one and leaves off titles
only one person watched.

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

## The read-only guard

Cinemetric also comes with a mod, the read-only guard, that is on by default. It checks the commands
Claude writes on its own, outside Cinemetric's skills, and stops any that would change something on
your Plex server, Tautulli or plex.tv. It reads only the server and Tautulli addresses (never the token
or API key) and makes no network requests. It's meant to be switched off only by you, with
`/cinemetric-mods guard off` or in Claude Code's `/config` menu, and it refuses Claude's usual ways of
switching it off. It is a safety net, not a guarantee: it reads each command before it runs, so it
can't see inside a program Claude saves to a file and runs later, whether that program writes to the
server or changes the setting that switches the guard off. Its rules are in
[openspec/specs/read-only-guard/spec.md](openspec/specs/read-only-guard/spec.md).

## What the skills do not protect against

- Anyone who can read your config file or environment can use your token. Keep your user account secure.
- A Plex token has the same access as the account it belongs to. Read-only behavior is enforced by
  Cinemetric's code, not by Plex.

## Reporting a problem

Please open a GitHub issue for general bugs. For anything security-sensitive, use GitHub's
"Report a vulnerability" (private security advisory) on this repository instead of a public issue.
