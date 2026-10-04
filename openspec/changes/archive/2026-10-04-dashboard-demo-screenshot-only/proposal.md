## Why

The dashboard skill's output is an HTML page, saved on the user's computer, published as a private
claude.ai page, or both. Claude's reply in the terminal is only a short note saying where the page is.
The website's dashboard demo still has an "In your terminal" tab next to the screenshot, which suggests
the terminal reply is part of what the skill gives you. It isn't, so the tab adds nothing.

## What Changes

- The dashboard demo on the website shows only the screenshot of the real dashboard page, with no tabs.
- The "In your browser" / "In your terminal" tab bar, the terminal conversation and the hidden panel
  labels are removed from the dashboard section.
- The tab script and tab styles are removed, since the dashboard was the only place that used them.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `website`: "Shows every skill" no longer asks for a conversation tab on the dashboard demo, and its
  two tab scenarios are replaced by one about the screenshot. "Works without JavaScript" no longer
  lists tabs among the script enhancements.

## Impact

- `website/index.html`, `website/script.js`, `website/styles.css`.
- No skill, script or manifest changes, so no version bump.
