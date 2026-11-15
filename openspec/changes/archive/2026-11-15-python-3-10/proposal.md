## Why

Python 3.8 stopped getting updates, security fixes included, in October 2024, and Python 3.9 in
October 2025. GitHub's newest Ubuntu no longer offers Python 3.8, so the tests' 3.8 run only works by
staying on Ubuntu 24.04, which GitHub will retire too. Python 3.10 is the oldest version that still
gets security fixes and that GitHub's newest Ubuntu offers, and almost everyone already has it or
newer.

## What Changes

- Cinemetric's minimum Python goes from 3.8 to 3.10, everywhere it's stated: the specs, the README,
  the website's setup guide, `tests/README.md` and `openspec/config.yaml`.
- The tests run on Python 3.10 and the newest stable Python, both on GitHub's newest Ubuntu, so the
  Ubuntu 24.04 special case goes away.
- The Now Playing pane's message when Python won't start says 3.10.
- No script changes: everything that ran on 3.8 runs on 3.10. Nothing new from 3.9 or 3.10 is used
  yet; later changes may.
- Version bump to 0.33.1.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `conventions`: "Standard library only" says Python 3.10 or newer.
- `testing`: "Tests run on GitHub", "One summary check" and "One command runs everything" say 3.10.
- `now-playing-pane`: "When a check fails" has the 3.10 message.
- `website`: "Shows how to set up" lists Python 3.10+.
- `mods`: "Telling the user when mods can't run" calls `mods_notice.py` a Python 3.10+ script.

## Impact

- Changed: `.github/workflows/tests.yml`, `plugins/cinemetric/hooks/now-playing-rules.ts`,
  `README.md`, `website/index.html`, `tests/README.md`, `openspec/config.yaml`.
- `VERSION` in every script, `plugin.json` and `marketplace.json`.
- People on Python 3.8 or 3.9: Cinemetric still runs for now, but it's no longer tested there and a
  later version may stop working.
