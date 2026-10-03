# Cinemetric

> [!WARNING]
> **Work in progress.** Cinemetric is in early development. Skills, setup steps and report formats may
> change without notice. Feedback and bug reports are welcome via GitHub issues.

**Claude skills for your Plex server.** Ask Claude Code about your media library and get a clear,
plain-English report: what you have, how much space it uses, what quality it's in, what was just added,
and what needs tidying up.

> Cinemetric is an independent project. It is not affiliated with, endorsed by, or sponsored by
> Plex, Inc. or Anthropic. "Plex" and "Claude" are trademarks of their respective owners.

> [!CAUTION]
> **AI can make mistakes.** Cinemetric's scripts collect the numbers, but the reports you read are
> written by Claude, an AI model. It can misread data, summarize something incorrectly, or draw a
> conclusion the numbers don't fully support. Double-check anything important in Plex (or Tautulli)
> before acting on it, especially before deleting, replacing or re-encoding files.

## Skills

| Skill | What it does |
|---|---|
| `setup` | Connects Cinemetric to your server using **Sign in with Plex**; no copying tokens around |
| `library-report` | Counts, storage, 4K/1080p and codec breakdown, 10-bit video, recently added, unavailable files, unmatched items, missing posters, very large files |
| `server-health` | Version and updates, remote access, CPU and memory, who's streaming now (direct play vs transcode, bandwidth), running tasks, library scans, scheduled maintenance |
| `watch-activity` | Plays and watch time, most watched movies, shows and music, most active users and devices, daily trends, recent plays. Uses Tautulli if you have it, otherwise Plex's own history |

More skills are planned; see [ROADMAP.md](ROADMAP.md).

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

Then try: *"Give me a Plex library report"*, *"What's been added to my Movies library recently?"*,
*"How's my Plex server doing?"* or *"What's been watched on Plex this month?"*

### Optional: add Tautulli

If you run [Tautulli](https://tautulli.com), Cinemetric can use it for fuller watch stats (watch time,
devices, busiest times). Without it, `watch-activity` uses Plex's own history, which only counts plays.

Ask Claude to *"add Tautulli to Cinemetric"* and tell it your Tautulli address. Your API key never goes
through the chat:

- **If Tautulli has no login**, Cinemetric fetches the key from Tautulli itself. Nothing else to do.
- **If Tautulli has a login**, Claude gives you a link to a small one-time page that runs only on your
  own computer. Paste the key there (from Tautulli's **Settings → Web Interface → API**) and click
  **Test and save**. The page closes itself once it's done, or after 10 minutes.
- **If Claude Code runs on another machine** (over SSH or in the cloud), that link won't open from your
  browser, so Claude gives you a command to run in a terminal on that machine instead.

Either way, the key is tested before it's saved to the same private config file. If your Tautulli uses
`https` with a self-signed certificate, setup will say so and let you choose: use Tautulli's plain `http`
address on your home network, or skip the certificate check for that address only. You can also set
`TAUTULLI_URL` and `TAUTULLI_API_KEY` environment variables.

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
