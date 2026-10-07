// The library status line: one dim row above the prompt saying how big the
// Plex library is and when Cinemetric last checked it, from the newest
// snapshot on this computer. It never contacts the server. It's drawn as its
// own row rather than through $.ui.status, which Claude Code shows with a
// notice icon that made it look like a warning.
// See openspec/specs/library-status-line/spec.md.

import type { EngineInterface, On } from 'claude-code'

import { COMMAND_SPEC } from './command'
import { NOW_COMMAND_SPEC, PANE_ID as NOW_PANE_ID } from './now-playing-rules'

import {
  NO_SNAPSHOT,
  SERVER_FOLDER,
  SNAPSHOT_FILE,
  libraryParts,
  localDate,
  statusLine,
} from './status-line-rules'

type Newest = { path: string; date: string; mtimeMs: number }

// The newest snapshot file read so far and what it held, so a file is read
// again only when a newer one appears or it changes.
let remembered: { newest: Newest; parts: string[] | undefined } | undefined

// The row's text. A reload starts it empty, and session.start fills it again.
let shownLine: string | undefined

// Cinemetric's data folder, the same way the Python scripts find it.
async function dataFolder($: EngineInterface): Promise<string | undefined> {
  const override = await $.env.get('CINEMETRIC_DATA_DIR')
  if (override) return override
  if ((await $.env.get('OS')) === 'Windows_NT') {
    const local = await $.env.get('LOCALAPPDATA')
    const home = await $.env.get('USERPROFILE')
    if (local) return `${local}/cinemetric`
    return home ? `${home}/AppData/Local/cinemetric` : undefined
  }
  const xdg = await $.env.get('XDG_DATA_HOME')
  if (xdg) return `${xdg}/cinemetric`
  const home = await $.env.get('HOME')
  return home ? `${home}/.local/share/cinemetric` : undefined
}

async function listOrNothing($: EngineInterface, path: string) {
  try {
    return await $.fs.list(path)
  } catch {
    return []
  }
}

// The snapshot file with the newest date, across every server's folder.
async function newestSnapshot($: EngineInterface): Promise<Newest | undefined> {
  const data = await dataFolder($)
  if (!data) return undefined
  const folder = `${data}/snapshots`
  let newest: { path: string; date: string } | undefined
  for (const server of await listOrNothing($, folder)) {
    if (server.kind !== 'dir' || !SERVER_FOLDER.test(server.name)) continue
    for (const file of await listOrNothing($, `${folder}/${server.name}`)) {
      const date = SNAPSHOT_FILE.exec(file.name)?.[1]
      if (file.kind !== 'file' || !date) continue
      if (!newest || date > newest.date) newest = { path: `${folder}/${server.name}/${file.name}`, date }
    }
  }
  if (!newest) return undefined
  try {
    return { ...newest, mtimeMs: (await $.fs.stat(newest.path)).mtimeMs }
  } catch {
    return { ...newest, mtimeMs: 0 }
  }
}

async function partsOf($: EngineInterface, newest: Newest): Promise<string[] | undefined> {
  const same = remembered?.newest
  if (same && same.path === newest.path && same.mtimeMs === newest.mtimeMs) return remembered?.parts
  let parts: string[] | undefined
  try {
    const text = await $.fs.read(newest.path)
    parts = typeof text === 'string' ? libraryParts(text) : undefined
  } catch {
    parts = undefined
  }
  remembered = { newest, parts }
  return parts
}

async function buildLine($: EngineInterface): Promise<string> {
  const newest = await newestSnapshot($)
  if (!newest) return NO_SNAPSHOT
  const today = localDate(new Date(await $.clock.now()))
  return statusLine(newest.date, today, await partsOf($, newest))
}

// Rebuilds the row's text, and asks for a redraw when it changed.
async function showStatus($: EngineInterface): Promise<void> {
  const line = await buildLine($)
  if (line === shownLine) return
  shownLine = line
  $.ui.invalidate('ui.render')
}

// The module's one session.start hook lives here, since it needs this file's
// helpers. It also adds the /cinemetric-mods and /cinemetric-now commands,
// whatever the switches. It runs again after every reload (any switch
// change), which ends Now Playing's checks, so it closes that panel too:
// typing /cinemetric-now opens it again.
export function setUpStatusLine(on: On, isOn: boolean): void {
  on('session.start', async ($, e, next) => {
    await $.command.register(COMMAND_SPEC)
    await $.command.register(NOW_COMMAND_SPEC)
    try {
      if ((await $.ui.panes()).some(pane => pane.id === NOW_PANE_ID)) await $.ui.close({ id: NOW_PANE_ID })
    } catch {
      // Nothing to close, or it couldn't be: the rest of the start goes on.
    }
    // Clears a status entry an earlier version of this mod may have pinned.
    $.ui.status(undefined)
    if (!isOn) return next(e)
    try {
      await showStatus($)
    } catch {
      // The line is only a convenience: a problem building it shows nothing.
    }
    return next(e)
  })

  if (!isOn) return
  // After each turn, so a snapshot a skill just saved shows straight away.
  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    await showStatus($)
    return done
  }).catch(($, e, next) => next(e))

  // The row above the prompt. Nothing is drawn while a survey is showing
  // there, or before the text is ready.
  on('ui.render', { component: 'AbovePrompt' }, ($, e, next) => {
    if (shownLine === undefined || e.props.hasSurvey) return next(e)
    const { Text } = $.ui.resolve(e)
    return (
      <Text dimColor wrap="truncate-end">
        {shownLine}
      </Text>
    )
  })
}
