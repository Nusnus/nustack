/**
 * The OpenCode plugin's promises: it registers every skill folder, hides the principle and language skills from
 * the model, and puts nus-mode back once a summary drops it, only in a session that loaded it.
 */
import { expect, test } from "bun:test"
import { readdir } from "node:fs/promises"
import plugin from "../plugin/opencode.ts"

type Hook = (event: Record<string, unknown>) => Promise<void>

async function start() {
  const added: { id: string; autoinvoke: boolean; content: string }[] = []
  const hooks: Record<string, Hook> = {}
  const storage = new Map<string, unknown>()
  const register = (name: string, hook: Hook) => {
    hooks[name] = hook
    return { dispose: async () => {} }
  }
  const context = {
    skill: {
      transform: (edit: (editor: object) => void) => {
        edit({ add: (skill: never) => added.push(skill) })
        return register("skill", async () => {})
      },
    },
    session: { hook: register },
    tool: { hook: register },
    storage: {
      get: async (key: string) => storage.get(key),
      set: async (key: string, value: unknown) => void storage.set(key, value),
    },
  }
  await plugin.setup(context as never)
  const request = async (messages: unknown[]) => {
    const system: { text: string }[] = []
    await hooks.context?.({ sessionID: "s", system, messages })
    return system
  }
  return { added, hooks, request }
}

test("registers every skill folder, hiding the principles and language skills", async () => {
  const { added } = await start()
  expect(added.map((skill) => skill.id).sort()).toEqual(
    (await readdir("plugin/skills", { withFileTypes: true }))
      .filter((each) => each.isDirectory())
      .map((each) => each.name)
      .sort(),
  )
  for (const skill of added) expect(skill.autoinvoke).toBe(!/^(principle|language)-/.test(skill.id))
})

test("puts nus-mode back once a summary drops it, only in a session that loaded it", async () => {
  const { added, hooks, request } = await start()
  const mode = added.find((skill) => skill.id === "nus-mode")?.content.trim() ?? ""
  expect(await request([{ text: "summary" }])).toEqual([])
  await hooks["execute.after"]?.({
    tool: "skill",
    input: { id: "nus-mode" },
    sessionID: "s",
    status: "error",
  })
  expect(await request([{ text: "summary" }])).toEqual([])
  await hooks["execute.after"]?.({
    tool: "skill",
    input: { id: "nus-mode" },
    sessionID: "s",
    status: "completed",
  })
  expect(await request([{ text: mode }])).toEqual([])
  const [reload] = await request([{ text: "summary" }])
  expect(reload?.text.startsWith(mode)).toBe(true)
})
