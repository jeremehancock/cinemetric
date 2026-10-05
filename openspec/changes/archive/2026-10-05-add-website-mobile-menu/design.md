## Context

The header nav (`website/index.html`) holds four in-page links plus a GitHub link. At 640px and below,
`styles.css` hides the four in-page links and the GitHub label. The site must stay plain HTML, CSS and
JS with no frameworks, and all content must be usable without JavaScript.

## Goals / Non-Goals

**Goals:**
- Phone visitors can reach every header link.
- Works without JavaScript, by keyboard, and with screen readers.

**Non-Goals:**
- Changing the desktop header or the current-section highlight.
- A full-screen overlay, slide-in drawer or animated hamburger-to-X icon.

## Decisions

- **Button starts `hidden` in the HTML; the script reveals it.** Without JavaScript the button never
  appears, so there is no dead control. Alternative: a CSS-only checkbox or `<details>` toggle. Rejected
  because the nav would need restructuring and they handle `aria-expanded` and Escape poorly.
- **A separate `menu-js` class on `<html>` for the collapsed layout.** The existing `js` class is only
  set when reduced motion is off (it drives the scroll-in animations), so the menu can't rely on it.
  Without `menu-js`, phone widths show the links in a wrapping row inside the header.
- **Drop-down panel under the header**, reusing the header's blurred dark background, with links
  stacked full width as large tap targets. The panel fades in briefly; the existing reduced-motion rule
  already turns transitions off.
- **Closing:** choosing a link, tapping the button, pressing Escape (focus returns to the button),
  tapping outside, or widening past 640px.

## Risks / Trade-offs

- [The header grows taller without JavaScript on phones] → Acceptable: the links stay reachable, and
  `scroll-padding-top` only matters for the rare no-JS visitor.
- [Sticky header plus open panel covers content] → The panel closes as soon as a link is chosen.
