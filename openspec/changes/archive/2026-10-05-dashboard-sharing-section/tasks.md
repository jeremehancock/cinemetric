## 1. Collect the sharing report

- [x] 1.1 Add `sharing` to `SOURCES` in `dashboard.py` (`users-and-shares`, `users_and_shares.py`, no extra arguments) and size the thread pool to `len(SOURCES)`
- [x] 1.2 Update the "every report fails" rule to cover all sources (it already compares against `len(SOURCES)`; check the message still makes sense)

## 2. Sharing section

- [x] 2.1 Add a `sharing_section(sharing, hide_names, error)` wide card after the library section: counts row (people, Plex Home, managed, friends, pending), library table (name, number of people)
- [x] 2.2 Turn each `worth_a_look` item into a short neutral sentence with a count, adding names only when names are shown
- [x] 2.3 When names are shown, list people (name, type, libraries count or "all", last played or "no plays found"), at most 20, then "and N more"
- [x] 2.4 One-line message when `people` is empty; on failure, show the reason with any leading `OWNER_ONLY: ` / `NOT_CONFIGURED: ` code removed
- [x] 2.5 Keep sharing items out of `attention_items` and `overall_status`; HTML-escape every value; reuse existing card, tile and list styles, adding only the CSS the section needs

## 3. Tests

- [x] 3.1 Add a made-up sharing report to the dashboard test data and cover each spec scenario: section built, OWNER_ONLY failure (page still written, `sections_missing.sharing`, no code prefix), downloads item doesn't change "Healthy", names hidden (no names anywhere, counts only), 26 people listed as 20 plus "6 more", nobody shared
- [x] 3.2 Extend the existing escaping test so a crafted name or library title in the sharing report is escaped
- [x] 3.3 `python3 -m unittest discover -s tests` passes

## 4. SKILL.md

- [x] 4.1 Update the dashboard `description` to mention who the server is shared with
- [x] 4.2 First-time online publishing note: the page also lists the people the server is shared with
- [x] 4.3 Summary step: sharing items can be mentioned in one line as things to check, not problems; `sections_missing.sharing` with OWNER_ONLY means the user isn't the owner

## 5. Docs and website

- [x] 5.1 README: dashboard row mentions sharing; `marketplace.json` description if needed
- [x] 5.2 Website: dashboard copy mentions sharing; add a made-up sharing report to the invented data set and retake `website/screens/dashboard.jpg` from the real `render()`
- [x] 5.3 After archiving, update the `dashboard` spec's Purpose line to include the sharing report

## 6. Verify

- [x] 6.1 Build the dashboard against the real server with names shown and hidden; check the Sharing section matches the `users-and-shares` report and no names appear when hidden
- [x] 6.2 `openspec validate dashboard-sharing-section` passes

## 7. Release

- [x] 7.1 Bump the version to 0.9.0 in all six scripts, `plugin.json` and `marketplace.json`
