## Context

The changes sentence was added to the website's "AI can make mistakes" notice. Its heading is about
reports being wrong, so a visitor skimming headings misses it. The "Early days" notes are being
dropped from the website and README at the same time.

## Goals / Non-Goals

**Goals:** a heading of its own that a skimming visitor sees, worded calmly; keep a route to GitHub
issues once "Early days" is gone.

**Non-Goals:** moving the wording into "Look, don't touch" (that section describes what Cinemetric
itself does); changing SECURITY.md.

## Decisions

- **Its own notice, beside the caution, in the same card style.** The caution's amber border and
  tint are removed, so neither notice looks selected next to the other. Each keeps a colored heading,
  so both still catch the eye without looking like a warning.
- **Heading "Changes are up to you".** It frames the user as in charge. Alternatives considered:
  "Be careful asking Claude to change things" (sounds like a warning) and "What Cinemetric can't
  control" (sounds like a disclaimer).
- **Layout.** With "Early days" gone there are two notices, so two equal columns, stacking from
  860px down as before.
- **Issues link.** A plain "Issues" link in the footer beside "Security" on the website, and a link
  on the README Roadmap's existing "GitHub issues" mention.
