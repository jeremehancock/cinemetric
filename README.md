# Cinemetric

**Claude skills for your Plex server.** Ask Claude Code about your media library and get a clear,
plain-English report: what you have, how much space it uses, what quality it's in, what was just added,
and what needs tidying up.

Cinemetric works best in Claude Code in your favorite terminal. See [Where to use it](#where-to-use-it).

**Website:** [cinemetric.dev](https://cinemetric.dev). Its source lives in [`website/`](website/): plain HTML,
CSS and JavaScript with no build step, ready for any static host.

> Cinemetric is an independent project. It is not affiliated with, endorsed by, or sponsored by
> Plex, Inc. or Anthropic. "Plex" and "Claude" are trademarks of their respective owners.

> [!CAUTION]
> **AI can make mistakes.** Cinemetric's scripts collect the numbers, but the reports you read are
> written by Claude, an AI model. It can misread data, summarize something incorrectly, or draw a
> conclusion the numbers don't fully support. Double-check anything important in Plex (or Tautulli)
> before acting on it, especially before deleting, replacing or re-encoding files. Cinemetric only
> controls what its own skills do: if you ask Claude to change something on your server, read each
> command Claude Code shows you before you approve it. See [SECURITY.md](SECURITY.md) for more.

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
| `show-progress` | Where each person is in each TV show: the furthest episode they finished, how many are left and the next one, and whether they're caught up, have new episodes waiting, are partway through, or stopped (nothing played from the show in 3 months). Rewatching early episodes or starting partway in doesn't count as falling behind. Also which shows got new episodes lately and whether the people following them have watched them. For everyone, one person or one show; "caught up" means with what's on your server. Uses Tautulli if you have it, otherwise Plex's own history |
| `episode-gaps` | Gaps in your TV shows: episode numbers missing between ones you have (E01, E02 and E04 are there, so E03 is probably missing), seasons that start late, seasons missing between others, and episodes whose files Plex can't find. Specials, two-episode files and shows numbered straight on across seasons aren't counted as gaps. Uses only what's on your server, so it can't see episodes after the last one you have |
| `playback-check` | Files likely to be transcoded (converted on the fly) on common devices, and why: image-based subtitles (PGS, VobSub), TrueHD or DTS audio, and bitrates above your remote streaming limit or a speed you choose. With Tautulli, also which devices and people transcode most, how often, and why. Checks every movie and episode in about a minute; facts only, it never tells you to convert files |
| `subtitles-and-languages` | Movies and episodes with audio in another language and no subtitles in yours, titles with no subtitles in a language you name (such as Spanish), and tracks with no language set, so Plex can't pick the right one. Also how many files have audio and subtitles in each language. Goes by each track's language label, checked against your libraries' language unless you name another; forced subtitles, which usually only cover a few lines, don't count as full subtitles. Facts only: it never tells you to download or replace anything |
| `title-lookup` | Everything about one movie, show or episode in one answer: when it was added, length, ratings, genres and collections; each file's quality (resolution, HDR, codecs, size); whether it's likely to be transcoded and why; for a show, its seasons, episode counts and episodes Plex can't find; and who watched it, when, and how far they got. If several titles match, Claude asks which one you meant. Uses Tautulli if you have it, otherwise Plex's own history |
| `changes` | What changed since yesterday, last week or last month: titles added and removed, new episodes, files Plex can no longer find, Plex updates, and people given or losing access. Each time you run it (or build the dashboard) it saves a small private snapshot on your computer, at most one per day, kept 90 days, to compare with next time. Nothing runs in the background; the library, server and sharing reports and the dashboard show the same "since last time" changes. It can also say how the library and sharing moved across all the saved snapshots |
| `year-in-review` | A recap page of one calendar year: hours watched, busiest months and busiest day, movies vs TV vs music, and the most watched movies, shows and artists. For the whole server it names no one and leaves off titles only one person watched, so it doesn't reveal anyone's viewing; it can also cover just your own year, or one person's as a recap to give them. Saved on your computer, as a private claude.ai page, or both; running it again updates the same file and link |
| `dashboard` | One page with library stats, server status (version, updates, remote access and anything that needs a look), the last 30 days of watching, unwatched titles, episode gaps, playback and sharing, with charts, plus trends over the saved snapshots (storage, titles per library and people with access). Saved on your computer, as a private claude.ai page you can open anywhere, or both; each refresh updates the same file and link |

More skills are planned, and ideas are welcome; see [Roadmap](#roadmap).

Every Cinemetric skill is **read-only**: it never changes anything on your server. See [SECURITY.md](SECURITY.md).
If your server lets apps delete media files, Cinemetric mentions it once in a conversation, because
switching off **Allow media deletion** in Plex (Settings, Library) makes sure Claude can't delete your
movies, shows or music through Plex. Plex then refuses deletions from every app, including its own.

## Mods

Mods are small add-ons that run inside Claude Code (the terminal and the desktop app's Code tab). They
come with Cinemetric, so there's nothing extra to install, and each one has its own on/off switch.

| Mod | Starts | What it does |
|---|---|---|
| `guard` | On | **Read-only guard.** Checks the commands Claude writes on its own, outside Cinemetric's skills. If one would change something on your Plex server, Tautulli or plex.tv (deleting a title, starting a library scan, marking something watched, stopping someone's stream, running a Tautulli command that isn't a read), the guard stops it before it runs and tells Claude why. It also keeps your Plex token and Tautulli API key out of Claude's sight: it hides them in anything a command prints, stops Claude reading Cinemetric's settings file, and stops Claude putting them in a file, an issue or a page |
| `status` | Off | **Library status line.** A dim line just above the prompt such as `Plex: 1,970 movies · 417 shows · 59.4 TB · checked 3 days ago`, read from the newest snapshot Cinemetric saved. It updates when you ask what changed or refresh the dashboard, the two skills that save snapshots. It never contacts your server, and checks for a new snapshot after each turn, so it shows straight away |
| `now` | Off | **Now Playing.** Type `/cinemetric-now` to open a panel showing who's streaming from your server right now: each person, what they're watching, on which device, how far in, and whether it's playing directly or being transcoded (converted on the fly). It checks your server about every 30 seconds, only while the panel is open, and stops when you close it. The panel shows people's names, and what it shows stays on your screen: it isn't sent to Claude. Switching any mod on or off closes the panel; type `/cinemetric-now` to open it again |

> [!IMPORTANT]
> **The guard is a safety net, not a guarantee.** It reads each command before it runs, so it catches the
> common ways of changing things, but it can't see inside a program Claude saves to a file and runs
> later. The same goes for your Plex token and Tautulli API key: a program like that could send them
> somewhere without printing them. And if you type or paste either one into the chat yourself, Claude
> sees it; the guard can only stop Claude passing it on.

**Switching mods on and off.** Type `/cinemetric-mods` in Claude Code to see every mod and whether it's
on, and `/cinemetric-mods <name> on` or `off` to switch one:

```
/cinemetric-mods
/cinemetric-mods status on
```

Each mod also has a switch in Claude Code's settings menu (`/config`). The guard is the one exception
to who can switch things: it's meant to be turned off only by you (`/cinemetric-mods guard off` or
`/config`). Cinemetric refuses Claude's usual ways of turning it off, so Claude can't casually switch
off its own safety net. Like the rest of the guard, that's a safety net, not a lock: it doesn't catch
every workaround, such as a script Claude writes to change the settings file.

**Mods not running?** If `/cinemetric-mods` says it isn't installed, or Cinemetric shows a notice that
the mods aren't running, every skill still works, but the mods (including the guard) are off for that
session. There are two possible reasons:

- **Claude Code is older than 2.1.260.** Run `claude update`, then start a new session.
- **Claude Code is new enough, but the feature mods use is switched off.** Claude Code is still rolling
  out the feature mods are built on, so a session can start with it off. To switch it on for every
  session, add this to `~/.claude/settings.json` (merge it into any `env` section already there),
  then start a new session:

  ```json
  "env": {
    "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS": "1"
  }
  ```

## Install

### Where to use it

Cinemetric works best in Claude Code in your favorite terminal. That's where every skill and every mod
works as described here, with no extra steps.

- **Claude Code in the desktop app (the Code tab):** the skills and the read-only guard work there too,
  but some versions of the app can't show the library status line or the Now Playing panel
  (`/cinemetric-now` tells you when that happens), and switching mods with `/cinemetric-mods` may not
  work there. Switch them in a terminal instead: the desktop app uses the same settings.
- **Claude in the desktop app's chat or on claude.ai:** mods only run in Claude Code, so they aren't
  available there.

### Install the plugin

In Claude Code:

```
/plugin marketplace add jeremehancock/cinemetric
/plugin install cinemetric@cinemetric
```

Requirements: Claude Code 2.1.75 or newer (2.1.260 or newer for [mods](#mods)) and Python 3.8+
(standard library only, nothing to `pip install`).
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
*"Find me a comedy under 2 hours I haven't seen"*, *"Who's caught up on Severance?"*, *"Am I missing any episodes on Plex?"*,
*"Why does Plex keep transcoding?"*, *"Tell me about Blade Runner 2049 on my Plex"* or
*"Build my Plex dashboard"*

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

Plans can change; feedback and ideas are welcome via
[GitHub issues](https://github.com/jeremehancock/cinemetric/issues). What the existing skills do, and
the rules every skill follows, are written down as specs in [openspec/specs/](openspec/specs/). New
work starts as an OpenSpec change proposal (`/opsx:propose`) before any code is written. Notes on how
each idea below might be built are in [openspec/ideas.md](openspec/ideas.md).

**New skill ideas**

One for each group of skills on the website:

- **Your library: `collections-and-playlists`:** your collections and playlists, how big each is,
  collections with only one title, and playlists pointing at files Plex can no longer find.
- **Watching: `watch-mix`:** what gets watched compared with what's on the shelf, by genre, decade and
  quality, for example "horror is 18% of your movies but 3% of what's watched".
- **Your server: `export`:** save a library listing as a spreadsheet file (CSV) on your computer.

**Updates to existing skills**

- **`server-health`:** when your server is busiest, by hour and day of the week, compared with when
  Plex runs its scheduled maintenance.
- **`library-report`:** count Dolby Vision and HDR10+ separately from other HDR.
- **`what-to-watch`:** something several people at home haven't seen yet, and "more like this" for a
  title you liked.
- **`unwatched`:** what one person hasn't watched.
- **`changes`:** how fast the library is growing, for example "about 1.2 TB a month".
- **`year-in-review`:** favorite genres, and a comparison with the year before.

**Mod ideas**

- **Heads-up:** a one-time notice when Claude Code starts, such as "Plex update available · 12 files
  unavailable", read from the newest snapshot without contacting your server.
- **Guard log:** a command that lists what the guard stopped recently and why.
- **Now Playing:** total bandwidth, and the exact reason each stream is being transcoded.

Suggestions are welcome via GitHub issues.

## Support Development

Cinemetric is free and open source, and it stays that way. If it has been useful to you and you'd like
to help keep it maintained, you can support development at
[cinemetric.dev/#support](https://cinemetric.dev/#support). Feedback and bug reports are just as welcome.

[![Buy Me A Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://www.buymeacoffee.com/jeremehancock)

## License

MIT. See [LICENSE](LICENSE).

## AI Assistance Disclosure

This tool was developed with assistance from AI language models.
