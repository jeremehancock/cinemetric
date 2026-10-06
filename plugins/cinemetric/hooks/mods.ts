// Every mod Cinemetric ships. Each one has a short name (what the user types
// after /cinemetric-mods) and the plugin.json userConfig setting that
// switches it. A new mod is added here and switched on in register.ts.
// See openspec/specs/mods/spec.md.

import { GUARD_SETTING } from './guard-rules'
import { STATUS_SETTING } from './status-line-rules'

export type Mod = {
  name: string
  setting: string
  description: string
  // Only the user may switch this mod off: never Claude, never a plugin.
  isUserOnlyOff: boolean
}

export const MODS: readonly Mod[] = [
  {
    name: 'guard',
    setting: GUARD_SETTING,
    description:
      "Read-only guard: stops Claude from running its own commands that would change your Plex server, Tautulli or plex.tv.",
    isUserOnlyOff: true,
  },
  {
    name: 'status',
    setting: STATUS_SETTING,
    description:
      'Library status line: shows how big your Plex library is and when Cinemetric last checked it, just above the prompt.',
    isUserOnlyOff: false,
  },
]
