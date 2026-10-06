# Cinemetric

> [!NOTE]
> **Early days.** Cinemetric is still growing, so skills, setup steps and report formats may change
> between versions. Ideas and bug reports are welcome via
> [GitHub issues](https://github.com/jeremehancock/cinemetric/issues).

**Claude skills for your Plex server.** Ask Claude Code about your media library and get a clear,
plain-English report: what you have, how much space it uses, what quality it's in, what was just added,
and what needs tidying up.

**Website:** [cinemetric.dev](https://cinemetric.dev). Its source lives in [`website/`](website/): plain HTML,
CSS and JavaScript with no build step, ready for any static host.

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
| `library-report` | Counts, storage, 4K/1080p and codec breakdown, 10-bit video, recently added, unavailable files, unmatched items, missing posters, very large files, duplicates |
| `server-health` | Version and updates, remote access, CPU and memory, who's streaming now (direct play vs transcode, bandwidth), streaming settings (hardware transcoding, remote limits), running tasks, library scans, scheduled maintenance |
| `watch-activity` | Who's watching right now, plays and watch time, most watched movies, shows and music, most active users and devices, daily trends, recent plays, the most streams at once, and titles started but never finished. Works for everyone or one person. Uses Tautulli if you have it, otherwise Plex's own history |
| `users-and-shares` | Who your server is shared with (friends, Plex Home, managed users, pending invites), which libraries each person can see, who can download, when each person last played something, and which shared libraries nobody has played from lately. Reads the share list from your plex.tv account; only the server owner can use it |
| `unwatched` | Movies and shows nobody has finished in a while (added more than 6 months ago, no finished play by anyone since), largest first, with how much space they use and when each was last finished. Facts only: it never suggests deleting anything. Uses Tautulli if you have it, otherwise Plex's own history |
| `what-to-watch` | Finds something to watch tonight in your own library: by genre, length, decade, rating or content rating, unwatched only, shuffled for fresh ideas each time. Suggests a few titles with a reason for each, or picks up where you left off. Only titles already on your server |
| `episode-gaps` | Gaps in your TV shows: episode numbers missing between ones you have (E01, E02 and E04 are there, so E03 is probably missing), seasons that start late, seasons missing between others, and episodes whose files Plex can't find. Specials, two-episode files and shows numbered straight on across seasons aren't counted as gaps. Uses only what's on your server, so it can't see episodes after the last one you have |
| `playback-check` | Files likely to be transcoded (converted on the fly) on common devices, and why: image-based subtitles (PGS, VobSub), TrueHD or DTS audio, and bitrates above your remote streaming limit or a speed you choose. With Tautulli, also which devices and people transcode most, how often, and why. Checks every movie and episode in about a minute; facts only, it never tells you to convert files |
| `changes` | What changed since yesterday, last week or last month: titles added and removed, new episodes, files Plex can no longer find, Plex updates, and people given or losing access. Each time you run it (or build the dashboard) it saves a small private snapshot on your computer, at most one per day, kept 90 days, to compare with next time. Nothing runs in the background; the library, server and sharing reports and the dashboard show the same "since last time" changes |
| `dashboard` | One page with library, server, watch, unwatched, episode gaps, playback and sharing stats and charts. Saved on your computer, as a private claude.ai page you can open anywhere, or both; each refresh updates the same file and link |

More skills are planned, and ideas are welcome; see [Roadmap](#roadmap).

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
*"How's my Plex server doing?"*, *"What's been watched on Plex this month?"*,
*"Who have I shared my Plex server with?"*, *"What on my Plex server has nobody watched in months?"*,
*"Find me a comedy under 2 hours I haven't seen"*, *"Am I missing any episodes on Plex?"*,
*"Why does Plex keep transcoding?"* or *"Build my Plex dashboard"*

### Optional: add Tautulli

If you run [Tautulli](https://tautulli.com), Cinemetric can use it for fuller watch stats (watch time,
devices, busiest times) and to see which devices and people transcode most in `playback-check`. Without
it, `watch-activity` uses Plex's own history, which only counts plays.

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

## Roadmap

Plans can change; feedback and ideas are welcome via GitHub issues. What the existing skills do, and
the rules every skill follows, are written down as specs in [openspec/specs/](openspec/specs/). New
work starts as an OpenSpec change proposal (`/opsx:propose`) before any code is written. Notes on how
each idea below might be built are in [openspec/ideas.md](openspec/ideas.md).

**Ideas for later**

New skills:

- [ ] **`year-in-review`**: a yearly recap page with top titles, total hours and busiest months, with
      care taken around other people's viewing details

Updates to existing skills:

- [ ] **Weekly digest**: a scheduled weekly run that only mentions what changed, using the snapshots
      the `changes` skill already saves
- [ ] **Trends on the dashboard**: charts of how the library and sharing changed over the saved
      snapshots
- [ ] **`setup`**: remember more than one server and switch between them

## Support Development

Cinemetric is free and open source, and it stays that way. If it has been useful to you and you'd like
to help keep it maintained, you can support development at
[cinemetric.dev/#support](https://cinemetric.dev/#support). Feedback and bug reports are just as welcome.

[![Buy Me A Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://www.buymeacoffee.com/jeremehancock)

## License

MIT. See [LICENSE](LICENSE).

## AI Assistance Disclosure

This tool was developed with assistance from AI language models.
