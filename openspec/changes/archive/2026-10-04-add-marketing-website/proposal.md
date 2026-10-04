## Why

Cinemetric's only public face today is the GitHub README, which is thorough but reads like documentation,
not an introduction. A small, good-looking website gives people a quick, friendly way to see what the
skills do and how to get started, and gives the project a link worth sharing. The owner hosts sites with
Coolify, so the site needs to be a plain folder of static files that Coolify can serve as-is.

## What Changes

- New top-level `website/` folder holding a self-contained static site: `index.html`, one stylesheet,
  one script and its images/icons. Plain HTML, CSS and JavaScript: no frameworks, no build step, no
  package manager. Coolify can point straight at the folder.
- A single scrolling landing page with a Plex-inspired look (dark charcoal backgrounds, Plex-style amber
  accent, poster-shelf and "now playing" styling) that covers:
  - A hero section with the one-line pitch and the two install commands, each with a copy button.
  - A feature section for each of the five skills (`setup`, `library-report`, `server-health`,
    `watch-activity`, `dashboard`): what it reports, example questions to ask Claude, and an
    example of its real output (a terminal reply, or for the dashboard, a screenshot of the page)
    with made-up sample data.
  - The read-only / privacy promises (never changes the server, token never passes through the chat,
    Sign in with Plex, optional Tautulli).
  - A step-by-step setup guide: requirements, install, Sign in with Plex, optional Tautulli, manual
    setup as a fallback, and how to revoke access.
  - The "not affiliated with Plex or Anthropic" notice and the "AI can make mistakes" caution.
  - A footer with a link to the GitHub repository and "Created by Jereme Hancock".
- Small touches that make it feel polished: subtle scroll-in animations, a sticky header that changes
  on scroll, and full keyboard/screen-reader support with reduced-motion
  respected.
- README gains a one-line pointer to the `website/` folder (and, once the owner has deployed it, the
  live address).
- No change to the plugin, its skills or scripts, so no version bump.

## Capabilities

### New Capabilities

- `website`: the static marketing site in `website/`: where it lives, how it's built (static files
  only, no external runtime dependencies), what content it must show, and the footer credit and link.

### Modified Capabilities

(none)

## Impact

- New files only, all under `website/` (plus a short README addition). No Python, skill or manifest
  changes.
- The plugin installer copies `plugins/cinemetric/` only, so the site never ships inside the plugin.
- Hosting is done by the owner in Coolify (static site pointed at `website/`); nothing in the repo
  configures Coolify.
- The site repeats some setup facts from the README. To keep the two from drifting apart, the site
  sticks to the short version and links to the README for the full details.
