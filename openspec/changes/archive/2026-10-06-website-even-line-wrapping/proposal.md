## Why

Text on the website often wrapped badly: a full line followed by one or two words on their own, such as
"by show." under "Titles added and removed in each library, and new episodes". It made the page look
unfinished, and which words got stranded changed with the screen width, so rewording couldn't fix it.

## What Changes

- Short text (tick lists, feature intros, "Ask Claude" lines, privacy cards, captions, setup steps,
  notices and the footer notice) wraps into lines of roughly even length.
- Longer paragraphs never end on a single word.
- Browsers that can't do the second part on their own (Firefox) get the same result from a small
  addition to `script.js`, which keeps each paragraph's last two words together.
- No wording changes, apart from one non-breaking space in the "Read-only, always" privacy card.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `website`: a new requirement that text doesn't end on a lonely word or a stubby last line.

## Impact

- `website/styles.css`: `text-wrap: balance` for short text, `text-wrap: pretty` for the rest.
- `website/script.js`: a fallback for browsers without `text-wrap: pretty`.
- `website/index.html`: one `&nbsp;` in the "Read-only, always" card.
- No plugin code changes. The website does not ship with the plugin, so no version bump.
