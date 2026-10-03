# Cinemetric

> [!WARNING]
> **Work in progress.** Cinemetric is in early development. Skills, setup steps and report formats may
> change without notice. Feedback and bug reports are welcome via GitHub issues.

**Claude skills for your Plex server.** Ask Claude Code about your media library and get a clear,
plain-English report: what you have, how much space it uses, what quality it's in, what was just added,
and what needs tidying up.

> Cinemetric is an independent project. It is not affiliated with, endorsed by, or sponsored by
> Plex, Inc. or Anthropic. "Plex" and "Claude" are trademarks of their respective owners.

## Skills

| Skill | What it does |
|---|---|
| `setup` | Connects Cinemetric to your server using **Sign in with Plex**; no copying tokens around |
| `library-report` | Counts, storage, 4K/1080p and codec breakdown, 10-bit video, recently added, unavailable files, unmatched items, missing posters, very large files |

More are planned: server health, watch activity (via Tautulli), and a scheduled dashboard.

Every Cinemetric skill is **read-only**: it never changes anything on your server. See [SECURITY.md](SECURITY.md).

## Install

In Claude Code:

```
/plugin marketplace add jeremehancock/cinemetric
/plugin install cinemetric@cinemetric
```

Requirements: Claude Code and Python 3.8+ (standard library only, nothing to `pip install`).
Your computer must be able to reach your Plex server over the network. No SSH is needed.

## Set up your server connection

Ask Claude: **"Set up Cinemetric"** (or run `/cinemetric:setup`).

1. Claude gives you a **Sign in with Plex** link. Open it and approve **Cinemetric**.
2. Tell Claude you're done. It lists the Plex servers your account can use; pick one.
3. Cinemetric tests the connection (preferring local, encrypted addresses) and saves it.

Your token goes straight from Plex into `~/.config/cinemetric/config.json`, a file only you can read.
It never appears in the chat. Cinemetric shows up in Plex under **Settings → Authorized Devices**,
where you can revoke it at any time.

Then try: *"Give me a Plex library report"* or *"What's been added to my Movies library recently?"*

### Manual setup

If you can't use the sign-in flow (for example, the computer can't reach plex.tv), create the config
file yourself, in your own terminal or editor (don't paste your token into a chat):

```json
{
  "plex_url": "http://192.168.1.10:32400",
  "plex_token": "YOUR-TOKEN-HERE"
}
```

Save it as `~/.config/cinemetric/config.json` and run `chmod 600 ~/.config/cinemetric/config.json`.
Cinemetric refuses to use the file if other users can read it. To find a token, open any item in Plex Web,
then **⋯ → Get Info → View XML**; the address ends with `X-Plex-Token=...`. You can also set `PLEX_URL`
and `PLEX_TOKEN` environment variables instead; they take priority. For `https` with a self-signed
certificate, add `"verify_tls": false` (this turns off certificate checking; only do it on your own network).

You can also run the script directly:

```bash
python3 plugins/cinemetric/skills/library-report/scripts/library_report.py --check
python3 plugins/cinemetric/skills/library-report/scripts/library_report.py --library Movies
```

## Revoking access

A Plex token gives the same access as your account. To revoke Cinemetric, remove "Cinemetric" under
**Settings → Authorized Devices** in Plex, then run setup again if you want to reconnect. If you used
manual setup and think a token leaked, use "sign out of all devices" in your Plex account settings.

## License

MIT. See [LICENSE](LICENSE).

## AI Assistance Disclosure

This tool was developed with assistance from AI language models.
