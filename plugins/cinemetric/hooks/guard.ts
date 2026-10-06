// The read-only guard: checks Claude's own shell commands and web fetches
// before they run, and refuses the ones that would change the user's Plex
// server, Tautulli or plex.tv. See openspec/specs/read-only-guard/spec.md.

import type { EngineInterface, On } from 'claude-code'

import {
  BLOCKED_PREFIX,
  GUARD_SETTING,
  blockReason,
  commandTouchesGuardSetting,
  editTouchesGuardSetting,
  hostOf,
  hostsFromSettings,
  isThisPlugin,
  serverBlockMessage,
  settingBlockMessage,
} from './guard-rules'

// The hosts from Cinemetric's settings file, and the file's modification
// time when they were read, so the file is read again only when it changes.
type Remembered = { path: string; mtimeMs: number; hosts: string[] }

let remembered: Remembered | undefined

// Where setup.py keeps Cinemetric's settings: $XDG_CONFIG_HOME/cinemetric,
// otherwise ~/.config/cinemetric (USERPROFILE stands for ~ on Windows).
async function settingsPath($: EngineInterface): Promise<string | undefined> {
  const xdg = await $.env.get('XDG_CONFIG_HOME')
  if (xdg) return `${xdg}/cinemetric/config.json`
  const home = (await $.env.get('HOME')) ?? (await $.env.get('USERPROFILE'))
  return home ? `${home}/.config/cinemetric/config.json` : undefined
}

// The hosts in the settings file. A missing or unreadable file means none.
async function hostsFromFile($: EngineInterface): Promise<string[]> {
  const path = await settingsPath($)
  if (!path) return []
  let mtimeMs: number
  try {
    mtimeMs = (await $.fs.stat(path)).mtimeMs
  } catch {
    remembered = undefined
    return []
  }
  if (remembered?.path === path && remembered.mtimeMs === mtimeMs) return remembered.hosts
  let hosts: string[] = []
  try {
    const text = await $.fs.read(path)
    hosts = typeof text === 'string' ? hostsFromSettings(text) : []
  } catch {
    hosts = []
  }
  remembered = { path, mtimeMs, hosts }
  return hosts
}

// The configured Plex and Tautulli hosts: from PLEX_URL and TAUTULLI_URL,
// which Cinemetric's scripts use before the settings file, and from the file.
// With none, the guard carries on with the rules that need no address.
async function configuredHosts($: EngineInterface): Promise<string[]> {
  const fromEnvironment = [
    hostOf(await $.env.get('PLEX_URL')),
    hostOf(await $.env.get('TAUTULLI_URL')),
  ].filter((host): host is string => !!host)
  return [...fromEnvironment, ...(await hostsFromFile($))]
}

function sayGuardFailed($: EngineInterface): void {
  try {
    $.ui.toast(`${BLOCKED_PREFIX} couldn't check a command, so it ran unchecked.`)
  } catch {
    // Nothing more to do: the call still goes ahead.
  }
}

export function setUpGuard(on: On): void {
  // Shell commands: writes to the servers, and switching the guard off
  // through a Claude Code settings file.
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    if (commandTouchesGuardSetting(e.command)) return { deny: settingBlockMessage() }
    const reason = blockReason(e.command, await configuredHosts($))
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
