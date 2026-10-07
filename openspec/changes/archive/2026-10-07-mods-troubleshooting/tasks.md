## 1. Notice

- [x] 1.1 Reword `NOTICE` and `CONTEXT` in `hooks/mods_notice.py` to give both fixes
- [x] 1.2 Update `tests/test_mods_notice.py` to check the `env` setting is named

## 2. README and website

- [x] 2.1 README: "works best in your favorite terminal" near the top and in Install
- [x] 2.2 README: replace "Claude Code version" with "Mods not running?", and add "Where to use it"
- [x] 2.3 Website: the same, briefly, in the setup section and the Mods section, linking to the README

## 3. Now Playing

- [x] 3.1 Close the panel and start no checks when Claude Code says it wasn't drawn; reply with why
- [x] 3.2 Test it with an app that can't draw panels

- [x] 3.3 `/cinemetric-mods`: give Claude Code's reason when a switch fails, and point to a terminal

## 4. Release

- [x] 4.1 Bump the version to 0.25.1 (scripts, plugin.json, marketplace.json)
- [x] 4.2 Run the Python and plugin tests and `openspec validate --strict`; confirm no em dashes
