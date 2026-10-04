# Security

Cinemetric is designed so you can hand it your Plex token without worrying about what it will do with it.
In short: every skill is read-only, talks only to Plex and (if you add it) Tautulli, and never shows
your token or API key in the chat.

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
