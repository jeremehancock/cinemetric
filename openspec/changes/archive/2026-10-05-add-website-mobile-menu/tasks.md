## 1. Markup

- [x] 1.1 Add a `hidden` menu button (with `aria-controls` and `aria-expanded="false"`) to the header in `website/index.html`, and an id on the nav it controls

## 2. Styles

- [x] 2.1 At 640px and narrower without the `menu-js` class, show the header links in a wrapping row instead of hiding them
- [x] 2.2 At 640px and narrower with `menu-js`, show the button and style the nav as a drop-down panel that appears only when open
- [x] 2.3 Keep desktop and tablet widths unchanged, and hide the button there

## 3. Script

- [x] 3.1 In `website/script.js`, add the `menu-js` class, reveal the button, and toggle the panel and `aria-expanded`
- [x] 3.2 Close the menu on link choice, Escape (focus back to button), outside tap, and resize past phone width

## 4. Check

- [x] 4.1 Check at 360px with and without JavaScript, at desktop width, and with keyboard only; confirm no sideways scroll
