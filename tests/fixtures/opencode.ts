/**
 * OpenCode's skill registry, session and tool hooks and plugin storage, as the loader uses them, and the error the
 * loader gives for a skill file, for the loader's unit tests; tests/unit/fixtures/opencode.test.ts tests the fake.
 */
import type { Skill } from "@opencode/plugin"
import { type Context, SkillError } from "../../plugin/opencode.ts"

/** A hook's name and the fields of its event a test sets beside the session's ID. */
export type HookEvent = [string, object]

export function refusal(path: string, problem: string): SkillError {
  return new SkillError(`${path} ${problem}, or reinstall the nustack plugin`)
}

export function fakeOpenCode(stored = new Map<string, Parameters<Context["storage"]["set"]>[1]>()) {
  const skills: string[] = []
  const hooks = new Map<string, (event: unknown) => Promise<void> | void>()
  const hook = async (name: string, callback: (event: never) => Promise<void> | void) => {
    hooks.set(name, callback as (event: unknown) => Promise<void> | void)
    return { dispose: async () => void hooks.delete(name) }
  }
  // The loader only adds skills, so the editor holds add alone.
  const editor = { add: (skill: Skill.Info) => void skills.push(skill.id) } as never
  const context: Context = {
    skill: {
      transform: async (edit) => {
        edit(editor)
        return { dispose: async () => void skills.splice(0) }
      },
    },
    session: { hook },
    tool: { hook },
    storage: {
      get: async (key) => stored.get(key),
      set: async (...pair) => void stored.set(...pair),
    },
  }
  const run = async ([name, event]: HookEvent) => {
    const callback = hooks.get(name)
    if (callback === undefined)
      throw new Error(`no ${name} hook is registered; register one before running it`)
    return callback({ sessionID: "s", ...event })
  }
  return { skills, hooks, stored, context, run }
}
