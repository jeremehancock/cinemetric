// The library status line's rules, as plain functions. Nothing here touches
// Claude Code, so they can be read and tested on their own. The rules are
// written down in openspec/specs/library-status-line/spec.md.

// The setting that switches the status line on and off (plugin.json's userConfig).
export const STATUS_SETTING = 'library_status_line'

// The names the changes skill gives snapshot folders and files.
export const SERVER_FOLDER = /^[A-Za-z0-9]{1,128}$/
export const SNAPSHOT_FILE = /^(\d{4}-\d{2}-\d{2})\.json$/

export const NO_SNAPSHOT = 'Plex: no snapshot yet · ask Claude "what changed on Plex?"'

// The day count between two YYYY-MM-DD dates, as words.
export function checkedWhen(snapshotDate: string, today: string): string {
  const days = Math.round((Date.parse(today) - Date.parse(snapshotDate)) / 86_400_000)
  if (!Number.isFinite(days) || days <= 0) return 'today'
  return days === 1 ? 'yesterday' : `${days} days ago`
}

// Today's local date as YYYY-MM-DD, the way the changes skill names files.
export function localDate(now: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

function size(gb: number): string {
  if (gb >= 1000) return `${(gb / 1000).toFixed(1)} TB`
  return `${Math.round(gb).toLocaleString('en-US')} GB`
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0
}

// The numbers part of the line, from a snapshot file's text, or undefined
// when the text isn't a format 1 snapshot with a library part. Only numbers
// are taken from it: no library names or other text from the server.
export function libraryParts(text: string): string[] | undefined {
  let snapshot: unknown
  try {
    snapshot = JSON.parse(text)
  } catch {
    return undefined
  }
  if (snapshot === null || typeof snapshot !== 'object') return undefined
  const { format, library } = snapshot as Record<string, unknown>
  if (format !== 1 || library === null || typeof library !== 'object') return undefined

  let movies = 0
  let shows = 0
  let albums = 0
  let sizeGb = 0
  let hasSize = false
  for (const one of Object.values(library as Record<string, unknown>)) {
    if (one === null || typeof one !== 'object') continue
    const { counts, size_gb } = one as Record<string, unknown>
    if (counts !== null && typeof counts === 'object') {
      const c = counts as Record<string, unknown>
      movies += count(c.movies)
      shows += count(c.shows)
      albums += count(c.albums)
    }
    if (typeof size_gb === 'number' && Number.isFinite(size_gb) && size_gb >= 0) {
      sizeGb += size_gb
      hasSize = true
    }
  }

  const parts: string[] = []
  if (movies) parts.push(`${movies.toLocaleString('en-US')} movies`)
  if (shows) parts.push(`${shows.toLocaleString('en-US')} shows`)
  if (albums) parts.push(`${albums.toLocaleString('en-US')} albums`)
  if (hasSize) parts.push(size(sizeGb))
  return parts
}

// The whole line, from the newest snapshot's date and its parts (undefined
// when the snapshot couldn't be read).
export function statusLine(snapshotDate: string, today: string, parts: string[] | undefined): string {
  return ['Plex:', [...(parts ?? []), `checked ${checkedWhen(snapshotDate, today)}`].join(' · ')].join(' ')
}
