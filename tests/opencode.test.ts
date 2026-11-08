/**
 * The OpenCode plugin's promises: it registers every skill folder, hides the principle and language skills from
 * the model, puts nus-mode back once a summary drops it, only in a session that loaded it, and refuses a broken
 * install by name. It sits at tests/opencode.test.ts rather than mirroring the plugin's path, since tests/ holds
 * this one test, and a tests/plugin/ folder would add a package of one module, which
 * plugin/skills/principle-layout/SKILL.md rules out.
 */
import { expect, test } from "bun:test"
import { chmod, cp, mkdir, mkdtemp, rm, symlink, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import type { Plugin, Skill } from "@opencode/plugin"
import plugin from "../plugin/opencode.ts"

type Context = Plugin.Context
type Json = Parameters<Context["storage"]["set"]>[1]
// The members of OpenCode's context that plugin/opencode.ts calls, each held to its real signature.
type Used = {
  skill: Pick<Context["skill"], "transform">
  session: Pick<Context["session"], "hook">
  tool: Pick<Context["tool"], "hook">
  storage: Pick<Context["storage"], "get" | "set">
}
declare const sessionHook: Context["session"]["hook"]
declare const toolHook: Context["tool"]["hook"]
type Input<Hook extends (...args: never[]) => unknown> = Parameters<Parameters<Hook>[1]>[0]
type Prompt = Input<typeof sessionHook<"prompt">>
type Request = Input<typeof sessionHook<"context">>
type Executed = Input<typeof toolHook<"execute.after">>
type Callbacks = {
  prompt?: (input: Prompt) => Promise<void> | void
  context?: (input: Request) => Promise<void> | void
  "execute.after"?: (input: Executed) => Promise<void> | void
}

const MODE_FILE = await Bun.file("plugin/skills/nus-mode/SKILL.md").text()
const CONTENT = MODE_FILE.slice(MODE_FILE.indexOf("\n---\n", 3) + 5)
const BODY = CONTENT.trim()
const MODE_FOLDER = join(import.meta.dirname, "..", "plugin", "skills", "nus-mode")
const RELOAD = `${BODY}\n\nBase directory for this skill: ${MODE_FOLDER}`
const HIDDEN = [
  "language-python",
  "principle-boundaries",
  "principle-dependencies",
  "principle-design",
  "principle-deterministic-tests",
  "principle-dry",
  "principle-fail-fast",
  "principle-layout",
  "principle-long-term",
  "principle-naming",
  "principle-pr-descriptions",
  "principle-resilience",
  "principle-responses",
  "principle-self-explanatory-code",
  "principle-types",
] as const
const OFFERED = [
  "defuddle",
  "json-canvas",
  "knap",
  "nus-mode",
  "obsidian-bases",
  "obsidian-cli",
  "obsidian-markdown",
] as const

async function start(setup = plugin.setup) {
  const added: Skill.Info[] = []
  const hooks: Callbacks = {}
  const storage = new Map<string, Json>()
  const registration = { dispose: async () => {} }
  const register = async (name: keyof Callbacks, callback: never) => {
    hooks[name] = callback
    return registration
  }
  const editor = {
    list: () => added,
    get: (id: string) => added.find((skill) => skill.id === id),
    add: (skill: Skill.Info) => void added.push(skill),
    update: () => {},
    remove: () => {},
  }
  const context = {
    skill: {
      transform: async (edit: (input: typeof editor) => void) => {
        edit(editor)
        return registration
      },
    },
    session: { hook: register as Context["session"]["hook"] },
    tool: { hook: register as Context["tool"]["hook"] },
    storage: {
      get: async (key: string) => storage.get(key),
      set: async (key: string, value: Json) => void storage.set(key, value),
    },
  } satisfies Used
  await setup(context as Used as Context)
  const request = async (session: string, text: string) => {
    const event = {
      sessionID: session as Request["sessionID"],
      agent: "build" as Request["agent"],
      model: { id: "claude", providerID: "anthropic" } as Request["model"],
      system: [] as Request["system"],
      messages: [{ role: "user", content: [{ type: "text", text }] }],
      options: {},
      tools: {},
    } satisfies Request
    await hooks.context?.(event)
    return event.system.map((part) => part.text)
  }
  const skillCall = async (session: string, status: Executed["status"]) => {
    const call = {
      tool: "skill",
      sessionID: session as Executed["sessionID"],
      agent: "build" as Executed["agent"],
      messageID: "m" as Executed["messageID"],
      id: "c" as Executed["id"],
      input: { id: "nus-mode" },
    }
    // Tool.Error is a class of OpenCode's schema package, which nustack does not depend on.
    await hooks["execute.after"]?.(
      status === "completed"
        ? { ...call, status, result: {} }
        : { ...call, status, error: {} as Extract<Executed, { status: "error" }>["error"] },
    )
  }
  const prompt = async (session: string) =>
    hooks.prompt?.({
      sessionID: session as Prompt["sessionID"],
      messageID: "m" as Prompt["messageID"],
      prompt: { text: "go", skills: [{ id: "nus-mode" as Skill.ID }] },
      delivery: "queue",
    })
  return { added, request, skillCall, prompt }
}

async function brokenInstall(build: (skills: string) => Promise<void>) {
  const root = await mkdtemp(join(tmpdir(), "nustack-"))
  await cp("plugin/opencode.ts", join(root, "opencode.ts"))
  await build(join(root, "skills"))
  return { root, setup: (await import(join(root, "opencode.ts"))).default.setup }
}

test("registers every skill folder, hiding the principles and language skills", async () => {
  const { added } = await start()
  const ids = (hidden: boolean) =>
    added
      .filter((skill) => skill.autoinvoke !== hidden)
      .map((skill): string => skill.id)
      .sort()
  expect(ids(true)).toEqual([...HIDDEN])
  expect(ids(false)).toEqual([...OFFERED])
  expect(added.find((skill) => skill.id === "nus-mode")).toMatchObject({
    name: "nus-mode",
    description:
      "Builds software to a senior engineer's bar. Use when asked for nus-mode, or when the project's AGENTS.md turns it on.",
    path: join(MODE_FOLDER, "SKILL.md"),
    content: CONTENT,
  })
})

test("puts nus-mode back once a summary drops it, only in a session that loaded it", async () => {
  const { request, skillCall } = await start()
  expect(await request("a", "summary")).toEqual([])
  await skillCall("a", "error")
  expect(await request("a", "summary")).toEqual([])
  await skillCall("a", "completed")
  expect(await request("a", BODY)).toEqual([])
  expect(await request("a", "summary")).toEqual([RELOAD])
  expect(await request("b", "summary")).toEqual([])
})

test("puts nus-mode back in a session whose user invoked it", async () => {
  const { request, prompt } = await start()
  await prompt("a")
  expect(await request("a", "summary")).toEqual([RELOAD])
  expect(await request("b", "summary")).toEqual([])
})

test.each([
  ["no skills folder", async () => {}, "skills is unreadable"],
  [
    "a skill folder with no SKILL.md",
    async (skills: string) => void (await mkdir(join(skills, "x"), { recursive: true })),
    "x/SKILL.md is missing",
  ],
  [
    "a SKILL.md with no frontmatter",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "# x\n")
    },
    "x/SKILL.md has no frontmatter",
  ],
  [
    "a SKILL.md that is not UTF-8",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), new Uint8Array([0xff, 0xfe]))
    },
    "x/SKILL.md is not UTF-8",
  ],
  [
    "a SKILL.md that names no skill",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\ndescription: d\n---\n")
    },
    "x/SKILL.md names no skill or description",
  ],
  [
    "a SKILL.md that names no description",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: x\n---\n")
    },
    "x/SKILL.md names no skill or description",
  ],
  [
    "a SKILL.md whose frontmatter is not YAML",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: [x\n---\n")
    },
    "x/SKILL.md holds frontmatter that is not YAML",
  ],
  [
    "a symlinked skill folder",
    async (skills: string) => {
      await mkdir(join(skills, "..", "elsewhere"), { recursive: true })
      await mkdir(skills)
      await symlink(join(skills, "..", "elsewhere"), join(skills, "x"))
    },
    "skills/x is a symlink",
  ],
  [
    "no nus-mode",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: x\ndescription: d\n---\n")
    },
    "nus-mode/SKILL.md is missing",
  ],
])("refuses an install with %s", async (_, build, message) => refuses(build, message))

// Root reads a file whatever its mode, so this case cannot fail there:
// https://man7.org/linux/man-pages/man7/capabilities.7.html (CAP_DAC_OVERRIDE)
test.skipIf(process.getuid?.() === 0)(
  "refuses an install with a SKILL.md that cannot be read",
  async () =>
    refuses(async (skills) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: x\ndescription: d\n---\n")
      await chmod(join(skills, "x", "SKILL.md"), 0o000)
    }, "x/SKILL.md cannot be read"),
)

async function refuses(build: (skills: string) => Promise<void>, message: string) {
  const { root, setup } = await brokenInstall(build)
  try {
    await expect(start(setup)).rejects.toThrow(message)
    await expect(start(setup)).rejects.toThrow("reinstall the nustack plugin")
  } finally {
    await rm(root, { recursive: true })
  }
}
