# Security

Cinemetric is designed so you can hand it your Plex token without worrying about what it will do with it.

## What the skills do

- **Read only.** Scripts only send HTTP `GET` requests, and only to a fixed list of Plex paths
  (`ALLOWED_PATHS` in each script). Any other request is blocked in code before it is sent.
  `server-health` reads the server's settings list but keeps only a few maintenance settings (scan and
  maintenance-window options); everything else in it is discarded without being printed.
- **Only Plex.** Report skills contact only the Plex server address you configured. The `setup` skill
  also contacts Plex's own sign-in service (`plex.tv` and `clients.plex.tv`) to sign you in and list your
  servers. If you add Tautulli, `watch-activity` and setup also contact the Tautulli address you gave,
  running only read-only commands (`TAUTULLI_COMMANDS` in the script). Nothing else: no analytics, no
  update checks, no third-party services.
- **Sign in with Plex, no copy-pasted tokens.** Setup receives the token straight from Plex and writes it
  to the private config file. It never passes through the chat. Each install is listed in Plex under
  **Authorized Devices** as "Cinemetric" and can be revoked there.
- **No redirects.** If the server answers with a redirect, the script stops instead of following it,
  so your token is never forwarded to a different address.
- **Token stays hidden.** The token is sent in a request header, never in a URL, and is never printed,
  logged, or included in error messages. Tautulli only accepts its API key in the URL, so the key is
  removed from any error message and never printed. It's entered in your own terminal, hidden as you
  type, never through the chat.
- **Tautulli setup stays on your computer.** The one-time key form listens only on `127.0.0.1` (not your
  network), at an address with a random code, and only answers requests addressed to `127.0.0.1` or
  `localhost`. It shuts down after one successful save, when cancelled, or after 10 minutes.
- **One exception to read-only.** To fetch the key automatically, setup uses Tautulli's `get_apikey`
  command. If Tautulli has never had an API key at all, Tautulli itself creates one in response and
  saves it in its own settings. If Tautulli already has a key (the usual case), nothing changes.
- **Private files only.** Config and in-progress sign-in files are created readable only by you (`600`,
  folder `700`); the sign-in file is deleted once setup finishes. The config file is refused if it's owned by another user or readable by
  other users (it must be `chmod 600`).
- **Encrypted by default.** HTTPS certificates are checked unless you explicitly set `"verify_tls": false`.
  Plain `http` to a non-local address triggers a warning.
- **No dependencies.** Python standard library only, so there are no third-party packages to trust.
- **Limited permissions for Claude.** Each skill's `allowed-tools` only pre-approves running its own script.
- **Media titles are treated as data.** Skill instructions tell Claude never to follow instructions that
  appear inside titles or metadata.

## What the skills do not protect against

- Anyone who can read your config file or environment can use your token. Keep your user account secure.
- A Plex token has the same access as the account it belongs to. Read-only behavior is enforced by
  Cinemetric's code, not by Plex.

## Reporting a problem

Please open a GitHub issue for general bugs. For anything security-sensitive, use GitHub's
"Report a vulnerability" (private security advisory) on this repository instead of a public issue.
