// The read-only guard, run through Claude Code's own engine with
// `claude plugin test plugins/cinemetric`. Every scenario in
// openspec/specs/read-only-guard/spec.md has a test here, plus the
// settings-file rule from openspec/specs/mods/spec.md.

import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const SETTINGS = '/home/u/.config/cinemetric/config.json'
const TOKEN = 'secret-token-123'

// Stands in for the world beneath the plugin: a home folder, and a settings
// file when one is given. Tool calls that get past the guard are recorded,
// and answered with `answer` when one is given.
function world(
  on: On,
  settings?: string,
  environment: Record<string, string> = {},
  answer?: (tool: string) => object,
) {
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
    return (answer?.(e.tool) ?? { result: {} }) as never
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

const DELETE_ONE = 'curl -X DELETE "http://192.168.1.20:32400/library/metadata/1"'

describe('commands that only handle text', () => {
  const textOnly: [string, string][] = [
    ['opening a pull request that talks about the server',
      'gh pr create --title "Guard" --body "Blocks curl -X DELETE to plex.tv and :32400"'],
    ['a commit message written with a here-document',
      `git commit -m "$(cat <<'EOF'\nStop ${DELETE_ONE} (it doesn't ask)\n\nMore text\nEOF\n)"`],
    ['writing notes to a file',
      "cat > notes.md <<'EOF'\nThe scan is 192.168.1.20:32400/library/sections/1/refresh\nEOF"],
    ['searching code', 'grep -rn "X-Plex-Token" src | grep POST'],
    ['a commit after other git steps',
      'cd /work && git add -A && GIT_EDITOR=true git commit -m "POST to :32400" 2>&1 | tail -5'],
  ]
  for (const [name, command] of textOnly) {
    test(`${name} runs`, async ($, on) => {
      const ran = world(on, CONFIGURED)
      const answer = await $.tool.call({ tool: 'Bash', command })
      expect(refusal(answer)).toBeUndefined()
      expect(ran).toEqual(['Bash'])
    })
  }

  const stillChecked: [string, string][] = [
    ['text piped into a shell', `echo '${DELETE_ONE}' | sh`],
    ['a request hidden in a command substitution', `echo "$(${DELETE_ONE})"`],
    ['a request in backticks', `echo \`${DELETE_ONE}\``],
    ['a request inside an unquoted here-document', `cat <<EOF\n$(${DELETE_ONE})\nEOF`],
    ['a request in a process substitution', `tee >(${DELETE_ONE}) < notes.md`],
    ['a text program next to a request', `echo start; ${DELETE_ONE}`],
    ['git told to run something', `git -c alias.x='!${DELETE_ONE}' x`],
    ['an unclosed quote', `echo "${DELETE_ONE}`],
    ['a ${...} the guard does not read', 'echo ${x:-curl -X DELETE http://192.168.1.20:32400/x}'],
    ['a subshell', `(echo hi; ${DELETE_ONE})`],
    ['a program written with a path', '/usr/bin/curl -X DELETE http://192.168.1.20:32400/x'],
    ['a request through /dev/tcp',
      'echo "DELETE /library/metadata/1 HTTP/1.1" > /dev/tcp/192.168.1.20/32400 # :32400'],
  ]
  for (const [name, command] of stillChecked) {
    test(`${name} is blocked`, async ($, on) => {
      const ran = world(on, CONFIGURED)
      const answer = await $.tool.call({ tool: 'Bash', command })
      expect(refusal(answer)).toContain('Cinemetric read-only guard')
      expect(ran).toEqual([])
    })
  }
})

// PowerShell, which Claude Code uses on Windows, isn't in the tool types on
// every computer, so its calls are built here.
function powerShell(command: string) {
  return { tool: 'PowerShell', command } as never
}

describe('PowerShell commands', () => {
  test('a delete with Invoke-RestMethod is blocked', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call(
      powerShell('Invoke-RestMethod -Method Delete -Uri "http://192.168.1.20:32400/library/metadata/123"'),
    )
    expect(refusal(answer)).toContain('Cinemetric read-only guard')
    expect(refusal(answer)).toContain('uses the DELETE method')
    expect(ran).toEqual([])
  })

  test('a library scan with Invoke-WebRequest is blocked', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call(
      powerShell('Invoke-WebRequest "http://192.168.1.20:32400/library/sections/1/refresh"'),
    )
    expect(refusal(answer)).toContain('starts a library scan')
    expect(ran).toEqual([])
  })

  test('a delete through .NET HttpClient is blocked', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call(
      powerShell(
        '$c = [System.Net.Http.HttpClient]::new(); $c.DeleteAsync("http://192.168.1.20:32400/library/metadata/1").Result',
      ),
    )
    expect(refusal(answer)).toContain('uses the DELETE method')
    expect(ran).toEqual([])
  })

  test('an upload through .NET WebClient is blocked', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call(
      powerShell('(New-Object Net.WebClient).UploadString("http://192.168.1.20:32400/:/prefs", "x=1")'),
    )
    expect(refusal(answer)).toContain('sends data to the server')
    expect(ran).toEqual([])
  })

  test('a read runs unchanged', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call(powerShell('Invoke-RestMethod "http://192.168.1.20:32400/identity"'))
    expect(refusal(answer)).toBeUndefined()
    expect(ran).toEqual(['PowerShell'])
  })

  test('an unrelated command runs unchanged', async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call(powerShell('Get-ChildItem'))
    await $.tool.call(powerShell('Invoke-RestMethod -Method Post https://example.com/api'))
    expect(ran).toEqual(['PowerShell', 'PowerShell'])
  })

  test('a commit that mentions the server and a write is checked in full', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call(powerShell('git commit -m "Blocks curl -X DELETE to :32400"'))
    expect(refusal(answer)).toContain('uses the DELETE method')
    expect(ran).toEqual([])
  })

  test('reading the settings file is refused', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call(powerShell('Get-Content $env:USERPROFILE\\.config\\cinemetric\\config.json'))
    expect(refusal(answer)).toContain('setup.py status')
    expect(ran).toEqual([])
  })

  test('switching the guard off through a settings file is refused', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call(
      powerShell(`Set-Content .claude\\settings.json '{"pluginConfigs": {"read_only_guard": false}}'`),
    )
    expect(refusal(answer)).toContain('only the user can switch the guard off')
    expect(ran).toEqual([])
  })

  test('the token can go to the server but nowhere else', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const toServer = await $.tool.call(
      powerShell(`Invoke-RestMethod "http://192.168.1.20:32400/identity?X-Plex-Token=${TOKEN}"`),
    )
    expect(refusal(toServer)).toBeUndefined()
    const elsewhere = await $.tool.call(powerShell(`Set-Content notes.txt "${TOKEN}"`))
    expect(refusal(elsewhere)).toContain('Plex token')
    expect(ran).toEqual(['PowerShell'])
  })

  test('switched off, nothing is checked', { options: { read_only_guard: false } }, async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call(powerShell('Invoke-RestMethod -Method Delete "http://192.168.1.20:32400/library/metadata/1"'))
    expect(ran).toEqual(['PowerShell'])
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

// The token and API key: openspec/specs/read-only-guard/spec.md, "Which
// secrets the guard protects" and the requirements after it.
const API_KEY = 'tautulli-secret'
const OTHER_TOKEN = 'environment-token-456'

function bashPrints(stdout: string) {
  return () => ({ result: { stdout, stderr: '', interrupted: false } })
}

describe('which secrets are protected', () => {
  test('the token and API key from the settings file', async ($, on) => {
    world(on, CONFIGURED, {}, bashPrints(`a=${TOKEN} b=${API_KEY}`))
    const answer = await $.tool.call({ tool: 'Bash', command: 'some-tool --show' })
    expect(JSON.stringify(answer.result)).not.toContain(TOKEN)
    expect(JSON.stringify(answer.result)).not.toContain(API_KEY)
  })

  test('PLEX_TOKEN and the settings file, when they differ', async ($, on) => {
    world(on, CONFIGURED, { PLEX_TOKEN: OTHER_TOKEN }, bashPrints(`${TOKEN} ${OTHER_TOKEN}`))
    const answer = await $.tool.call({ tool: 'Bash', command: 'some-tool --show' })
    expect(JSON.stringify(answer.result)).toContain(
      '[Plex token hidden by Cinemetric] [Plex token hidden by Cinemetric]',
    )
  })

  test('a new token after setup is protected without a restart', async ($, on) => {
    let settings = CONFIGURED
    let mtimeMs = 1
    mock.env(on, { HOME: '/home/u' })
    on('fs.stat', () => ({ value: { kind: 'file' as const, size: 1, mtimeMs, isLink: false } }))
    on('fs.read', () => ({ value: settings }))
    on('ui.toast', () => ({ value: undefined }))
    on('tool.call', bashPrints('new-token-789-abc') as never)
    await $.tool.call({ tool: 'Bash', command: 'some-tool' })
    settings = JSON.stringify({ plex_url: 'http://192.168.1.20:32400', plex_token: 'new-token-789-abc' })
    mtimeMs = 2
    const answer = await $.tool.call({ tool: 'Bash', command: 'some-tool' })
    expect(JSON.stringify(answer.result)).toContain('[Plex token hidden by Cinemetric]')
  })

  test('nothing set up: nothing is hidden or refused', async ($, on) => {
    const ran = world(on, undefined, {}, bashPrints('PATH=/usr/bin'))
    const answer = await $.tool.call({ tool: 'Bash', command: 'env' })
    expect(JSON.stringify(answer.result)).toContain('PATH=/usr/bin')
    expect(ran).toEqual(['Bash'])
  })

  test('a short placeholder value is ignored', async ($, on) => {
    const ran = world(on, JSON.stringify({ plex_token: 'x' }), {}, bashPrints('x marks the spot'))
    const answer = await $.tool.call({ tool: 'Write', file_path: '/work/notes.md', content: 'x' })
    expect(refusal(answer)).toBeUndefined()
    const shown = await $.tool.call({ tool: 'Bash', command: 'echo hi' })
    expect(JSON.stringify(shown.result)).toContain('x marks the spot')
    expect(ran).toEqual(['Write', 'Bash'])
  })
})

describe('hiding the secrets in what Claude sees', () => {
  test('printing the environment', async ($, on) => {
    world(on, CONFIGURED, { PLEX_TOKEN: TOKEN }, bashPrints(`HOME=/home/u\nPLEX_TOKEN=${TOKEN}\n`))
    const answer = await $.tool.call({ tool: 'Bash', command: 'env' })
    const stdout = (answer.result as { stdout: string }).stdout
    expect(stdout).toBe('HOME=/home/u\nPLEX_TOKEN=[Plex token hidden by Cinemetric]\n')
  })

  test('a roundabout read of the settings file', async ($, on) => {
    world(on, CONFIGURED, {}, bashPrints(CONFIGURED))
    const answer = await $.tool.call({
      tool: 'Bash',
      command: `python3 -c "print(open('/home/u/.conf' + 'ig/cinemetric/config.json').read())"`,
    })
    const stdout = (answer.result as { stdout: string }).stdout
    expect(stdout).toContain('[Plex token hidden by Cinemetric]')
    expect(stdout).toContain('[Tautulli API key hidden by Cinemetric]')
    expect(stdout).toContain('http://192.168.1.20:32400')
  })

  test('a log file read with the Read tool', async ($, on) => {
    world(on, CONFIGURED, {}, () => ({
      result: {
        type: 'text',
        file: {
          filePath: '/var/log/app.log',
          content: `GET /library?X-Plex-Token=${TOKEN} 200`,
          numLines: 1,
          startLine: 1,
          totalLines: 1,
        },
      },
    }))
    const answer = await $.tool.call({ tool: 'Read', file_path: '/var/log/app.log' })
    expect(JSON.stringify(answer.result)).toContain('X-Plex-Token=[Plex token hidden by Cinemetric] 200')
  })

  test('a tool that reports an error has its error text hidden too', async ($, on) => {
    world(on, CONFIGURED, {}, () => ({ isError: true, result: `failed for ${TOKEN}`, text: `failed for ${TOKEN}` }))
    const answer = await $.tool.call({ tool: 'Bash', command: 'some-tool' })
    expect(refusal(answer)).toBe('failed for [Plex token hidden by Cinemetric]')
  })

  test('ordinary output is unchanged', async ($, on) => {
    world(on, CONFIGURED, {}, bashPrints('On branch main\n'))
    const answer = await $.tool.call({ tool: 'Bash', command: 'git status' })
    expect(answer.result).toEqual({ stdout: 'On branch main\n', stderr: '', interrupted: false })
  })
})

describe('blocking reads of the settings file', () => {
  test('the Read tool on the settings file is refused', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call({ tool: 'Read', file_path: SETTINGS })
    expect(refusal(answer)).toContain("Cinemetric's settings file holds the user's Plex token")
    expect(refusal(answer)).toContain('setup.py status')
    expect(ran).toEqual([])
  })

  test('the settings file under XDG_CONFIG_HOME is refused too', async ($, on) => {
    const ran = world(on, undefined, { XDG_CONFIG_HOME: '/srv/conf' })
    const answer = await $.tool.call({ tool: 'Read', file_path: '/srv/conf/cinemetric/config.json' })
    expect(refusal(answer)).toContain("Cinemetric's settings file")
    const shell = await $.tool.call({ tool: 'Bash', command: 'cat "$XDG_CONFIG_HOME/cinemetric/config.json"' })
    expect(refusal(shell)).toContain("Cinemetric's settings file")
    expect(ran).toEqual([])
  })

  test('printing it from the shell is refused', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call({ tool: 'Bash', command: 'cat ~/.config/cinemetric/config.json' })
    expect(refusal(answer)).toContain("Cinemetric's settings file")
    const jq = await $.tool.call({ tool: 'Bash', command: 'ls -l ~/.config/cinemetric/config.json && jq . ~/.config/cinemetric/config.json' })
    expect(refusal(jq)).toContain("Cinemetric's settings file")
    expect(ran).toEqual([])
  })

  test("checking the file's details, and setup status, run", async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call({ tool: 'Bash', command: 'ls -l ~/.config/cinemetric/config.json' })
    await $.tool.call({ tool: 'Bash', command: 'stat /home/u/.config/cinemetric/config.json' })
    await $.tool.call({ tool: 'Bash', command: 'python3 /plugins/cinemetric/skills/setup/scripts/setup.py status' })
    await $.tool.call({ tool: 'Bash', command: 'grep -rn "cinemetric/config.json" plugins' })
    expect(ran).toEqual(['Bash', 'Bash', 'Bash', 'Bash'])
  })
})

describe('refusing to pass the secrets on', () => {
  test('filing an issue with the token is refused', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call({
      tool: 'Bash',
      command: `gh issue create --title "Broken" --body "my token is ${TOKEN}"`,
    })
    expect(refusal(answer)).toContain("it contains the user's Plex token")
    expect(refusal(answer)).not.toContain(TOKEN)
    expect(ran).toEqual([])
  })

  test('writing the API key into a file is refused', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call({ tool: 'Write', file_path: '/work/notes.md', content: `key: ${API_KEY}` })
    expect(refusal(answer)).toContain("it contains the user's Tautulli API key")
    expect(refusal(answer)).not.toContain(API_KEY)
    expect(ran).toEqual([])
  })

  test('publishing a page with the token through an MCP tool is refused', async ($, on) => {
    const ran = world(on, CONFIGURED)
    const answer = await $.tool.call({
      tool: 'mcp__docs__publish',
      page: { title: 'Notes', body: [`token ${TOKEN}`] },
    } as never)
    expect(refusal(answer)).toContain("it contains the user's Plex token")
    expect(ran).toEqual([])
  })

  test("a read from the user's own server with the token runs", async ($, on) => {
    const ran = world(on, CONFIGURED)
    await $.tool.call({
      tool: 'Bash',
      command: `curl -H "X-Plex-Token: ${TOKEN}" "http://192.168.1.20:32400/identity"`,
    })
    await $.tool.call({ tool: 'Bash', command: `curl "http://192.168.1.20:8181/api/v2?apikey=${API_KEY}&cmd=get_activity"` })
    await $.tool.call({ tool: 'WebFetch', url: `http://192.168.1.20:32400/identity?X-Plex-Token=${TOKEN}`, prompt: 'x' })
    expect(ran).toEqual(['Bash', 'Bash', 'WebFetch'])
  })

  test("a write to the user's own server with the token names the write", async ($, on) => {
    world(on, CONFIGURED)
    const answer = await $.tool.call({
      tool: 'Bash',
      command: `curl -X DELETE "http://192.168.1.20:32400/library/metadata/1?X-Plex-Token=${TOKEN}"`,
    })
    expect(refusal(answer)).toContain('uses the DELETE method')
  })
})

describe('when hiding fails', () => {
  test('the result comes back unchanged, the tool runs once, and the user is told', async ($, on) => {
    const toasts: string[] = []
    let runs = 0
    mock.env(on, { HOME: '/home/u' })
    on('fs.stat', () => ({ value: { kind: 'file' as const, size: 1, mtimeMs: 1, isLink: false } }))
    on('fs.read', () => ({ value: CONFIGURED }))
    on('ui.toast', ($, e) => {
      toasts.push(e.text)
      return { value: undefined }
    })
    // A result the guard can't turn into text (JSON has no big integers), so
    // looking through it throws.
    on('tool.call', () => {
      runs++
      return { result: { stdout: 'ok', size: 1n } } as never
    })
    const answer = await $.tool.call({ tool: 'Bash', command: 'some-tool' })
    expect(runs).toBe(1)
    expect((answer.result as { stdout: string }).stdout).toBe('ok')
    expect(toasts.join(' ')).toContain("couldn't check a tool's output")
    expect(toasts.join(' ')).not.toContain(TOKEN)
  })
})
