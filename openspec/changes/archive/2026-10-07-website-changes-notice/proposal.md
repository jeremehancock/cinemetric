## Why

The website's sentence about changes the user asks Claude to make sits inside the "AI can make
mistakes" notice, whose heading is about reports being wrong. A visitor skimming headings won't
connect it with Claude changing their server, so it's easy to miss. It needs its own heading, worded
so it reads as the user being in control rather than as a danger.

The "Early days" notes on the website and in the README are also no longer wanted. They held the only
link to GitHub issues in each file, so that link needs a new home.

## What Changes

- A new notice, **"Changes are up to you"**, beside "AI can make mistakes". It says Cinemetric only
  reads but Claude can do more than run its skills, that Claude Code shows each command before
  running it so the user should read it before approving, and that switching off Allow media
  deletion in Plex stops Plex deleting media files for any app.
- The "AI can make mistakes" notice goes back to being only about reports, and loses its amber border
  and tint, so the two notices match and neither looks selected.
- The website's "Early days" notice is removed, so the two notices sit side by side (stacked on
  phones). The footer gains an "Issues" link to GitHub issues.
- The README's "Early days" note is removed, and the Roadmap's mention of GitHub issues becomes a
  link.
- The notices' text fills their cards instead of being wrapped into evened-out shorter lines, which
  only suits text of three lines or fewer.
- `tests/test_safety_wording.py` checks the new notice, that "Early days" is gone, and that issues
  are still linked.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `website`: "Matches the project's promises" moves the changes wording into its own notice;
  "Footer credit and link" adds the issues link; "Text doesn't end on a lonely word" stops
  counting notices as short text.

## Impact

- `website/index.html`, `website/styles.css`, `README.md`, `tests/test_safety_wording.py`.
- SECURITY.md unchanged. No plugin changes, no version bump.
