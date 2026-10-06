## 1. Styles

- [x] 1.1 In `website/styles.css`, give paragraphs, list items, captions and poster subtitles `text-wrap: pretty`
- [x] 1.2 Give short text `text-wrap: balance`: tick lists, feature intros, "Ask Claude" lines, privacy cards, mock captions, the setup lead-in, section intros, setup step text, Tautulli and manual-setup details, notices and the footer notice

## 2. Markup

- [x] 2.1 In `website/index.html`, join "or changed." in the "Read-only, always" card with `&nbsp;`

## 3. Script

- [x] 3.1 In `website/script.js`, when `CSS.supports("text-wrap", "pretty")` is false, replace the last space in each paragraph, list item and caption with a non-breaking space, skipping pairs over 24 characters, code blocks and the example chips

## 4. Check

- [x] 4.1 Render the page in headless Chromium at every 40px from 320px to 1600px and confirm no single-word last lines and no short text whose last line is under 40% of its longest line
- [x] 4.2 Repeat with `text-wrap: pretty` removed and `CSS.supports` reporting no support, to stand in for Firefox
- [x] 4.3 Compare real Firefox and Chromium screenshots at 1280px
