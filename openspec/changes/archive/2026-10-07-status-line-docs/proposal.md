## Why

A user ran a server health check and expected the library status line to update. It didn't, because
only the `changes` skill and the dashboard save the snapshot the line reads. The README and website
said where the snapshot comes from, but not that other skills leave the line alone, so it looked
like a bug.

## What Changes

- The README's `status` row and the website's Library status line card say the line only updates
  when the `changes` skill or the dashboard saves a new snapshot, and that other skills, like the
  server health check, don't change it.
- No change to the mod, its wording or any script, so no version bump.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `website`: "Shows the mods" asks the Library status line card to say what updates the line.

## Impact

- `README.md` and `website/index.html` only.
