// The /cinemetric-mods command: lists the mods and switches them on or off,
// through the same setting the /config menu changes.

import type { EngineInterface, On, PluginOptions, PromptOrigin } from 'claude-code'

import { MODS, type Mod } from './mods'

export const COMMAND = 'cinemetric-mods'

const USAGE =
  `Type /${COMMAND} to see every mod, or /${COMMAND} <name> on or /${COMMAND} <name> off ` +
  `to switch one. Mods: ${MODS.map(mod => mod.name).join(', ')}.`

// The /config key for a mod's setting: "<plugin>.<setting>". The plugin part
// depends on how Cinemetric was loaded, so the menu's own row is used when it
// lists one, and the plain plugin name otherwise.
async function settingKey($: EngineInterface, mod: Mod): Promise<string> {
  const rows = await $.config.list()
  const row = rows.find(
    one => one.key.endsWith(`.${mod.setting}`) && one.provider.plugin === $.plugin.name,
  )
  return row?.key ?? `${$.plugin.name}.${mod.setting}`
}

// Whether a mod is on. Claude Code loads this module again whenever a switch
// changes, so the options it was loaded with are always the current ones.
function isOn(options: PluginOptions, mod: Mod): boolean {
  return options[mod.setting] === true
}

// Whether the run came from the person themselves: Enter at the prompt, or
// their own message through Remote Control.
function isFromUser(origin: PromptOrigin): boolean {
  return origin.kind === 'composer' || origin.kind === 'bridge'
}

function listMods(options: PluginOptions): string {
  const lines = MODS.map(mod => `  ${mod.name} (${isOn(options, mod) ? 'on' : 'off'}): ${mod.description}`)
  return ['Cinemetric mods:', ...lines, '', USAGE].join('\n')
}

async function switchMod(
  $: EngineInterface,
  options: PluginOptions,
  mod: Mod,
  toOn: boolean,
  origin: PromptOrigin,
): Promise<string> {
  const word = toOn ? 'on' : 'off'
  if (!toOn && mod.isUserOnlyOff && !isFromUser(origin)) {
    return `Only you can switch the ${mod.name} off. Type /${COMMAND} ${mod.name} off yourself, or use /config.`
  }
  if (isOn(options, mod) === toOn) return `${mod.name} is already ${word}.`
  let deny: string | undefined
  try {
    ;({ deny } = await $.config.set({ key: await settingKey($, mod), value: toOn }))
  } catch (error) {
    // Say why, so a session that can't change settings (such as one the
    // desktop app started) can be told apart from other failures.
    const reason = error instanceof Error && error.message ? ` (${error.message.split('\n')[0]})` : ''
    return (
      `Couldn't switch ${mod.name} ${word} from here${reason}. ` +
      `Type /${COMMAND} ${mod.name} ${word} in Claude Code in a terminal, or use /config.`
    )
  }
  if (deny !== undefined) return `Couldn't switch ${mod.name} ${word}: ${deny}`
  return `${mod.name} is now ${word}.`
}

export async function answerCommand(
  $: EngineInterface,
  options: PluginOptions,
  args: string,
  origin: PromptOrigin,
): Promise<string> {
  const words = args.trim().toLowerCase().split(/\s+/).filter(Boolean)
  if (words.length === 0) return listMods(options)

  const mod = MODS.find(one => one.name === words[0])
  const state = words[1]
  if (mod === undefined || words.length !== 2 || (state !== 'on' && state !== 'off')) {
    return `Nothing changed. ${USAGE}`
  }
  return switchMod($, options, mod, state === 'on', origin)
}

// How the command is listed. It's added in status-line.ts's session.start
// hook (a module has one), whether or not any mod is on, so a mod can always
// be switched back on.
export const COMMAND_SPEC = {
  name: COMMAND,
  description: 'List Cinemetric mods, or switch one on or off',
  argumentHint: '[name on|off]',
}

export function setUpCommand(on: On, options: PluginOptions): void {
  on('command.run', { command: COMMAND }, async ($, e) => ({
    text: await answerCommand($, options, e.args, e.origin),
  }))
}
