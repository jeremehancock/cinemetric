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
your Plex server, Tautulli or plex.tv. It also keeps your Plex token and Tautulli API key out of
Claude's sight: it replaces them with a label in anything a tool hands back to Claude, refuses
Claude's reads of Cinemetric's settings file, and refuses any call that would put them in a file, an
issue, a page or anywhere other than your own server. To recognise them it reads the token and API key
from your settings file and `PLEX_TOKEN`, and holds them only in its own memory: it never shows, logs,
saves or sends them. It makes no network requests. It's meant to be switched off only by you, with
`/cinemetric-mods guard off` or in Claude Code's `/config` menu, and it refuses Claude's usual ways of
switching it off. It is a safety net, not a guarantee: it reads each command before it runs, so it
can't see inside a program Claude saves to a file and runs later, whether that program writes to the
server, sends the token somewhere without printing it, or changes the setting that switches the guard
off. It also can't hide a token you type or paste into the chat yourself, though it still stops
Claude passing it on. Its rules are in
[openspec/specs/read-only-guard/spec.md](openspec/specs/read-only-guard/spec.md).

## Now Playing

The Now Playing mod is off until you switch it on. When you type `/cinemetric-now`, it opens a panel
and runs the same read-only server-health script the skills use, asking your server only for its
current streams, about every 30 seconds while the panel is open. It stops when you close the panel.
The mod itself never reads your token: the script does the talking to Plex, under the same rules as
every skill. The panel shows people's names and what they're watching on your screen only; none of it
is sent to Claude. It saves nothing.

## What the skills do not protect against

- Anyone who can read your config file or environment can use your token. Keep your user account secure.
- A Plex token has the same access as the account it belongs to. Read-only behavior is enforced by
  Cinemetric's code, not by Plex.
- Cinemetric can't stop Claude from changing your server if you ask it to. The skills only read, and
  the read-only guard catches common ways Claude might change things on its own, but if you ask Claude
  to delete, rename or fix something, that's ordinary Claude Code work, not something Cinemetric
  controls. Treat it like any other change Claude makes on your computer.
- Claude Code's own permission prompts are your last check. By default Claude Code asks before running
  a command, so read any command that mentions your Plex server or Tautulli before you approve it. If
  you let Claude Code run commands without asking, the guard is the only check left.
- Two Plex settings limit the damage if something does go wrong. If you don't delete files through
  Plex, switch off **Allow media deletion** (Settings, Library): Plex then refuses to delete media
  files for any app, Claude included. And keep **Backup database every three days** switched on
  (Settings, Scheduled Tasks): it keeps copies of your library details and watch history, though not
  the media files themselves.

## Reporting a problem

Please open a GitHub issue for general bugs. For anything security-sensitive, use GitHub's
"Report a vulnerability" (private security advisory) on this repository instead of a public issue.
