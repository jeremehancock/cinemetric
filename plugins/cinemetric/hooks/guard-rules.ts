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

// The same for a shell command, except that a command which only runs
// text-only programs (a commit, a pull request, `cat > notes.md <<'EOF'`)
// is let through even when its text mentions the server and a write word.
export function shellBlockReason(command: string, hosts: readonly string[]): string | undefined {
  if (!isAimedAtServers(command, hosts) || onlyHandlesText(command)) return undefined
  return writeReason(command)
}

// Programs that only handle text: they can't send a request and don't run
// their arguments. Left off on purpose: sed (its `e` command), sort
// (--compress-program), rg (--pre), awk, find and xargs, which can all run
// other programs.
const TEXT_ONLY_PROGRAMS = new Set([
  'echo', 'printf', 'cat', 'tee', 'head', 'tail', 'grep', 'wc', 'ls', 'pwd', 'cd', 'mkdir', 'true',
  'false',
])

// git and gh count only with one of these straight after the name, so
// `git -c alias.x='!cmd'`, `git push` and `gh api` are checked as usual.
const TEXT_ONLY_SUBCOMMANDS: Record<string, ReadonlySet<string>> = {
  git: new Set([
    'add', 'commit', 'status', 'log', 'diff', 'show', 'tag', 'branch', 'checkout', 'switch',
    'restore', 'stash', 'notes', 'rev-parse',
  ]),
  gh: new Set(['pr', 'issue', 'release']),
}

// True when the guard can read the whole command and every program it runs
// only handles text. Anything it can't read counts as false, so the command
// gets the usual checks.
export function onlyHandlesText(command: string): boolean {
  if (/\/dev\/(?:tcp|udp)\//i.test(command)) return false
  const commands = commandsIn(command)
  return commands !== undefined && commands.every(isTextOnly)
}

function isTextOnly(words: readonly string[]): boolean {
  // Words such as NAME=value before the program's name set a variable.
  let first = 0
  while (first < words.length && isAssignment(words[first] ?? '')) first++
  const [name, subcommand] = words.slice(first)
  if (name === undefined) return true
  if (TEXT_ONLY_PROGRAMS.has(name)) return true
  return subcommand !== undefined && (TEXT_ONLY_SUBCOMMANDS[name]?.has(subcommand) ?? false)
}

function isAssignment(word: string): boolean {
  return /^[A-Za-z_][A-Za-z0-9_]*=/.test(word)
}

// Thrown by the reader when it meets shell syntax it doesn't read.
class CannotRead extends Error {}

// Stands in for text the shell fills in by running a command, such as
// $(...). It can't be part of a program's name on the lists above.
const FILLED_IN = '\u0000'

type Heredoc = { end: string; stripTabs: boolean; expands: boolean }

// Reads a shell command the way the shell would, far enough to know which
// programs it runs. Gives back each command as its words with quotes removed
// (redirections and their files left out), including the commands run by
// $(...), backticks, <(...) and >(...). Gives back undefined for anything it
// doesn't read: ${...}, $((...)), subshells and groups, and anything left open.
export function commandsIn(text: string): string[][] | undefined {
  try {
    const reader = new ShellReader(text)
    reader.readCommands(false)
    return reader.commands
  } catch (error) {
    if (error instanceof CannotRead) return undefined
    throw error
  }
}

class ShellReader {
  at = 0
  commands: string[][] = []
  private heredocs: Heredoc[] = []

  constructor(private readonly text: string) {}

  // Reads commands until the end of the text, or until the `)` that closes
  // a $(...), <(...) or >(...) when `inParentheses` is true.
  readCommands(inParentheses: boolean): void {
    const text = this.text
    let words: string[] = []
    let word: string | undefined
    let isFileName = false

    const endWord = () => {
      if (word !== undefined && !isFileName) words.push(word)
      if (word !== undefined) isFileName = false
      word = undefined
    }
    const endCommand = () => {
      endWord()
      if (isFileName) throw new CannotRead()
      if (words.length > 0) this.commands.push(words)
      words = []
    }
    const add = (part: string) => {
      word = (word ?? '') + part
    }

    while (true) {
      if (this.at >= text.length) {
        if (inParentheses || this.heredocs.length > 0) throw new CannotRead()
        endCommand()
        return
      }
      const c = text.charAt(this.at)
      const next = text[this.at + 1]

      if (c === ' ' || c === '\t') {
        endWord()
        this.at++
      } else if (c === '\n') {
        endCommand()
        this.at++
        this.readHeredocBodies()
      } else if (c === '#' && word === undefined) {
        while (this.at < text.length && text[this.at] !== '\n') this.at++
      } else if (c === ')') {
        if (!inParentheses) throw new CannotRead()
        endCommand()
        this.at++
        return
      } else if (c === ';' || c === '|' || (c === '&' && next !== '>')) {
        endCommand()
        this.at += next === c || (c === '|' && next === '&') ? 2 : 1
      } else if ((c === '<' || c === '>') && next === '(') {
        this.at += 2
        this.readCommands(true)
        add(FILLED_IN)
      } else if (c === '<' && next === '<' && text[this.at + 2] === '<') {
        // A here-string: the next word is text given to the program.
        endRedirectNumber()
        this.at += 3
      } else if (c === '<' && next === '<') {
        endRedirectNumber()
        this.at += 2
        this.readHeredocStart()
      } else if (c === '<' || c === '>' || c === '&') {
        endRedirectNumber()
        endWord()
        const operator = /^(?:&>>?|[0-9]*(?:>>|>\||>&|<&|<>|>|<))/.exec(text.slice(this.at))
        this.at += operator ? operator[0].length : 1
        isFileName = true
      } else if (c === '(' || ((c === '{' || c === '}') && word === undefined)) {
        throw new CannotRead()
      } else if (c === "'") {
        const close = text.indexOf("'", this.at + 1)
        if (close < 0) throw new CannotRead()
        add(text.slice(this.at + 1, close))
        this.at = close + 1
      } else if (c === '"') {
        this.at++
        add(this.readDoubleQuoted())
      } else if (c === '\\') {
        if (next === undefined) throw new CannotRead()
        if (next !== '\n') add(next)
        this.at += 2
      } else if (c === '`') {
        this.readBackticks()
        add(FILLED_IN)
      } else if (c === '$') {
        add(this.readDollar())
      } else {
        add(c)
        this.at++
      }
    }

    // `2>` and the like: a number written right before a redirection is the
    // stream being redirected, not a word.
    function endRedirectNumber() {
      if (word !== undefined && /^[0-9]+$/.test(word)) word = undefined
      else endWord()
    }
  }

  // After `$`: a command run by $(...), ANSI-C quoting $'...', or a plain `$`
  // (a variable, whose value the guard doesn't need).
  private readDollar(): string {
    const text = this.text
    const next = text[this.at + 1]
    if (next === '(') {
      if (text[this.at + 2] === '(') throw new CannotRead()
      this.at += 2
      this.readCommands(true)
      return FILLED_IN
    }
    if (next === '{') throw new CannotRead()
    if (next === "'") {
      let i = this.at + 2
      while (i < text.length && text[i] !== "'") i += text[i] === '\\' ? 2 : 1
      if (i >= text.length) throw new CannotRead()
      const inside = text.slice(this.at + 2, i)
      this.at = i + 1
      return inside
    }
    this.at++
    return '$'
  }

  // Reads up to the closing double quote, starting just after the opening one.
  private readDoubleQuoted(): string {
    const text = this.text
    let inside = ''
    while (true) {
      if (this.at >= text.length) throw new CannotRead()
      const c = text.charAt(this.at)
      const next = text[this.at + 1]
      if (c === '"') {
        this.at++
        return inside
      } else if (c === '\\') {
        if (next === undefined) throw new CannotRead()
        inside += '$`"\\\n'.includes(next) ? (next === '\n' ? '' : next) : c + next
        this.at += 2
      } else if (c === '`') {
        this.readBackticks()
        inside += FILLED_IN
      } else if (c === '$') {
        inside += this.readDollar()
      } else {
        inside += c
        this.at++
      }
    }
  }

  // Reads `...` as a command of its own, starting at the opening backtick.
  private readBackticks(): void {
    const text = this.text
    let inside = ''
    let i = this.at + 1
    while (true) {
      if (i >= text.length) throw new CannotRead()
      if (text[i] === '`') break
      if (text[i] === '\\' && '$`\\'.includes(text[i + 1] ?? '')) {
        inside += text[i + 1]
        i += 2
      } else {
        inside += text[i]
        i++
      }
    }
    this.at = i + 1
    const commands = commandsIn(inside)
    if (commands === undefined) throw new CannotRead()
    this.commands.push(...commands)
  }

  // After `<<`: the word that ends the here-document. Quoting any part of it
  // means the body is plain text; otherwise the shell fills in $(...) there.
  private readHeredocStart(): void {
    const text = this.text
    let stripTabs = false
    if (text[this.at] === '-') {
      stripTabs = true
      this.at++
    }
    while (text[this.at] === ' ' || text[this.at] === '\t') this.at++
    let end = ''
    let expands = true
    while (this.at < text.length && !/[\s;&|<>()]/.test(text[this.at] ?? '')) {
      const c = text.charAt(this.at)
      if (c === "'" || c === '"') {
        const close = text.indexOf(c, this.at + 1)
        if (close < 0) throw new CannotRead()
        end += text.slice(this.at + 1, close)
        this.at = close + 1
        expands = false
      } else if (c === '\\') {
        end += text[this.at + 1] ?? ''
        this.at += 2
        expands = false
      } else if (c === '$' || c === '`') {
        throw new CannotRead()
      } else {
        end += c
        this.at++
      }
    }
    if (end === '') throw new CannotRead()
    this.heredocs.push({ end, stripTabs, expands })
  }

  // After a new line: the bodies of any here-documents started on that line.
  private readHeredocBodies(): void {
    const text = this.text
    for (const heredoc of this.heredocs) {
      while (true) {
        if (this.at >= text.length) throw new CannotRead()
        let lineEnd = text.indexOf('\n', this.at)
        if (lineEnd < 0) lineEnd = text.length
        const line = text.slice(this.at, lineEnd)
        this.at = Math.min(lineEnd + 1, text.length)
        if ((heredoc.stripTabs ? line.replace(/^\t+/, '') : line) === heredoc.end) break
        // The shell runs anything in $(...) or backticks while filling in an
        // unquoted body. Rather than read those, check the whole command.
        if (heredoc.expands && /\$\(|\$\{|`/.test(line)) throw new CannotRead()
      }
    }
    this.heredocs = []
  }
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
