## Context

The dashboard demo panel stacks two tab panels in one grid cell ("In your browser" with the
screenshot, "In your terminal" with a conversation). A small script in `website/script.js` turns the
tab bar on and switches panels; without the script both panels show one after the other with their own
labels. The dashboard is the only demo that uses this.

## Goals / Non-Goals

**Goals:**
- The dashboard demo shows only the screenshot of the real page.
- No leftover code for a feature nothing uses.

**Non-Goals:**
- Changing the screenshot, the dashboard copy, or any other skill's demo.

## Decisions

- **Remove the tab code rather than keep it for later.** Nothing else uses tabs, and an unused
  script and styles are just more to maintain. If a future demo needs tabs, it can be added back with
  that demo. Alternative considered: keep the code dormant. Rejected because it would sit untested.
- **Keep the window frame.** The panel keeps the `mock-bar` (the three dots), now with a plain title
  like the other demos, so all five demo panels look alike. The screenshot keeps its own scroll box
  and its caption becomes the figure's `figcaption`, as in the other demos.

## Risks / Trade-offs

- [The other demos' `tabpanel` wrappers also rely on `.tabpanel` styles] → Keep the base `.tabpanel`
  styles that those panels use; only remove rules that exist for switching (tab bar, tab stack, hidden
  labels, dashed divider).
