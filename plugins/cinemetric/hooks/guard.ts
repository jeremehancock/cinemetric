// The read-only guard: checks Claude's own shell commands and web fetches
// before they run, and refuses the ones that would change the user's Plex
// server, Tautulli or plex.tv. It also keeps the user's Plex token and
// Tautulli API key out of what Claude sees and sends.
// See openspec/specs/read-only-guard/spec.md.

import type { EngineInterface, On } from 'claude-code'

import {
  BLOCKED_PREFIX,
  GUARD_SETTING,
  type Secret,
  type Settings,
  blockReason,
  combineSecrets,
  commandReadsCinemetricSettings,
  commandTouchesGuardSetting,
  editTouchesGuardSetting,
  findSecret,
  hideInText,
  hideSecrets,
  hostOf,
  isAimedAtServers,
  isCinemetricSettingsFile,
  isThisPlugin,
  plexToken,
  readSettings,
  secretBlockMessage,
  serverBlockMessage,
  settingBlockMessage,
  settingsFileBlockMessage,
  shellBlockReason,
} from './guard-rules'

// What the guard uses from Cinemetric's settings file, and the file's
// modification time when it was read, so it's read again only when it
// changes. The token and API key live only here, in this module's memory.
type Remembered = { path: string; mtimeMs: number; settings: Settings }

let remembered: Remembered | undefined

// Where setup.py keeps Cinemetric's settings: $XDG_CONFIG_HOME/cinemetric,
// otherwise ~/.config/cinemetric (USERPROFILE stands for ~ on Windows).
async function settingsPath($: EngineInterface): Promise<string | undefined> {
  const xdg = await $.env.get('XDG_CONFIG_HOME')
  if (xdg) return `${xdg}/cinemetric/config.json`
  const home = (await $.env.get('HOME')) ?? (await $.env.get('USERPROFILE'))
  return home ? `${home}/.config/cinemetric/config.json` : undefined
}

const NOTHING: Settings = { hosts: [], secrets: [] }

// The hosts and secrets in the settings file. A missing or unreadable file
// means none.
async function settingsFromFile($: EngineInterface): Promise<Settings> {
  const path = await settingsPath($)
  if (!path) return NOTHING
  let mtimeMs: number
  try {
    mtimeMs = (await $.fs.stat(path)).mtimeMs
  } catch {
    remembered = undefined
    return NOTHING
  }
  if (remembered?.path === path && remembered.mtimeMs === mtimeMs) return remembered.settings
  let settings = NOTHING
  try {
    const text = await $.fs.read(path)
    settings = typeof text === 'string' ? readSettings(text) : NOTHING
  } catch {
    settings = NOTHING
  }
  remembered = { path, mtimeMs, settings }
  return settings
}

// The configured Plex and Tautulli hosts: from PLEX_URL and TAUTULLI_URL,
// which Cinemetric's scripts use before the settings file, and from the file.
// With none, the guard carries on with the rules that need no address.
async function configuredHosts($: EngineInterface): Promise<string[]> {
  const fromEnvironment = [
    hostOf(await $.env.get('PLEX_URL')),
    hostOf(await $.env.get('TAUTULLI_URL')),
  ].filter((host): host is string => !!host)
  return [...fromEnvironment, ...(await settingsFromFile($)).hosts]
}

// The Plex token and Tautulli API key to protect: from PLEX_TOKEN, which the
// scripts use before the settings file, and from the file.
async function protectedSecrets($: EngineInterface): Promise<Secret[]> {
  return combineSecrets(
    [plexToken(await $.env.get('PLEX_TOKEN'))],
    (await settingsFromFile($)).secrets,
  )
}

// A tool's own arguments, without the keys the engine adds beside them.
function toolArguments(e: object): object {
  const { tool, tool_use_id, consent, agentId, ...rest } = e as Record<string, unknown>
  return rest
}

// Sending the token to the user's own server, or Tautulli, is how it's meant
// to be used. Writes there are still refused by the hooks further in.
function aimedAtOwnServers(e: { tool: string } & Record<string, unknown>, hosts: readonly string[]): boolean {
  if (e.tool === 'Bash' && typeof e.command === 'string') return isAimedAtServers(e.command, hosts)
  if (e.tool === 'WebFetch' && typeof e.url === 'string') return isAimedAtServers(e.url, hosts)
  return false
}

function sayGuardFailed($: EngineInterface, what = "couldn't check a command, so it ran unchecked."): void {
  try {
    $.ui.toast(`${BLOCKED_PREFIX} ${what}`)
  } catch {
    // Nothing more to do: the call still goes ahead.
  }
}

export function setUpGuard(on: On): void {
  // The token and API key, for every tool. Registered first so it wraps the
  // hooks below: it sees each call before them and its result after them.
  on('tool.call', async ($, e, next) => {
    const secrets = await protectedSecrets($)
    if (secrets.length === 0) return next(e)
    const found = findSecret(JSON.stringify(toolArguments(e)), secrets)
    if (found && !aimedAtOwnServers(e as never, await configuredHosts($))) {
      return { deny: secretBlockMessage(found) }
    }
    const answer = await next(e)
    if (answer.deny !== undefined) return answer
    // Most results hold no secret, and are handed back exactly as they came.
    if (!findSecret(JSON.stringify(answer), secrets)) return answer
    if (answer.isError) {
      return { deny: hideInText(answer.text ?? String(answer.result ?? ''), secrets) }
    }
    return {
      result: hideSecrets(answer.result, secrets),
      ...(answer.context ? { context: hideSecrets(answer.context, secrets) } : {}),
    }
  }).catch(($, e, next) => {
    // After the tool has run, next(e) hands back its result without running
    // it again.
    sayGuardFailed($, next.called ? "couldn't check a tool's output for the Plex token." : undefined)
    return next(e)
  })

  // Cinemetric's settings file, which holds the token and API key.
  on('tool.call', { tool: 'Read' }, async ($, e, next) =>
    isCinemetricSettingsFile(e.file_path, await settingsPath($))
      ? { deny: settingsFileBlockMessage() }
      : next(e),
  ).catch(($, e, next) => {
    sayGuardFailed($)
    return next(e)
  })

  // Shell commands: writes to the servers, and switching the guard off
  // through a Claude Code settings file.
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (commandTouchesGuardSetting(e.command)) return { deny: settingBlockMessage() }
    if (commandReadsCinemetricSettings(e.command, await settingsPath($))) {
      return { deny: settingsFileBlockMessage() }
    }
    const reason = shellBlockReason(e.command, await configuredHosts($))
    return reason ? { deny: serverBlockMessage(reason) } : next(e)
  }).catch(($, e, next) => {
    sayGuardFailed($)
    return next(e)
  })

  // Web fetches only send GET, so only the address can make one a write.
  on('tool.call', { tool: 'WebFetch' }, async ($, e, next) => {
    const reason = blockReason(e.url, await configuredHosts($))
    return reason ? { deny: serverBlockMessage(reason) } : next(e)
  }).catch(($, e, next) => {
    sayGuardFailed($)
    return next(e)
  })

  on('tool.call', { tool: 'Write' }, ($, e, next) =>
    editTouchesGuardSetting(e.file_path, e.content) ? { deny: settingBlockMessage() } : next(e),
  ).catch(($, e, next) => {
    sayGuardFailed($)
    return next(e)
  })

  on('tool.call', { tool: 'Edit' }, ($, e, next) =>
    editTouchesGuardSetting(e.file_path, e.old_string, e.new_string)
      ? { deny: settingBlockMessage() }
      : next(e),
  ).catch(($, e, next) => {
    sayGuardFailed($)
    return next(e)
  })

  // Another plugin switching the guard off through the settings menu's own
  // route. The person's own change in /config passes, and so does this
  // plugin's /cinemetric-mods command, which already lets only the person
  // switch the guard off. Claude Code is meant to skip a plugin's own hooks
  // for its own change, but a hot-reloaded copy can still reach this one, so
  // the name is checked here too.
  on('config.set', ($, e, next) =>
    e.key.endsWith(`.${GUARD_SETTING}`) &&
    e.value === false &&
    e.origin.kind === 'plugin' &&
    !isThisPlugin(e.origin.name, $.plugin.name)
      ? { deny: settingBlockMessage() }
      : next(e),
  )
}
