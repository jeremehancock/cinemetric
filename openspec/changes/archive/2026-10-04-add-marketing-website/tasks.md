## 1. Scaffold

- [x] 1.1 Create `website/` with `index.html`, `styles.css`, `script.js` and `favicon.svg` (Cinemetric mark, not the Plex logo)
- [x] 1.2 Set up `index.html` skeleton: meta tags (description, theme-color, Open Graph with relative paths and a marked spot for the live URL), skip link, header/nav, `<main>` sections, footer
- [x] 1.3 Define design tokens in `styles.css` (dark charcoal surfaces, amber accent, text greys, radii, spacing, system font stack) and confirm AA contrast for text colors

## 2. Content sections

- [x] 2.1 Hero: headline, one-line pitch, poster-wall background (CSS gradients only), terminal card with both install commands and copy buttons
- [x] 2.2 Skill "shelf": five poster cards linking to each skill's detail section
- [x] 2.3 `setup` detail: Sign in with Plex steps, example prompt, sign-in stepper mock
- [x] 2.4 `library-report` detail: counts, storage, 4K/1080p and codec breakdown, 10-bit, recently added, housekeeping; example prompts; quality-breakdown mock with sample data
- [x] 2.5 `server-health` detail: version/updates, remote access, CPU/memory, live streams (direct play vs transcode, bandwidth), tasks, scans, maintenance; "Now Playing" mock
- [x] 2.6 `watch-activity` detail: plays and watch time, top titles, users, devices, daily trends, recent plays, Tautulli vs Plex history; top-titles list and mini chart mock
- [x] 2.7 `dashboard` detail: one page with charts, local / online (private claude.ai page) / both, updates in place; mini-dashboard mock
- [x] 2.8 Privacy & safety section: read-only, credentials never in chat, private config file, revoke from Plex Authorized Devices
- [x] 2.9 Setup guide: requirements, install, connect, optional Tautulli (three paths), manual setup fallback, revoking access; copy buttons on each command; links to the matching README sections
- [x] 2.10 Notices: "AI can make mistakes" caution and the not-affiliated-with-Plex-or-Anthropic notice
- [x] 2.11 Footer: "Created by Jereme Hancock", GitHub link to `https://github.com/jeremehancock/cinemetric`, MIT license link
- [x] 2.12 Cross-check every claim on the page against README.md and `openspec/specs/*`

## 3. Enhancements (`script.js`)

- [x] 3.1 Add `js` class to `<html>` on load; scroll-in reveals via IntersectionObserver applied only under that class
- [x] 3.2 Sticky header backdrop on scroll and current-section highlight in the nav
- [x] 3.3 Copy buttons with clipboard API, fallback, and "Copied" feedback through an `aria-live` region
- [x] 3.5 Respect `prefers-reduced-motion` in both CSS and JS

## 4. Polish and checks

- [x] 4.1 Responsive layout from 360px to wide desktop with no horizontal page scroll; code blocks scroll inside themselves
- [x] 4.2 Keyboard pass: visible focus rings, skip link works, all controls reachable; decorative SVGs `aria-hidden`
- [x] 4.3 Confirm no external requests (grep for `http` in `src`/`href` of scripts, styles and fonts) and no framework or `package.json`
- [x] 4.4 Load the page with JavaScript disabled and confirm all content is visible
- [x] 4.5 Serve `website/` with `python3 -m http.server` and check it in a browser at phone and desktop widths; take screenshots
- [x] 4.6 Render `og-image.png` from the hero with a headless browser if one is available (otherwise leave the tag pointing at the favicon and note it)

## 5. Docs

- [x] 5.1 Add a one-line pointer to `website/` in README.md (live URL to be added by the owner after Coolify deploy)
- [x] 5.2 No version bump: this change touches no script, skill or manifest, so the plugin is unchanged

## 6. Review feedback

- [x] 6.1 Balance heading line breaks so no headline leaves one word alone on a line
- [x] 6.2 Privacy cards: one-line titles and body text of similar length
- [x] 6.3 Open every outside link in a new tab with `rel="noopener noreferrer"`
- [x] 6.4 Link the creator's name in the footer to https://jeremehancock.com
- [x] 6.5 Two-tab demo panels: real terminal output first, illustration second; real dashboard screenshot from sample data
- [x] 6.6 Replace the hero's colored tiles with 30 real posters from the owner's Plex server (no token or address in the files)

## 7. Second review

- [x] 7.1 Remove underlines from links
- [x] 7.2 Remove the hover tilt on the demo panels
- [x] 7.3 Remove the "At a glance" graphics from the four text-only skills; keep tabs only on the dashboard demo
- [x] 7.4 Remove the hero stats strip and its counters, and the styles left unused by these removals

## 8. Dashboard demo polish

- [x] 8.1 Show each dashboard tab's caption only on that tab
- [x] 8.2 Stack both dashboard tabs in one spot so switching doesn't change the panel's size or move the page
