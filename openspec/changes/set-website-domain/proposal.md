## Why

The website is now live at https://cinemetric.dev. Link previews (Slack, Discord, X, Facebook) need the
page's full address and a full image address to show the title card, and the README should send people
to the live site.

## What Changes

- `website/index.html`: set `og:url` to `https://cinemetric.dev/`, make `og:image` the full address
  `https://cinemetric.dev/og-image.png` (with its size and alt text), add `twitter:image`, and add a
  `canonical` link so search engines treat `https://cinemetric.dev/` as the page's one address.
  Remove the "set this once the site is live" comment.
- `README.md`: link the live site at https://cinemetric.dev alongside the existing pointer to
  `website/`.
- No plugin, skill or script changes, so no version bump. The plugin's `homepage` in `plugin.json` and
  `marketplace.json` stays the GitHub repository.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `website`: adds a requirement that the page declares its live address and full-address social
  preview image.

## Impact

- Two files edited: `website/index.html` and `README.md`. All links between the site's own files stay
  relative, so the site still works from any address or straight from disk.
