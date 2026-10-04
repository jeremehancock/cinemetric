## Context

`dashboard.py` writes a single HTML file. Its `<head>` includes a `FONTS` link to
`fonts.googleapis.com` for three families (Big Shoulders Display, IBM Plex Sans, IBM Plex Mono). The
CSS already has fallbacks after each one, in `--font-display`, `--font-body` and `--font-mono`.
Nothing else on the page is loaded from outside: the charts are inline SVG and the styles are inline.

## Goals / Non-Goals

**Goals:**
- Opening the dashboard makes no network requests at all.
- That stays true after future edits, without relying on someone remembering the rule.
- The page still looks deliberate and readable on Linux, macOS and Windows.

**Non-Goals:**
- Matching the current fonts exactly.
- Changing the layout, colors or anything else on the page.

## Decisions

**Use fonts already on the computer.** Remove the `FONTS` link and keep the existing font lists. If
the user happens to have IBM Plex or Big Shoulders installed, the browser uses them locally (no
network); otherwise it falls through to the existing fallbacks (Arial Narrow / Roboto Condensed,
system-ui / Segoe UI, ui-monospace / Menlo). Add more fallbacks (for example a condensed font that
ships with macOS or Windows for headings) only where a platform falls back to something that looks
wrong.

*Alternative considered: embed the font files in the page as base64.* That keeps the exact look, but
adds roughly 150–300 KB to every dashboard and to the script (the script must stay standard-library
only and self-contained, so the fonts would live in the source). Not worth it for a private status
page.

**Enforce it with a Content Security Policy.** Add
`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">`
as the first element in `<head>`. The browser then refuses any outside font, stylesheet, image or
script, even if one is added by mistake later. This matches how the rest of Cinemetric enforces its
rules in code (allowlists) instead of by convention. The setup form already uses a similar policy.

*Alternative considered: only remove the link.* Simpler, but nothing would stop the same gap coming
back.

## Risks / Trade-offs

- [The page looks a little plainer, especially the large numbers and headings] → Keep the existing
  weights and letter-spacing so the hierarchy holds; compare before/after screenshots in light and
  dark mode.
- [A strict policy could block something the page legitimately needs] → The page uses only inline
  styles and inline SVG today; check the browser console for policy violations after the change.
- [Scheduled dashboards keep the old fonts link until automation is reinstalled] → The skill already
  tells Claude to run `schedule install` again after an update; call this out in the release notes.
