## Context

Cinemetric is a Claude Code plugin with five read-only skills for Plex. Its users find it through the
GitHub README today. The owner wants a public landing page, hosted on their own Coolify instance, that
"feels like Plex" and shows off the skills and how to set them up. Coolify can serve any folder of
static files, so the repo only needs to provide that folder; the owner handles the Coolify side.

Facts on the page come from existing sources of truth: README.md (install and setup steps),
`openspec/specs/*` (what each skill reports, security promises) and the plugin manifests (repo URL,
author). The site is a summary for newcomers, not a second copy of the docs.

## Goals / Non-Goals

**Goals:**
- A single, polished landing page in `website/` that a static host serves with zero configuration.
- A look that a Plex user recognises instantly: dark charcoal surfaces, warm amber accent, poster-like
  cards, media-player chrome.
- Clear coverage of all five skills with believable sample output, plus a short, copyable setup guide.
- Fast and dependable: no external requests, no build, small total size, works with JS off.

**Non-Goals:**
- Coolify configuration, Dockerfiles, nginx configs, domains or TLS (owner does this).
- A docs site, blog, multiple pages, search or analytics.
- Any live connection to a Plex server; all data on the page is invented sample data.
- Changes to the plugin, its skills or version number.

## Decisions

### File layout
```
website/
  index.html          all content, semantic sections
  styles.css          design tokens + layout + components
  script.js           progressive enhancements only
  favicon.svg         Cinemetric mark
  og-image.png        social share preview (1200×630), captured from the hero with a
                      headless browser; skipped if no browser is available to render it
```
One HTML file keeps everything a visitor reads in one place and is the simplest thing for Coolify to
serve. Alternative considered: separate pages per skill. Rejected: five short sections read better as
one scroll, and multiple pages mean duplicated header/footer markup without a templating step.

### No external requests, including fonts
Use a system font stack (`-apple-system, "Segoe UI", Roboto, Inter, ...`) rather than Google Fonts.
This matches the project's recent decision to drop web fonts from the dashboard
(`remove-dashboard-web-fonts`), keeps the page private for visitors (no third-party calls) and fast.
Icons are hand-drawn inline SVG, not an icon library.

### Plex-inspired visual language, without Plex's brand
- Palette as CSS custom properties: near-black background (`#111215`-ish), raised panels
  (`#1f2326`), Plex-style amber accent (around `#e5a00d`) for buttons, highlights and focus rings,
  soft greys for secondary text. Checked against WCAG AA.
- Hero: a large headline over a slowly drifting, blurred "poster wall" of 30 real posters from the
  owner's Plex server (owner's choice, made knowing posters are studio artwork), with an amber glow.
  They were fetched once with GET requests using the plugin's own config loader (token never printed),
  resized to 200×300, stripped of metadata and checked to contain no token. They live in
  `website/posters/`. Install commands sit in a
  terminal-style card.
- Skill sections styled like a Plex library: each skill is a "poster card" in a horizontal shelf
  near the top for quick navigation, and below, a detail row per skill with an example prompt and its
  demo panel.
- Honest demos: three of the skills reply in text in the terminal, so designed graphics would
  misrepresent them. `setup`, `library-report`, `server-health` and `watch-activity` each show only a
  realistic Claude Code reply that follows that skill's `SKILL.md` order, with sample data, in a
  terminal-style panel. `dashboard` really produces a page, so its panel has two tabs: "In your browser", a
  screenshot of the real dashboard (`website/screens/dashboard.jpg`) rendered by the real `render()`
  function from an invented sample data set in its dark theme, and "In your terminal", the
  conversation. Alternatives considered and dropped: a second "At a glance" graphic tab for the text
  skills (owner saw no reason to show it, since those skills never produce a graphic). Tables in the
  terminal replies are HTML tables styled like terminal tables, because box-drawing characters line up
  badly in some system fonts.
- Links have no underline; they're told apart by color and weight, at the owner's request.
- Our own mark: a simple amber chevron/play-shaped "C" in SVG. The Plex logo and wordmark are never
  used, per the trademark notice.
Alternative considered: a light theme toggle. Rejected for now: Plex's identity is dark, and one well-
tuned theme is better than two half-tuned ones.

### Enhancements in `script.js`
Content is in the HTML; JS only adds polish, gated so nothing depends on it:
- Scroll-in reveals with `IntersectionObserver`. The "hidden until revealed" state is applied only
  after JS adds a `js` class to `<html>`, so with JS off everything is visible.
- Sticky header that gains a blurred backdrop after scrolling, and highlights the current section.
- Copy buttons using `navigator.clipboard.writeText`, with a fallback selection method and a
  "Copied" confirmation announced through an `aria-live` region.
- Tabs on the dashboard demo (click or arrow keys); without the script both views show, labeled.
- All motion disabled under `prefers-reduced-motion: reduce` (in both CSS and JS).

### Keeping content honest and in sync
Text is written fresh in plain, friendly English but every claim is checked against README.md and the
specs during implementation. The setup section stays short and links to the README's sections for the
full steps, so future setup changes only have to be made in one place for the details to stay right.
The version number is not shown on the page, so it doesn't go stale on every bump.

### README pointer
Add one line near the top of README.md pointing at `website/`. The live URL is added later by the
owner once Coolify is set up, since it isn't known yet.

## Risks / Trade-offs

- [Site text drifts from the README as features change] → Keep site copy high-level, link to README
  for detail, and note in tasks that skill changes should glance at `website/index.html`.
- [Looking "too much" like Plex could imply endorsement] → Own logo, own name everywhere, the
  not-affiliated notice in the footer, no Plex artwork or logos.
- [Social preview image needs an absolute URL that isn't known yet] → Use relative paths now;
  leave a clearly marked spot for the owner to set the full `og:url`/`og:image` once deployed.
- [Clipboard API blocked when opened from `file://` or plain http] → Fallback copy method plus the
  command text is always selectable.

## Migration Plan

New folder only; nothing to migrate. To deploy, the owner points a Coolify static site at `website/`.
Rollback is removing the folder or the Coolify app.

## Open Questions

- Final public URL (needed for the README link and full social-preview tags). Owner to supply after
  deployment.
