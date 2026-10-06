// The read-only guard's rules, as plain functions over text. Nothing here
// touches Claude Code, so the rules can be read and tested on their own.
// The rules are written down in openspec/specs/read-only-guard/spec.md.

// The setting that switches the guard on and off (plugin.json's userConfig).
export const GUARD_SETTING = 'read_only_guard'

// Addresses that point at Plex whatever the user's own server is called.
const PLEX_SIGNS = [
  /(^|[^a-z0-9.-])plex\.tv(?![a-z0-9-])/,
  /\.plex\.tv(?![a-z0-9-])/,
  /\.plex\.direct(?![a-z0-9-])/,
  /:32400(?![0-9])/,
  /x-plex-token/,
]

// Plex addresses that change something even when only read. The first group
// does so through a plain GET (checked against python-plexapi); the second
// is changed by Plex with PUT, listed in case a server also takes a GET.
const PLEX_CHANGING_PATHS: readonly [string, string][] = [
  ['/refresh', 'starts a library scan or metadata refresh'],
  ['/:/scrobble', 'marks something as watched'],
  ['/:/unscrobble', 'marks something as unwatched'],
  ['/:/progress', "changes someone's watch progress"],
  ['/:/timeline', "changes someone's watch progress"],
  ['/status/sessions/terminate', "stops someone's stream"],
  ['/:/rate', 'changes a rating'],
  ['/emptytrash', "empties a library's trash"],
  ['/library/optimize', 'optimizes the Plex database'],
  ['/library/clean/', 'cleans up Plex files'],
  ['/actions/', 'changes what shows in Continue Watching'],
]

// Tautulli API commands that only read. Everything else counts as a write.
const TAUTULLI_READS = new Set(['arnold', 'status', 'search', 'docs', 'docs_md'])

const WRITE_METHODS = 'POST|PUT|PATCH|DELETE'

// Keeps the host (and port, when one is written) of an address, lowercased.
// Anything else in the address, such as a token in the query, is dropped.
export function hostOf(address: unknown): string | undefined {
  if (typeof address !== 'string' || address.trim() === '') return undefined
  try {
    return new URL(address.trim()).host.toLowerCase() || undefined
  } catch {
    return undefined
  }
}

// Reads Cinemetric's settings file text and keeps only the two hosts. The
// token and API key are never copied out of the parsed object.
export function hostsFromSettings(text: string): string[] {
  let settings: unknown
  try {
    settings = JSON.parse(text)
  } catch {
    return []
  }
  if (settings === null || typeof settings !== 'object') return []
  const { plex_url, tautulli_url } = settings as Record<string, unknown>
  return [hostOf(plex_url), hostOf(tautulli_url)].filter((host): host is string => !!host)
}

function escapeForRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// True when the text is aimed at the user's Plex server, Tautulli or plex.tv.
export function isAimedAtServers(text: string, hosts: readonly string[]): boolean {
  const lower = text.toLowerCase()
  if (PLEX_SIGNS.some(sign => sign.test(lower))) return true

  return hosts.some(host =>
    new RegExp(`(^|[^a-z0-9.-])${escapeForRegExp(host)}(?![a-z0-9-]|\\.[a-z0-9])`).test(lower),
  )
}

// The parts of a shell command that run one after another or through a pipe.
// A lone `&` is left alone because it shows up inside web addresses.
function commandParts(text: string): string[] {
  return text.split(/\|\||&&|[|;\n]/)
}

// Says why the text would change something, or undefined when it only reads.
export function writeReason(text: string): string | undefined {
  const method =
    new RegExp(`(?:^|[^A-Za-z0-9_])(${WRITE_METHODS})(?![A-Za-z0-9_])`).exec(text) ??
    new RegExp(
      `(?:-X\\s*|--request[\\s=]+|--method[\\s=]+|-Method\\s+|method\\s*[=:]\\s*)['"]?(${WRITE_METHODS})\\b`,
      'i',
    ).exec(text) ??
    new RegExp(`\\b(?:requests|httpx|session|client)\\.(${WRITE_METHODS})\\s*\\(`, 'i').exec(text)
  if (method?.[1]) return `uses the ${method[1].toUpperCase()} method`

  if (/(?:^|\s)--(?:data(?:-raw|-binary|-urlencode|-ascii)?|json|form(?:-string)?|upload-file)(?=[\s=]|$)/.test(text)) {
    return 'sends data to the server'
  }
  if (/(?:^|\s)--(?:post-data|post-file|body-data|body-file)(?=[\s=]|$)/.test(text)) {
    return 'sends data to the server'
  }
  // curl's short flags (-d, -F, -T, also inside a group like -sd) are only
  // read inside the part of the command that runs curl, so `cut -d` or
  // `grep -F` elsewhere in a pipeline don't count.
  const curlSendsData = commandParts(text).some(
    part => /(?:^|[\s/\\])curl(?:\.exe)?(?=\s|$)/.test(part) && /(?:^|\s)-[a-zA-Z]*[dFT]/.test(part),
  )
  if (curlSendsData) return 'sends data to the server'

  const tautulliCommand = /\bcmd["']?\s*[=:]\s*["']?([A-Za-z0-9_]+)/.exec(text)
  if (tautulliCommand?.[1]) {
    const command = tautulliCommand[1].toLowerCase()
    if (!command.startsWith('get_') && !TAUTULLI_READS.has(command)) {
      return `runs the Tautulli command ${command}, which isn't a read`
    }
  }

  const lower = text.toLowerCase()
  for (const [path, what] of PLEX_CHANGING_PATHS) {
    if (lower.includes(path)) return what
  }

  return undefined
}

// The reason a call would write to the user's servers, or undefined.
export function blockReason(text: string, hosts: readonly string[]): string | undefined {
  return isAimedAtServers(text, hosts) ? writeReason(text) : undefined
}

const SETTINGS_FILE = /(^|[\/\\])\.claude[\/\\]settings(\.local)?\.json$/
const SETTINGS_FILE_IN_TEXT = /\.claude[\/\\]settings(\.local)?\.json/

// True when a file is one of Claude Code's settings files.
export function isSettingsFile(path: string): boolean {
  return SETTINGS_FILE.test(path.trim())
}

// True when a shell command names one of Claude Code's settings files and
// mentions the guard's setting.
export function commandTouchesGuardSetting(command: string): boolean {
  return SETTINGS_FILE_IN_TEXT.test(command) && command.includes(GUARD_SETTING)
}

// True when an edit or write to a file would touch the guard's setting in
// one of Claude Code's settings files.
export function editTouchesGuardSetting(path: string, ...texts: readonly string[]): boolean {
  return isSettingsFile(path) && texts.some(text => text.includes(GUARD_SETTING))
}

// Whether a plugin name is this plugin's, however it was loaded ("cinemetric",
// "cinemetric@cinemetric", "cinemetric@inline").
export function isThisPlugin(name: string, own: string): boolean {
  return name.split('@')[0] === own.split('@')[0]
}

export const BLOCKED_PREFIX = 'Cinemetric read-only guard'

const HOW_TO_SWITCH_OFF =
  'To switch the guard off, the user can type /cinemetric-mods guard off, or use the /config menu.'

export function serverBlockMessage(reason: string): string {
  return (
    `${BLOCKED_PREFIX} blocked this: it would change something on the Plex server, Tautulli or ` +
    `plex.tv (it ${reason}). Cinemetric only reads from the server. If the user wants this change, ` +
    `they can make it themselves in Plex or Tautulli. ${HOW_TO_SWITCH_OFF}`
  )
}

export function settingBlockMessage(): string {
  return `${BLOCKED_PREFIX} blocked this: only the user can switch the guard off. ${HOW_TO_SWITCH_OFF}`
}
