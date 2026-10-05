## Why

On screens 640px wide or narrower, the website hides the Skills, Privacy, Setup and Support links in
the header and puts nothing in their place. Phone visitors see only the logo and a GitHub icon, so the
only way to reach the setup guide is to scroll the whole page.

## What Changes

- Add a menu button to the header at phone widths. Tapping it opens a panel with the section links
  (Skills, Privacy, Setup, Support) and the GitHub link.
- The menu closes when a link is chosen, when the button is tapped again, when Escape is pressed, or
  when the visitor taps outside it. The button tells screen readers whether the menu is open.
- Without JavaScript there is no button; the section links stay visible in the header on phones
  instead of being hidden.
- Desktop and tablet widths are unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `website`: the "Accessible and responsive" requirement now says the main navigation must stay
  reachable at phone width, through a menu button, and without JavaScript.

## Impact

- `website/index.html`: a menu button in the header.
- `website/styles.css`: phone-width header and menu panel styles.
- `website/script.js`: opening and closing the menu.
- No plugin code changes. The website does not ship with the plugin, so no version bump.
