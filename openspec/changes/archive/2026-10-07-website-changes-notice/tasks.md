## 1. Website and README

- [x] 1.1 Add the "Changes are up to you" notice beside "AI can make mistakes", and take the changes sentence out of the caution
- [x] 1.2 Remove the website's "Early days" notice and add an "Issues" link to the footer
- [x] 1.3 Set the notice grid to two equal columns, stacking from 860px; give both notices the same card style, with colored headings
- [x] 1.4 Remove the README's "Early days" note and link "GitHub issues" in the Roadmap
- [x] 1.5 Take the notices off the evened-out (balanced) wrapping list so their text fills the cards

## 2. Checks

- [x] 2.1 Update `tests/test_safety_wording.py`: the new notice, the caution only about reports, "Early days" gone, issues still linked
- [x] 2.2 Run the Python tests and `openspec validate --strict`; check the layout at wide and phone widths; confirm no em dashes
