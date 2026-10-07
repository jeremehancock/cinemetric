// Cinemetric's mods: the /cinemetric-mods command, and each mod whose switch
// is on. Claude Code loads this module again whenever a switch changes, so
// turning a mod on or off takes effect without a restart.

import type { Register } from 'claude-code'

import { setUpCommand } from './command'
import { setUpGuard } from './guard'
import { GUARD_SETTING } from './guard-rules'
import { setUpNowPlaying } from './now-playing'
import { NOW_SETTING } from './now-playing-rules'
import { setUpStatusLine } from './status-line'
import { STATUS_SETTING } from './status-line-rules'

export const register: Register = (on, options) => {
  // Tells hooks/mods_notice.py that the mods are running, so it stays quiet.
  // Set before the SessionStart settings hooks run, which inherit it. On a
  // Claude Code without mods nothing sets it, and the script shows a notice.
  on('classic.SessionStart', async ($, e, next) => {
    await $.env.set('CINEMETRIC_MODS_ACTIVE', '1')
    return next(e)
  }).catch(($, e, next) => next(e))

  setUpCommand(on, options)
  // Also adds the /cinemetric-mods command at session start, on or off.
  setUpStatusLine(on, options[STATUS_SETTING] === true)
  // Adds the /cinemetric-now command at session start, on or off.
  setUpNowPlaying(on, options[NOW_SETTING] === true)
  if (options[GUARD_SETTING] === true) setUpGuard(on)
}
