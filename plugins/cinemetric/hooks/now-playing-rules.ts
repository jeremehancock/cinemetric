// Now Playing's rules, as plain functions. Nothing here touches Claude Code,
// so they can be read and tested on their own. The rules are written down in
// openspec/specs/now-playing-pane/spec.md.

// The setting that switches Now Playing on and off (plugin.json's userConfig).
export const NOW_SETTING = 'now_playing_pane'

export const NOW_COMMAND = 'cinemetric-now'
// How the command is listed. It's added at session start whether the mod is
// on or off, so typing it while off says how to switch it on.
export const NOW_COMMAND_SPEC = {
  name: NOW_COMMAND,
  description: "Show who's streaming from Plex right now, updated while it's open",
}
export const PANE_ID = 'cinemetric-now'
export const PANE_TITLE = 'Now Playing'

// How often the panel checks while it's open, and how long one check may take.
export const CHECK_EVERY_MS = 30_000
export const CHECK_TIMEOUT_MS = 20_000

export const OFF_REPLY = 'Now Playing is off. Type /cinemetric-mods now on to switch it on.'
export const OPEN_REPLY = "Now Playing is open. It checks Plex about every 30 seconds while it's open."

export const CHECKING = 'Checking Plex...'
export const NOTHING_PLAYING = 'Nothing is playing right now.'

export const NO_PYTHON = "Couldn't start Python. Now Playing needs Python 3.8 or newer."
export const TOO_SLOW = 'Plex took too long to answer.'
export const UNREADABLE = "Couldn't read Plex's answer."

// The server-health script, from the plugin's folder.
export const SCRIPT = 'skills/server-health/scripts/server_health.py'

export type Stream = {
  user: string
  title: string
  device: string
  state: string
  progressPct: number | null
  isLive: boolean
  method: string
  transcoded: string
}

export type Result = {
  checkedAt: number
  streams: Stream[]
  transcoding: number
  bandwidthKbps: number
}

// Text from the server, made safe to draw on one line: no control
// characters, no line breaks.
function plain(value: unknown): string {
  if (typeof value !== 'string') return ''
  return value.replace(/[\u0000-\u001f\u007f-\u009f]+/g, ' ').trim()
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0
}

function transcodedPart(transcode: unknown): string {
  if (typeof transcode !== 'object' || transcode === null) return ''
  const { video, audio } = transcode as { video?: unknown; audio?: unknown }
  const parts = [video === 'transcode' && 'video', audio === 'transcode' && 'audio'].filter(Boolean)
  return parts.join(' and ')
}

function streamOf(raw: unknown): Stream | undefined {
  if (typeof raw !== 'object' || raw === null) return undefined
  const s = raw as Record<string, unknown>
  const pct = s.progress_pct
  return {
    user: plain(s.user) || 'Someone',
    title: plain(s.title) || 'Something',
    device: plain(s.player) || plain(s.platform),
    state: s.state === 'playing' || s.state === 'paused' || s.state === 'buffering' ? s.state : '',
    progressPct: typeof pct === 'number' && Number.isFinite(pct) ? Math.max(0, Math.min(100, Math.round(pct))) : null,
    isLive: s.live_tv === true,
    method: s.method === 'direct play' || s.method === 'direct stream' || s.method === 'transcode' ? s.method : '',
    transcoded: s.method === 'transcode' ? transcodedPart(s.transcode) : '',
  }
}

// The script's `--now-playing` output, or undefined when it isn't what the
// script prints.
export function parseResult(stdout: string): Result | undefined {
  let data: unknown
  try {
    data = JSON.parse(stdout)
  } catch {
    return undefined
  }
  if (typeof data !== 'object' || data === null) return undefined
  const { checked_at: checkedAt, live_activity: live } = data as Record<string, unknown>
  if (typeof checkedAt !== 'number' || typeof live !== 'object' || live === null) return undefined
  const { streams, totals } = live as { streams?: unknown; totals?: unknown }
  if (!Array.isArray(streams)) return undefined
  const sums = (typeof totals === 'object' && totals !== null ? totals : {}) as Record<string, unknown>
  const parsed = streams.map(streamOf).filter((s): s is Stream => s !== undefined)
  return {
    checkedAt,
    streams: parsed,
    transcoding: count(sums.transcode),
    bandwidthKbps: count(sums.bandwidth_kbps),
  }
}

// What the script said went wrong: its first line, without the `error:` and
// any SHOUTED_CODE: in front, at most 200 characters.
export function scriptError(stderr: string): string {
  const first = plain(stderr.split(/\r?\n/).find(line => line.trim() !== '') ?? '')
  const message = first.replace(/^error:\s*/i, '').replace(/^[A-Z][A-Z_]+:\s*/, '')
  if (!message) return UNREADABLE
  return message.length > 200 ? `${message.slice(0, 199)}…` : message
}

// The local time of a check, as `9:41 PM`.
export function clockTime(epochSeconds: number): string {
  const when = new Date(epochSeconds * 1000)
  const hours = when.getHours()
  const minutes = String(when.getMinutes()).padStart(2, '0')
  return `${hours % 12 || 12}:${minutes} ${hours < 12 ? 'AM' : 'PM'}`
}

// The line at the top: `3 streams · 1 transcoding · 24.1 Mbps · updated 9:41 PM`,
// or just the time when nobody is streaming.
export function summaryLine(result: Result): string {
  const updated = `updated ${clockTime(result.checkedAt)}`
  const n = result.streams.length
  if (n === 0) return updated
  const streams = `${n} ${n === 1 ? 'stream' : 'streams'}`
  const mbps = `${(result.bandwidthKbps / 1000).toFixed(1)} Mbps`
  return [streams, `${result.transcoding} transcoding`, mbps, updated].join(' · ')
}

function cut(text: string, room: number): string {
  if (text.length <= room) return text
  return room <= 1 ? '…' : `${text.slice(0, room - 1)}…`
}

// One stream's row, at most `columns` wide: the title gives way first.
export function streamRow(stream: Stream, columns: number): string {
  const where = stream.isLive ? 'Live TV' : stream.progressPct === null ? '' : `${stream.progressPct}%`
  const how = [stream.state, where].filter(Boolean).join(' ')
  const method = stream.transcoded ? `${stream.method} (${stream.transcoded})` : stream.method
  const before = [stream.user]
  const after = [stream.device, how, method].filter(Boolean)
  // Everything but the title, and the one separator the title adds.
  const fixed = [...before, ...after].join(' · ').length + ' · '.length
  const title = cut(stream.title, Math.max(8, columns - fixed))
  return cut([...before, title, ...after].join(' · '), Math.max(1, columns))
}

// Every line of the panel, top to bottom, fitted to its rows and columns.
export function paneLines(
  result: Result | undefined,
  error: string | undefined,
  columns: number,
  rows: number,
): string[] {
  const lines: string[] = []
  if (result === undefined && error === undefined) return [CHECKING]
  if (result !== undefined) lines.push(cut(summaryLine(result), columns))
  if (error !== undefined) lines.push(cut(`Last check failed: ${error}`, columns))
  if (result === undefined) return lines
  if (result.streams.length === 0) return [...lines, NOTHING_PLAYING]

  const room = Math.max(1, rows - lines.length)
  const shown = result.streams.length <= room ? result.streams : result.streams.slice(0, room - 1)
  lines.push(...shown.map(stream => streamRow(stream, columns)))
  const more = result.streams.length - shown.length
  if (more > 0) lines.push(`and ${more} more`)
  return lines
}
