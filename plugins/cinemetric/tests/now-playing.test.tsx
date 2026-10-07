// Now Playing, run through Claude Code's own engine with
// `claude plugin test plugins/cinemetric`. The scenarios are in
// openspec/specs/now-playing-pane/spec.md.

import { describe, expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On, ProcessRunResult } from 'claude-code'

import {
  CHECKING,
  NO_PYTHON,
  NOTHING_PLAYING,
  NO_PANEL_REPLY,
  OFF_REPLY,
  OPEN_REPLY,
  PANE_ID,
  SCRIPT,
  TOO_SLOW,
  UNREADABLE,
  paneLines,
  parseResult,
  scriptError,
  streamRow,
  summaryLine,
  type Result,
} from '../hooks/now-playing-rules'

const ON = { options: { now_playing_pane: true } }
// 9:41 PM local time, so the clock text never depends on the time zone.
const CHECKED_AT = new Date(2026, 9, 6, 21, 41).getTime() / 1000

type RawStream = Record<string, unknown>

const EPISODE: RawStream = {
  user: 'alex',
  title: 'The Bear S03E04',
  player: 'Living Room TV',
  state: 'playing',
  live_tv: false,
  progress_pct: 42,
  method: 'direct play',
}
const MOVIE: RawStream = {
  user: 'sam',
  title: 'Dune: Part Two (2024)',
  player: 'iPhone',
  state: 'paused',
  live_tv: false,
  progress_pct: 10,
  method: 'transcode',
  transcode: { video: 'transcode', audio: 'copy' },
}

function output(streams: RawStream[], transcode = 0, bandwidth = 0): string {
  return JSON.stringify({
    cinemetric_version: 'x',
    checked_at: CHECKED_AT,
    live_activity: { streams, totals: { streams: streams.length, transcode, bandwidth_kbps: bandwidth } },
  })
}

function parsed(streams: RawStream[], transcode = 0, bandwidth = 0): Result {
  const result = parseResult(output(streams, transcode, bandwidth))
  if (!result) throw new Error('fixture did not parse')
  return result
}

const ran = (stdout: string, exitCode = 0, stderr = ''): ProcessRunResult => ({
  exitCode,
  stdout,
  stderr,
  isStdoutTruncated: false,
  isStderrTruncated: false,
})

// Stands in for Claude Code and the computer beneath the plugin: a clock, the
// panel, and Python running the script. `answer` decides each run's result;
// throwing means the program couldn't start. Returns what was run and the
// panels opened and closed.
function world(
  on: On,
  answer: (argv: readonly string[]) => ProcessRunResult = () => ran(output([])),
  canDrawPanels = true,
) {
  const runs: (readonly string[])[] = []
  const open = new Set<string>()
  const clock = mock.clock(on, { now: CHECKED_AT * 1000 })
  mock.env(on, { HOME: '/home/u' })
  on('process.run', ($, e) => {
    runs.push(e.argv)
    try {
      return { value: answer(e.argv) }
    } catch {
      return { deny: 'could not start' }
    }
  })
  on('ui.open', ($, e) => {
    open.add(e.id)
    if (!canDrawPanels) {
      return { value: { isPlaced: false as const, reason: 'the attached surfaces place no panes' } }
    }
    return { value: { isPlaced: true as const } }
  })
  on('ui.close', ($, e) => {
    open.delete(e.id)
    return { value: undefined }
  })
  on('ui.panes', () => ({
    value: [...open].map(id => ({ id, title: 'x', isShown: true, isFocused: false, isPlaced: true })),
  }))
  on('ui.invalidate', () => ({ value: undefined }))
  on('ui.status', () => ({ value: undefined }))
  on('fs.list', () => ({ deny: 'no such folder' }))
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('ui.render', ($, e) => {
    const { Box } = $.ui.resolve(e)
    return <Box />
  })
  return { runs, open, clock }
}

function startSession($: Engine) {
  return $.session.start({ cwd: '/work', surface: 'terminal', isInteractive: true })
}

// Types /cinemetric-now, then lets the check it started finish.
async function nowCommand($: Engine, clock: { settle: () => Promise<void> }) {
  const reply = await $.command.run({
    command: 'cinemetric-now',
    args: '',
    origin: { kind: 'composer' },
    presentation: { isFullscreen: true, columns: 120 },
  })
  await clock.settle()
  return reply
}

// The panel's lines as drawn.
async function pane($: Engine, columns = 100, rows = 20): Promise<string[]> {
  const ui = await $.ui.mount({
    plugin: 'cinemetric',
    surface: 'terminal',
    component: 'Pane',
    requestId: PANE_ID,
    props: {
      title: 'Now Playing',
      isFocused: false,
      bodyColumns: columns,
      placement: 'dock',
      scroll: { offset: 0, bodyRows: rows },
      view: {},
    },
  })
  const lines = (await ui.findAll({ type: 'Text' })).map(found => found.text)
  await ui.unmount()
  return lines
}

describe('what the panel shows', () => {
  test('two streams', () => {
    const result = parsed([EPISODE, MOVIE], 1, 24_100)
    expect(summaryLine(result)).toBe('2 streams · 1 transcoding · 24.1 Mbps · updated 9:41 PM')
    expect(streamRow(result.streams[0]!, 100)).toBe(
      'alex · The Bear S03E04 · Living Room TV · playing 42% · direct play',
    )
    expect(streamRow(result.streams[1]!, 100)).toBe(
      'sam · Dune: Part Two (2024) · iPhone · paused 10% · transcode (video)',
    )
  })

  test('video and audio, direct stream, and Live TV', () => {
    const both = parsed([{ ...MOVIE, transcode: { video: 'transcode', audio: 'transcode' } }])
    expect(streamRow(both.streams[0]!, 100)).toContain('transcode (video and audio)')
    const direct = parsed([{ ...EPISODE, method: 'direct stream' }])
    expect(streamRow(direct.streams[0]!, 100)).toContain('playing 42% · direct stream')
    const live = parsed([{ ...EPISODE, live_tv: true, progress_pct: null }])
    expect(streamRow(live.streams[0]!, 100)).toContain('playing Live TV · direct play')
  })

  test('one stream says stream', () => {
    expect(summaryLine(parsed([EPISODE], 0, 8000))).toBe('1 stream · 0 transcoding · 8.0 Mbps · updated 9:41 PM')
  })

  test('nobody watching', () => {
    expect(paneLines(parsed([]), undefined, 100, 20)).toEqual(['updated 9:41 PM', NOTHING_PLAYING])
  })

  test('before the first check', () => {
    expect(paneLines(undefined, undefined, 100, 20)).toEqual([CHECKING])
  })

  test('a long title is cut short, not wrapped', () => {
    const long = parsed([{ ...EPISODE, title: 'A Very Long Show Title That Goes On And On S01E01' }])
    const row = streamRow(long.streams[0]!, 60)
    expect(row.length).toBeLessThanOrEqual(60)
    expect(row).toContain('…')
    expect(row.endsWith('playing 42% · direct play')).toBe(true)
  })

  test('more streams than rows', () => {
    const many = parsed([EPISODE, MOVIE, EPISODE, MOVIE, EPISODE])
    const lines = paneLines(many, undefined, 100, 4)
    expect(lines.length).toBe(4)
    expect(lines[3]).toBe('and 3 more')
  })

  test('text from the server is drawn on one line', () => {
    const sneaky = parsed([{ ...EPISODE, title: 'Line one\nline two\u001b[31m' }])
    expect(streamRow(sneaky.streams[0]!, 100)).not.toMatch(/[\n\u001b]/)
  })
})

describe('when a check fails', () => {
  test("the script's own message, first line only", () => {
    expect(
      scriptError(
        'error: NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet. Run the cinemetric:setup skill.\nmore',
      ),
    ).toBe('Cinemetric is not connected to a Plex server yet. Run the cinemetric:setup skill.')
  })

  test('long messages are cut to 200 characters', () => {
    expect(scriptError(`error: ${'x'.repeat(500)}`).length).toBe(200)
  })

  test('output that is not what the script prints', () => {
    expect(parseResult('not json')).toBeUndefined()
    expect(parseResult('{"live_activity": {}}')).toBeUndefined()
  })

  test('the last good result stays, with a line saying the check failed', () => {
    const lines = paneLines(parsed([EPISODE]), TOO_SLOW, 100, 20)
    expect(lines[1]).toBe(`Last check failed: ${TOO_SLOW}`)
    expect(lines[2]).toContain('alex')
  })
})

describe('in a session', () => {
  test('fresh install: the command says how to switch it on and runs nothing', async ($, on) => {
    const { runs, open, clock } = world(on)
    await startSession($)
    expect((await nowCommand($, clock)).text).toBe(OFF_REPLY)
    expect(runs).toEqual([])
    expect(open.size).toBe(0)
  })

  test('switched on: the command opens the panel and checks once', ON, async ($, on) => {
    const { runs, open, clock } = world(on, () => ran(output([EPISODE, MOVIE], 1, 24_100)))
    await startSession($)
    expect(runs).toEqual([])
    expect((await nowCommand($, clock)).text).toBe(OPEN_REPLY)
    expect(open.has(PANE_ID)).toBe(true)
    expect(runs.length).toBe(1)
    const [python, script, flag] = runs[0]!
    expect(python).toBe('python3')
    expect(script!.endsWith(`/${SCRIPT}`)).toBe(true)
    expect(flag).toBe('--now-playing')
    const lines = await pane($)
    expect(lines[0]).toBe('2 streams · 1 transcoding · 24.1 Mbps · updated 9:41 PM')
    expect(lines[1]).toBe('alex · The Bear S03E04 · Living Room TV · playing 42% · direct play')
  })

  test("an app that can't draw panels: nothing stays open and nothing is checked", ON, async ($, on) => {
    const { runs, open, clock } = world(on, () => ran(output([EPISODE])), false)
    await startSession($)
    expect((await nowCommand($, clock)).text).toBe(NO_PANEL_REPLY)
    expect(open.has(PANE_ID)).toBe(false)
    await clock.advance(120_000)
    expect(runs).toEqual([])
  })

  test('the reply never carries stream details', ON, async ($, on) => {
    const { clock } = world(on, () => ran(output([EPISODE])))
    await startSession($)
    const reply = await nowCommand($, clock)
    expect(JSON.stringify(reply)).not.toContain('alex')
    expect(JSON.stringify(reply)).not.toContain('The Bear')
  })

  test('open for two minutes: one check on opening and one every 30 seconds', ON, async ($, on) => {
    const { runs, clock } = world(on)
    await startSession($)
    await nowCommand($, clock)
    await clock.advance(120_000)
    expect(runs.length).toBe(5)
  })

  test('typed again while open: still one set of checks', ON, async ($, on) => {
    const { runs, clock } = world(on)
    await startSession($)
    await nowCommand($, clock)
    await nowCommand($, clock)
    await clock.advance(30_000)
    expect(runs.length).toBe(2)
  })

  // A reload runs session start again, which closes the panel through the
  // same ui.close event a person's close raises.
  test('closing the panel stops the checks', ON, async ($, on) => {
    const { runs, open, clock } = world(on)
    await startSession($)
    await nowCommand($, clock)
    await startSession($)
    expect(open.has(PANE_ID)).toBe(false)
    await clock.advance(120_000)
    expect(runs.length).toBe(1)
  })

  test('a panel left open by a reload is closed at session start', ON, async ($, on) => {
    const { open } = world(on)
    open.add(PANE_ID)
    await startSession($)
    expect(open.has(PANE_ID)).toBe(false)
  })

  test('falls back to python when python3 is missing', ON, async ($, on) => {
    const { runs, clock } = world(on, argv => {
      if (argv[0] === 'python3') throw new Error('not found')
      return ran(output([]))
    })
    await startSession($)
    await nowCommand($, clock)
    expect(runs.map(argv => argv[0])).toEqual(['python3', 'python'])
    expect(await pane($)).toEqual(['updated 9:41 PM', NOTHING_PLAYING])
  })

  test('no Python at all', ON, async ($, on) => {
    const { clock } = world(on, () => {
      throw new Error('not found')
    })
    await startSession($)
    await nowCommand($, clock)
    expect(await pane($)).toEqual([`Last check failed: ${NO_PYTHON}`])
  })

  test('not set up: the script says so', ON, async ($, on) => {
    const { clock } = world(on, () => ran('', 1, 'error: NOT_CONFIGURED: Cinemetric is not connected to a Plex server yet.'))
    await startSession($)
    await nowCommand($, clock)
    expect(await pane($)).toEqual(['Last check failed: Cinemetric is not connected to a Plex server yet.'])
  })

  test('output the mod can not read', ON, async ($, on) => {
    const { clock } = world(on, () => ran('garbage'))
    await startSession($)
    await nowCommand($, clock)
    expect(await pane($)).toEqual([`Last check failed: ${UNREADABLE}`])
  })

  test('one failed check keeps the earlier streams', ON, async ($, on) => {
    let fail = false
    const { clock } = world(on, () => (fail ? ran('', 1, 'error: Could not reach the Plex server.') : ran(output([EPISODE]))))
    await startSession($)
    await nowCommand($, clock)
    fail = true
    await clock.advance(30_000)
    const lines = await pane($)
    expect(lines[1]).toBe('Last check failed: Could not reach the Plex server.')
    expect(lines[2]).toContain('alex')
  })
})
