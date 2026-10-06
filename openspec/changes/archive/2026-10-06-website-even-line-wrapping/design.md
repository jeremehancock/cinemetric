## Context

The site is plain HTML, CSS and JavaScript, with no build step. Its headings already used
`text-wrap: balance`. Body text used normal wrapping, which often left one or two words alone on the
last line. Where that happened depended on the screen width, so changing the wording only moved the
problem to another width.

## Goals / Non-Goals

**Goals:**
- No single-word last lines anywhere on the page, at any width from 320px to wide desktop.
- No short text (three lines or fewer) whose last line is a word or two under a full line.
- The same result in Chrome, Safari and Firefox, without changing the copy.

**Non-Goals:**
- Hyphenation or justified text.
- The headline's line break, which is deliberate.

## Decisions

- **`balance` for short text, `pretty` for long text.** `balance` evens out every line, which suits a
  bullet or a one- to three-line intro, but browsers only apply it to a handful of lines (about six in
  Chrome). `pretty` only adjusts the end of a paragraph, so it suits longer prose. Alternative:
  `pretty` everywhere. Rejected because it still allows a two-word second line under a full first line.
- **Firefox fallback in `script.js`, only when `CSS.supports("text-wrap", "pretty")` is false.** It
  replaces the last space in each paragraph, list item and caption with a non-breaking space, working
  on the element's whole text so links and bold words at the end are handled. Firefox already supports
  `balance`, so short text is even there too. Alternative: hand-placed `&nbsp;` in the HTML. Rejected
  because every new sentence would need remembering, and Chrome and Safari don't need it.
- **Skip word pairs over 24 characters**, so a long path or command can't be forced out of a narrow
  column.
- **One hand-placed `&nbsp;`** in the "Read-only, always" card, which is too narrow at some widths for
  `pretty` to fix on its own.

## Risks / Trade-offs

- [`balance` leaves short text narrower than its column] → It is used only on short text, where an
  even right edge looks better than a full first line.
- [Without JavaScript, Firefox still shows some single-word last lines] → Acceptable: it is cosmetic,
  and all content is still visible, as the "Works without JavaScript" requirement asks.
