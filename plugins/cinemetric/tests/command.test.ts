// The /cinemetric-mods command, run through Claude Code's own engine with
// `claude plugin test plugins/cinemetric`. See openspec/specs/mods/spec.md.

import { describe, expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { ConfigRow, On, PromptOrigin } from 'claude-code'

// Stands in for the /config menu: one row per setting, changed by
// $.config.set. Returns the row so a test can read what it holds now.
function configMenu(on: On, isGuardOn: boolean) {
  const row: { -readonly [K in keyof ConfigRow]: ConfigRow[K] } = {
    key: 'cinemetric.read_only_guard',
    label: 'Read-only guard',
    kind: 'boolean',
    value: isGuardOn,
    provider: { plugin: 'cinemetric', tier: 'user' },
    isLocked: false,
  }
  mock.env(on, { HOME: '/home/u' })
  on('config.list', () => ({ value: [{ ...row }] }))
  on('config.set', ($, e) => {
    row.value = e.value
    return { value: e.value }
  })
  return row
}

const USER: PromptOrigin = { kind: 'composer' }

function run($: Engine, args: string, origin = USER) {
  return $.command.run({
    command: 'cinemetric-mods',
    args,
    origin,
    presentation: { isFullscreen: false, columns: 100 },
  })
}

describe('/cinemetric-mods', () => {
  test('on its own, lists every mod and whether it is on', async ($, on) => {
    configMenu(on, true)
    const { text } = await run($, '')
    expect(text).toContain('guard (on)')
    expect(text).toContain('Read-only guard')
  })

  test('shows the guard as off when it is switched off', { options: { read_only_guard: false } }, async ($, on) => {
    configMenu(on, false)
    const { text } = await run($, '')
    expect(text).toContain('guard (off)')
  })

  test('says so when the guard is already on', async ($, on) => {
    configMenu(on, true)
    const { text } = await run($, 'guard on')
    expect(text).toContain('already on')
  })

  test('switches the guard off when the user types it', async ($, on) => {
    const row = configMenu(on, true)
    const { text } = await run($, 'guard off')
    expect(text).toContain('guard is now off')
    expect(row.value).toBe(false)
  })

  test('a typo changes nothing and shows the right form', async ($, on) => {
    const row = configMenu(on, true)
    const { text } = await run($, 'gaurd off')
    expect(text).toContain('Nothing changed')
    expect(text).toContain('Mods: guard')
    expect(row.value).toBe(true)
  })

  test('works with every mod off, so the guard can come back on', { options: { read_only_guard: false } }, async ($, on) => {
    const row = configMenu(on, false)
    const { text } = await run($, 'guard on')
    expect(text).toContain('guard is now on')
    expect(row.value).toBe(true)
  })

  test('lists Now Playing, off by default', async ($, on) => {
    configMenu(on, true)
    const { text } = await run($, '')
    expect(text).toContain('now (off)')
    expect(text).toContain('Mods: guard, status, now.')
  })

  test('anyone can switch Now Playing on and off', { options: { now_playing_pane: true } }, async ($, on) => {
    const sets: unknown[] = []
    mock.env(on, { HOME: '/home/u' })
    on('config.list', () => ({ value: [] }))
    on('config.set', ($, e) => {
      sets.push([e.key, e.value])
      return { value: e.value }
    })
    const { text } = await run($, 'now off', { kind: 'sdk' })
    expect(text).toContain('now is now off')
    expect(sets).toEqual([['cinemetric.now_playing_pane', false]])
  })

  test('only the user can switch the guard off', async ($, on) => {
    const row = configMenu(on, true)
    const { text } = await run($, 'guard off', { kind: 'sdk' })
    expect(text).toContain('Only you can switch the guard off')
    expect(row.value).toBe(true)
  })
})
