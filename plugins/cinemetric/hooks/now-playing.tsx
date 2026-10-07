// Now Playing: /cinemetric-now opens a panel listing who's streaming from Plex
// right now. While the panel is open it runs the server-health script with
// --now-playing about every 30 seconds; while it's closed it does nothing. The
// mod never reads the Plex token: the script does the talking to Plex. What
// the panel shows is drawn for the user only and never sent to Claude.
// See openspec/specs/now-playing-pane/spec.md.

import type { EngineInterface, On, Timer } from 'claude-code'

import {
  CHECK_EVERY_MS,
  CHECK_TIMEOUT_MS,
  NO_PANEL_REPLY,
  NO_PYTHON,
  NOW_COMMAND,
  OFF_REPLY,
  OPEN_REPLY,
  PANE_ID,
  PANE_TITLE,
  SCRIPT,
  TOO_SLOW,
  UNREADABLE,
  paneLines,
  parseResult,
  scriptError,
  type Result,
} from './now-playing-rules'

// The latest good result and the last check's problem, if it had one. A
// reload starts them empty, and the next check fills them again.
let latest: Result | undefined
let problem: string | undefined
let timer: Timer | undefined
let isChecking = false
// The Python that started last time, so later checks don't try python3 first
// on a computer that only has python.
let python: string | undefined

const PYTHONS = ['python3', 'python']

// Runs the script once and records what came of it.
async function check($: EngineInterface): Promise<void> {
  if (isChecking) return
  isChecking = true
  try {
    const outcome = await runScript($)
    if (typeof outcome === 'string') {
      problem = outcome
    } else {
      latest = outcome
      problem = undefined
    }
  } finally {
    isChecking = false
    $.ui.invalidate('ui.render')
  }
}

// The script's result, or a sentence saying why there isn't one.
async function runScript($: EngineInterface): Promise<Result | string> {
  const script = `${$.plugin.root}/${SCRIPT}`
  const tries = python ? [python] : PYTHONS
  for (const name of tries) {
    const startedAt = await $.clock.now()
    let ran
    try {
      ran = await $.process.run([name, script, '--now-playing'], { timeoutMs: CHECK_TIMEOUT_MS })
    } catch {
      // Either this Python couldn't start, or the check ran out of time.
      if ((await $.clock.now()) - startedAt >= CHECK_TIMEOUT_MS - 1000) return TOO_SLOW
      if (name === python) python = undefined
      continue
    }
    python = name
    if (ran.exitCode !== 0) return scriptError(ran.stderr)
    return parseResult(ran.stdout) ?? UNREADABLE
  }
  return NO_PYTHON
}

// Checks once now, then every 30 seconds until the panel closes. The command
// is listed, and a panel left open by a reload is closed, in status-line.tsx's
// session.start hook (a module has one).
function startChecks($: EngineInterface): void {
  if (timer) return
  void check($)
  timer = $.clock.every(CHECK_EVERY_MS, () => void check($))
}

function stopChecks(): void {
  timer?.cancel()
  timer = undefined
  latest = undefined
  problem = undefined
}

export function setUpNowPlaying(on: On, isOn: boolean): void {
  on('command.run', { command: NOW_COMMAND }, async $ => {
    if (!isOn) return { text: OFF_REPLY }
    const opened = await $.ui.open({ id: PANE_ID, title: PANE_TITLE })
    // An app that can't draw panels keeps the panel open but unseen, so
    // close it rather than check Plex for a panel nobody can see.
    if (!opened.isPlaced) {
      await $.ui.close({ id: PANE_ID })
      return { text: NO_PANEL_REPLY }
    }
    startChecks($)
    return { text: OPEN_REPLY }
  })

  if (!isOn) return

  on('ui.close', async ($, e, next) => {
    if (e.id === PANE_ID) stopChecks()
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE_ID }, ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const lines = paneLines(latest, problem, e.props.bodyColumns, e.props.scroll.bodyRows)
    return (
      <Box flexDirection="column">
        {lines.map((line, i) => (
          <Text dimColor={i === 0} wrap="truncate-end">
            {line}
          </Text>
        ))}
      </Box>
    )
  })
}
