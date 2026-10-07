## 1. Docs

- [x] 1.1 Add the three points to "What the skills do not protect against" in `SECURITY.md`
- [x] 1.2 Add one sentence to the README's "AI can make mistakes" caution, linking to `SECURITY.md`
- [x] 1.3 Add the same sentence to the website's "AI can make mistakes" notice

## 2. Checks

- [x] 2.1 Add a website test that the notice has the new sentence and doesn't promise more
- [x] 2.2 Run `python3 -m unittest discover -s tests` and `openspec validate --strict`; confirm no em dashes in the changes
