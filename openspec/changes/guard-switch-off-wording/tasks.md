## 1. Wording

- [x] 1.1 README Mods section: replace "only you can turn it off ... never Claude" with the guard being meant to be turned off only by the user, Claude's usual ways refused, and a safety net rather than a lock
- [x] 1.2 SECURITY.md: same change to "Only you can switch it off"
- [x] 1.3 Website guard card caveat and the "switching mods" paragraph in `website/index.html`
- [x] 1.4 The `read_only_guard` description in `plugins/cinemetric/.claude-plugin/plugin.json`
- [x] 1.5 Search the repo for any other user-facing "only you can" / "never Claude" claim about the guard

## 2. Tests

- [x] 2.1 Update `tests/test_mods.py` to check the new website wording, and that "never Claude" is gone
- [x] 2.2 Run `python3 -m unittest discover -s tests` and `claude plugin test plugins/cinemetric`

## 3. Release

- [x] 3.1 Bump the version in every script's `VERSION`, `plugin.json` and `marketplace.json` (0.23.1 to 0.23.2)
- [x] 3.2 Run `claude plugin validate plugins/cinemetric` and `openspec validate guard-switch-off-wording`
