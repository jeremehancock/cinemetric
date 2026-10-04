## Why

Cinemetric now has a website at https://cinemetric.dev. The plugin's `homepage` still points to the
GitHub repository, so the "homepage" link people see for the plugin skips the friendlier introduction.

## What Changes

- `homepage` in `plugins/cinemetric/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
  becomes `https://cinemetric.dev`.
- `repository` in `plugin.json` stays `https://github.com/jeremehancock/cinemetric`, so the source is
  still one click away.
- Version bump to 0.4.1 (every script's `VERSION`, `plugin.json`, `marketplace.json`). It's a
  metadata-only change, so a patch bump.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `conventions`: adds a requirement that the plugin's `homepage` is the website and its `repository` is
  the GitHub repository.

## Impact

- Two manifests and five scripts' `VERSION` constants. No behavior change in any script.
