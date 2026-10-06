// The read-only guard, run through Claude Code's own engine with
// `claude plugin test plugins/cinemetric`. Every scenario in
// openspec/specs/read-only-guard/spec.md has a test here, plus the
// settings-file rule from openspec/specs/mods/spec.md.

import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const SETTINGS = '/home/u/.config/cinemetric/config.json'
const TOKEN = 'secret-token-123'

// Stands in for the world beneath the plugin: a home folder, and a settings
// file when one is given. Tool calls that get past the guard are recorded.
function world(on: On, settings?: string, environment: Record<string, string> = {}) {
  const ran: string[] = []
  mock.env(on, { HOME: '/home/u', ...environment })
  on('fs.stat', ($, e) => {
    if (settings === undefined || e.path !== SETTINGS) return { deny: 'no such file' }
    return { value: { kind: 'file' as const, size: settings.length, mtimeMs: 1, isLink: false } }
  })
  on('fs.read', ($, e) => {
    if (settings === undefined || e.path !== SETTINGS) return { deny: 'no such file' }
    return { value: settings }
  })
  on('ui.toast', () => ({ value: undefined }))
  on('tool.call', ($, e) => {
    ran.push(e.tool)
    return { result: {} as never }
  })
  return ran
}

// The refusal the guard gave, or undefined when the call went ahead. The
// kit hands a refusal back as `deny`; a session shows it as an error result.
function refusal(answer: { deny?: string; text?: string; isError?: boolean }): string | undefined {
  return answer.deny ?? (answer.isError ? answer.text : undefined)
}

const CONFIGURED = JSON.stringify({
  plex_url: 'http://192.168.1.20:32400',
  plex_token: TOKEN,
  tautulli_url: 'http://192.168.1.20:8181',
  tautulli_api_key: 'tautulli-secret',
})

describe('commands aimed at the servers', () => {
  test('a delete with curl is blocked', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call({
      tool: 'Bash',
      command: `curl -X DELETE "http://192.168.1.20:32400/library/metadata/123?X-Plex-Token=${TOKEN}"`,
    })
    expect(refusal(answer)).toContain('Cinemetric read-only guard')
    expect(refusal(answer)).toContain('uses the DELETE method')
    expect(ran).toEqual([])
  })

  test('the message never repeats the token', async ($, on) => {
    world(on, CONFIGURED)
    const answer = await $.tool.call({
      tool: 'Bash',
      command: `curl -X PUT "http://192.168.1.20:32400/:/prefs?X-Plex-Token=${TOKEN}"`,
    })
    expect(refusal(answer)).not.toContain(TOKEN)
    expect(refusal(answer)).toContain('/cinemetric-mods guard off')
  })

  test('a read-only check runs', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call({ tool: 'Bash', command: 'curl -s "http://192.168.1.20:32400/identity"' })
    expect(refusal(answer)).toBeUndefined()
    expect(ran).toEqual(['Bash'])
  })

  test('a library scan through a GET is blocked', async ($, on) => {
    world(on, CONFIGURED)
    const answer = await $.tool.call({
      tool: 'Bash',
      command: `curl "http://192.168.1.20:32400/library/sections/1/refresh?X-Plex-Token=${TOKEN}"`,
    })
    expect(refusal(answer)).toContain('starts a library scan')
  })

  test("stopping someone's stream through a GET is blocked", async ($, on) => {
    world(on, CONFIGURED)
    const answer = await $.tool.call({
      tool: 'Bash',
      command: 'curl "http://192.168.1.20:32400/status/sessions/terminate?sessionId=abc&reason=x"',
    })
    expect(refusal(answer)).toContain("stops someone's stream")
  })

  test('a Tautulli command that changes something is blocked', async ($, on) => {
    world(on, CONFIGURED)
    const answer = await $.tool.call({
      tool: 'Bash',
      command: 'curl "http://192.168.1.20:8181/api/v2?apikey=k&cmd=delete_history"',
    })
    expect(refusal(answer)).toContain('delete_history')
  })

  test('a Tautulli read runs', async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call({ tool: 'Bash', command: 'curl "http://192.168.1.20:8181/api/v2?apikey=k&cmd=get_activity"' })
    expect(ran).toEqual(['Bash'])
  })

  test('sending data is blocked, but cut -d elsewhere in a pipeline is not', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const sends = await $.tool.call({
      tool: 'Bash',
      command: 'curl -s -d "x=1" "http://192.168.1.20:32400/library/sections"',
    })
    expect(refusal(sends)).toContain('sends data')
    await $.tool.call({
      tool: 'Bash',
      command: 'curl -s "http://192.168.1.20:32400/identity" | cut -d\'"\' -f2',
    })
    expect(ran).toEqual(['Bash'])
  })

  test('running a Cinemetric script runs', async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call({
      tool: 'Bash',
      command: 'python3 /plugins/cinemetric/skills/library-report/scripts/library_report.py',
    })
    expect(ran).toEqual(['Bash'])
  })

  test('an unrelated command runs, write methods and all', async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call({ tool: 'Bash', command: 'git status' })
    await $.tool.call({ tool: 'Bash', command: 'curl -X POST https://example.com/api -d "a=1"' })
    expect(ran).toEqual(['Bash', 'Bash'])
  })

  test('a web fetch that marks something watched is blocked', async ($, on) => {
    world(on, CONFIGURED)
    const answer = await $.tool.call({
      tool: 'WebFetch',
      url: 'http://192.168.1.20:32400/:/scrobble?key=1&identifier=com.plexapp.plugins.library',
      prompt: 'x',
    })
    expect(refusal(answer)).toContain('marks something as watched')
  })
})

describe('where the addresses come from', () => {
  test('without a settings file, address-free signs still count', async ($, on) => {
    world(on)
    const answer = await $.tool.call({
      tool: 'Bash',
      command: `curl -X DELETE "https://10.9.8.7/library/metadata/1?X-Plex-Token=${TOKEN}"`,
    })
    expect(refusal(answer)).toContain('Cinemetric read-only guard')
  })

  test('a damaged settings file is not an error', async ($, on) => {
    const ran = world(on, '{not json')
    await $.tool.call({ tool: 'Bash', command: 'ls' })
    const answer = await $.tool.call({
      tool: 'Bash',
      command: 'curl -X DELETE "https://plex.tv/api/servers/1/shared_servers/2"',
    })
    expect(ran).toEqual(['Bash'])
    expect(refusal(answer)).toContain('uses the DELETE method')
  })

  test('an address set in the environment counts', async ($, on) => {
    world(on, undefined, { PLEX_URL: 'https://media.example.net' })
    const answer = await $.tool.call({
      tool: 'Bash',
      command: 'curl -X DELETE "https://media.example.net/library/metadata/1"',
    })
    expect(refusal(answer)).toContain('Cinemetric read-only guard')
  })

  test('a lookalike address does not count', async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call({ tool: 'Bash', command: 'curl -X DELETE "http://192.168.1.200/x"' })
    expect(ran).toEqual(['Bash'])
  })
})

describe('switching the guard off', () => {
  test('editing a Claude Code settings file to switch it off is blocked', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const edit = await $.tool.call({
      tool: 'Edit',
      file_path: '/home/u/.claude/settings.json',
      old_string: '"read_only_guard": true',
      new_string: '"read_only_guard": false',
    })
    expect(refusal(edit)).toContain('only the user can switch the guard off')
    const shell = await $.tool.call({
      tool: 'Bash',
      command: `jq '.pluginConfigs.cinemetric.options.read_only_guard=false' .claude/settings.local.json > x`,
    })
    expect(refusal(shell)).toContain('only the user can switch the guard off')
    expect(ran).toEqual([])
  })

  test('other files that mention the setting, and other settings changes, go ahead', async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call({ tool: 'Write', file_path: '/work/app/src/config.py', content: 'read_only_guard = True' })
    await $.tool.call({
      tool: 'Edit',
      file_path: '/work/cinemetric/plugins/cinemetric/hooks/guard.ts',
      old_string: 'read_only_guard',
      new_string: 'read_only_guard',
    })
    await $.tool.call({
      tool: 'Write',
      file_path: '/work/app/.claude/settings.json',
      content: '{"permissions": {"allow": ["Bash(ls)"]}}',
    })
    expect(ran).toEqual(['Write', 'Edit', 'Write'])
  })

  test('another plugin cannot switch it off through the settings menu', async ($, on) => {
    world(on, CONFIGURED)
    on('config.set', ($, e) => ({ value: e.value }))
    const answer = await $.config.set({
      key: 'cinemetric.read_only_guard',
      value: false,
      previous: true,
      provider: { plugin: 'cinemetric', tier: 'user' },
      origin: { kind: 'plugin', name: 'someone-else' },
    })
    expect(answer.deny).toContain('only the user can switch the guard off')
  })
})

describe("the guard's own command", () => {
  for (const name of ['cinemetric', 'cinemetric@cinemetric', 'cinemetric@inline']) {
    test(`a change from this plugin (${name}) goes through`, async ($, on) => {
      world(on, CONFIGURED)
      on('config.set', ($, e) => ({ value: e.value }))
      const answer = await $.config.set({
        key: 'cinemetric.read_only_guard',
        value: false,
        previous: true,
        provider: { plugin: 'cinemetric', tier: 'user' },
        origin: { kind: 'plugin', name },
      })
      expect(answer.deny).toBeUndefined()
    })
  }
})

describe('the switch', () => {
  test('the guard is on by default', async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call({ tool: 'Bash', command: 'curl -X DELETE "http://192.168.1.20:32400/library/metadata/1"' })
    expect(ran).toEqual([])
  })

  test('switched off, nothing is checked', { options: { read_only_guard: false } }, async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call({ tool: 'Bash', command: 'curl -X DELETE "http://192.168.1.20:32400/library/metadata/1"' })
    expect(ran).toEqual(['Bash'])
  })
})

describe('when the guard itself fails', () => {
  test('the call runs and the user is told', async ($, on) => {
    const toasts: string[] = []
    const ran: string[] = []
    on('env.get', () => {
      throw new Error('broken')
    })
    on('ui.toast', ($, e) => {
      toasts.push(e.text)
      return { value: undefined }
    })
    on('tool.call', ($, e) => {
      ran.push(e.tool)
      return { result: {} as never }
    })
    await $.tool.call({ tool: 'Bash', command: 'curl -X DELETE "http://192.168.1.20:32400/x"' })
    expect(ran).toEqual(['Bash'])
    expect(toasts.join(' ')).toContain("couldn't check")
  })
})
