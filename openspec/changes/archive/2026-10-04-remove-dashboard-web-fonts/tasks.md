## 1. Remove the outside fonts

- [x] 1.1 In `dashboard.py`, delete the `FONTS` constant and its use in `full_page`
- [x] 1.2 Add the Content Security Policy meta tag (`default-src 'none'; style-src 'unsafe-inline'; img-src data:`) as the first element in `<head>`
- [x] 1.3 Update the module docstring: no external requests at all (drop "except optional web fonts")

## 2. Check the look

- [x] 2.1 Build a dashboard from sample report JSON and open it in a browser; confirm no network requests and no policy violations in the console
- [x] 2.2 Compare headings, big numbers and tables in light and dark mode; add fallback fonts to `--font-display`, `--font-body` or `--font-mono` only where a platform falls back to something that looks wrong

## 3. Verify the spec scenarios

- [x] 3.1 Confirm the generated page has no `http://` or `https://` resource links (grep the output)
- [x] 3.2 Confirm `<head>` starts with the `default-src 'none'` policy

## 4. Release

- [x] 4.1 Bump the version to 0.3.1 in all five scripts, `plugin.json` and `marketplace.json`
- [x] 4.2 Note in the commit message that users with automatic updates should run `schedule install` again to pick up the change
