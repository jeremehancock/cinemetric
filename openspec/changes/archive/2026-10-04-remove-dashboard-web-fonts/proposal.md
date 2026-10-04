## Why

The dashboard page links to Google Fonts, so whenever the user opens it their browser contacts Google.
That breaks Cinemetric's promise that it talks only to Plex and Tautulli, with no third-party services.
It also tells Google each time the user looks at a page that's meant to stay private on their computer.
The backfilled `security` spec lists this as the one exception; this change removes the exception.

## What Changes

- The dashboard page no longer links to Google Fonts. It uses fonts already on the user's computer.
- The page declares a Content Security Policy that blocks every outside request, so a future edit
  can't quietly add one back.
- The look changes slightly: headings and numbers use the closest installed font instead of Big
  Shoulders Display and IBM Plex.
- Version bump to 0.3.1.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `security`: "Only known destinations" loses its Google Fonts exception and adds a scenario for
  opening the dashboard.
- `dashboard`: "Rule-based page" adds that the page loads nothing from outside itself and enforces it
  with a Content Security Policy.

## Impact

- `plugins/cinemetric/skills/dashboard/scripts/dashboard.py`: remove `FONTS`, add the CSP meta tag,
  update the font lists in the CSS and the module docstring.
- Existing dashboards are fixed the next time they're rebuilt. Scheduled updates run from a copy of
  the scripts, so users with automation need to run `schedule install` again after updating (the
  skill already tells Claude to do this).
- `VERSION` in all five scripts, `plugin.json` and `marketplace.json`.
