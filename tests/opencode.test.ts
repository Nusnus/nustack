/**
 * The OpenCode plugin's promises: it registers every skill folder by its frontmatter's name and description, hides
 * the principle and language skills from the model, disposes of what it registered once the host stops it, puts
 * nus-mode back once a summary drops it, only in a session that loaded it, and refuses a broken install by name. It
 * sits at tests/opencode.test.ts rather than mirroring the plugin's path, since tests/ holds this one test, and a
 * tests/plugin/ folder would add a package of one module, which plugin/skills/principle-layout/SKILL.md rules out.
 */
import { expect, test } from "bun:test"
import { once } from "node:events"
import { chmod, cp, mkdir, mkdtemp, rm, symlink, writeFile } from "node:fs/promises"
import { createServer } from "node:net"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
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
type Message = Request["messages"][number]
type Executed = Input<typeof toolHook<"execute.after">>
type Callbacks = {
  prompt?: (input: Prompt) => Promise<void> | void
  context?: (input: Request) => Promise<void> | void
  "execute.after"?: (input: Executed) => Promise<void> | void
}

// Makes a skills folder, and returns what stops anything its removal leaves running, such as a socket's server.
type Build = (skills: string) => Promise<void | (() => Promise<void>)>

const PLUGIN = join(import.meta.dirname, "..", "plugin")
const MODE_FOLDER = join(PLUGIN, "skills", "nus-mode")
const BODY = contentOf(await Bun.file(join(MODE_FOLDER, "SKILL.md")).text()).trim()
const RELOAD = `${BODY}\n\nBase directory for this skill: ${MODE_FOLDER}`
const HOST_PROMPT = "the host's own system prompt"
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

async function start(setup = plugin.setup, storage = new Map<string, Json>()) {
  const added: Skill.Info[] = []
  const hooks: Callbacks = {}
  // A disposal and a write to the storage each take effect a turn of the event loop after the call, as a host's may,
  // so the tests fail a plugin that goes on before one it does not await.
  const turn = () => Bun.sleep(0)
  // A registration of its own for each one the plugin makes, which counts the times the plugin disposes of it.
  const registrations: { disposals: number }[] = []
  const registration = () => {
    const made = { disposals: 0 }
    registrations.push(made)
    return {
      dispose: async () => {
        await turn()
        made.disposals++
      },
    }
  }
  const register = async (name: keyof Callbacks, callback: never) => {
    hooks[name] = callback
    return registration()
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
        return registration()
      },
    },
    session: { hook: register as Context["session"]["hook"] },
    tool: { hook: register as Context["tool"]["hook"] },
    storage: {
      get: async (key: string) => storage.get(key),
      set: async (key: string, value: Json) => {
        await turn()
        storage.set(key, value)
      },
    },
  } satisfies Used
  const stop = await setup(context as Used as Context)
  // Sends a request whose messages are the given ones, a string as a user's text, and returns what the plugin put
  // after the host's system prompt.
  const request = async (session: string, ...messages: (string | Message)[]) => {
    const event = {
      sessionID: session as Request["sessionID"],
      agent: "build" as Request["agent"],
      model: { id: "claude", providerID: "anthropic" } as Request["model"],
      system: [{ type: "text", text: HOST_PROMPT }] as Request["system"],
      messages: messages.map(
        (message): Message =>
          typeof message === "string"
            ? { role: "user", content: [{ type: "text", text: message }] }
            : message,
      ),
      options: {},
      tools: {},
    } satisfies Request
    await hooks.context?.(event)
    const [first, ...put] = event.system.map((part) => part.text)
    expect(first).toBe(HOST_PROMPT)
    return put
  }
  const toolCall = async (
    session: string,
    status: Executed["status"],
    tool: string,
    input: unknown,
  ) => {
    const call = {
      tool,
      sessionID: session as Executed["sessionID"],
      agent: "build" as Executed["agent"],
      messageID: "m" as Executed["messageID"],
      id: "c" as Executed["id"],
      input,
    }
    // Tool.Error is a class of OpenCode's schema package, which nustack does not depend on.
    await hooks["execute.after"]?.(
      status === "completed"
        ? { ...call, status, result: {} }
        : { ...call, status, error: {} as Extract<Executed, { status: "error" }>["error"] },
    )
  }
  // Sends a prompt that invokes the given skills, and one with no skills key where it is given no list.
  const prompt = async (session: string, skills?: string[]) =>
    hooks.prompt?.({
      sessionID: session as Prompt["sessionID"],
      messageID: "m" as Prompt["messageID"],
      prompt: {
        text: "go",
        ...(skills && { skills: skills.map((id) => ({ id: id as Skill.ID })) }),
      },
      delivery: "queue",
    })
  const disposals = () => registrations.map((made) => made.disposals)
  return { added, request, toolCall, prompt, storage, stop, disposals }
}

test.each([
  ["no skills folder", async () => {}, /\/skills is unreadable \(.+\)/],
  [
    "a symlinked skill folder",
    async (skills: string) => {
      await mkdir(join(skills, "..", "elsewhere"), { recursive: true })
      await mkdir(skills)
      await symlink(join(skills, "..", "elsewhere"), join(skills, "x"))
    },
    "/skills/x is a symlink",
  ],
  [
    "no nus-mode",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: x\ndescription: d\n---\n")
      // A plain file beside the skill folders, as an operating system leaves one, is no skill.
      await writeFile(join(skills, ".DS_Store"), "")
      // A SKILL.md with CRLF line endings, as a vendored skill holds where its upstream wrote them, is a skill.
      await mkdir(join(skills, "y"))
      await writeFile(join(skills, "y", "SKILL.md"), "---\r\nname: y\r\ndescription: d\r\n---\r\n")
      // A socket, as a running tool leaves one, is no skill either. It lasts while its server listens.
      const server = createServer().listen(join(skills, "z.sock"))
      await once(server, "listening")
      return async () => void (await once(server.close(), "close"))
    },
    "/skills/nus-mode/SKILL.md is missing",
  ],
])("refuses an install with %s", async (_, build, message) => refuses(build, message))

test("registers every skill folder, hiding the principles and language skills, and disposes of each registration", async () => {
  const { added, stop, disposals } = await start()
  const ids = (hidden: boolean) =>
    added
      .filter((skill) => skill.autoinvoke !== hidden)
      .map((skill): string => skill.id)
      .sort()
  expect(ids(true)).toEqual([...HIDDEN])
  expect(ids(false)).toEqual([...OFFERED])
  expect(Object.fromEntries(added.map(({ id, path, content }) => [id, { path, content }]))).toEqual(
    await registered(),
  )
  // Its cleanup, and nothing before it, disposes of each registration once: the skills and the three hooks.
  expect(disposals()).toEqual([0, 0, 0, 0])
  await stop()
  expect(disposals()).toEqual([1, 1, 1, 1])
})

test("registers each skill by its frontmatter's name and description, not its folder's name", async () =>
  installed(
    async (skills) => {
      await mkdir(join(skills, "nus-mode"), { recursive: true })
      await writeFile(
        join(skills, "nus-mode", "SKILL.md"),
        "---\nname: nus-mode\ndescription: m\n---\n",
      )
      await mkdir(join(skills, "x"))
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: y\ndescription: d\n---\n")
    },
    async (setup) => {
      const { added } = await start(setup)
      expect(added.map(({ id, name, description }) => ({ id, name, description }))).toEqual(
        expect.arrayContaining([
          { id: "nus-mode", name: "nus-mode", description: "m" },
          { id: "x", name: "y", description: "d" },
        ]),
      )
      expect(added).toHaveLength(2)
    },
  ))

test("puts nus-mode back in a session whose user invoked it", async () => {
  const { request, prompt, storage } = await start()
  await prompt("a", ["nus-mode"])
  await prompt("c", ["defuddle", "nus-mode", "knap"])
  await prompt("d", ["defuddle", "knap"])
  await prompt("e", [])
  await prompt("f")
  // A later prompt that invokes another skill leaves the session's mark.
  await prompt("a", ["defuddle"])
  expect(await request("a", "summary")).toEqual([RELOAD])
  expect(await request("b", "summary")).toEqual([])
  expect(await request("c", "summary")).toEqual([RELOAD])
  expect(await request("d", "summary")).toEqual([])
  expect(await request("e", "summary")).toEqual([])
  expect(await request("f", "summary")).toEqual([])
  // A session keeps its mark across a start of the plugin on the same storage.
  const again = await start(plugin.setup, storage)
  expect(await again.request("a", "summary")).toEqual([RELOAD])
  expect(await again.request("b", "summary")).toEqual([])
  // A start on another storage holds no mark of that session.
  expect(await (await start()).request("a", "summary")).toEqual([])
})

test("puts nus-mode back once a summary drops it, only in a session that loaded it", async () => {
  const { request, toolCall, storage } = await start()
  expect(await request("a", "summary")).toEqual([])
  await toolCall("a", "error", "skill", { id: "nus-mode" })
  expect(await request("a", "summary")).toEqual([])
  await toolCall("a", "completed", "skill", { id: "nus-mode" })
  // A later call that loads another skill leaves the session's mark.
  await toolCall("a", "completed", "skill", { id: "defuddle" })
  await toolCall("c", "completed", "skill", { id: "defuddle" })
  await toolCall("c", "completed", "read", { id: "nus-mode" })
  // A call with no input, which OpenCode's type for a tool call allows.
  await toolCall("c", "completed", "skill", undefined)
  expect(await request("a", BODY)).toEqual([])
  expect(await request("a", "go", `Loaded:\n${BODY}\n`, "go on")).toEqual([])
  // The skill tool's result, which holds nus-mode's text in a session that loaded it by the tool.
  const result: Message = {
    role: "tool",
    content: [
      { type: "tool-result", id: "c", name: "skill", result: { type: "text", value: BODY } },
    ],
  }
  expect(await request("a", "go", result, "go on")).toEqual([])
  expect(await request("a", "summary")).toEqual([RELOAD])
  expect(await request("b", "summary")).toEqual([])
  expect(await request("c", "summary")).toEqual([])
  // A session keeps the mark a tool call set across a start of the plugin on the same storage.
  const again = await start(plugin.setup, storage)
  expect(await again.request("a", "summary")).toEqual([RELOAD])
  expect(await again.request("c", "summary")).toEqual([])
  // A start on another storage holds no mark of that session.
  expect(await (await start()).request("a", "summary")).toEqual([])
})

test.each([
  [
    "a skill folder with no SKILL.md",
    async (skills: string) => void (await mkdir(join(skills, "x"), { recursive: true })),
    "/skills/x/SKILL.md is missing",
  ],
  [
    "a folder in place of SKILL.md",
    async (skills: string) =>
      void (await mkdir(join(skills, "x", "SKILL.md"), { recursive: true })),
    /\/skills\/x\/SKILL\.md cannot be read \(.+\)/,
  ],
  [
    "a SKILL.md that is not UTF-8",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), new Uint8Array([0xff, 0xfe]))
    },
    "/skills/x/SKILL.md is not UTF-8",
  ],
  [
    "a SKILL.md with no frontmatter",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "# x\n")
    },
    "/skills/x/SKILL.md has no frontmatter",
  ],
  [
    "a SKILL.md with no frontmatter at its start",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "# x\n---\nname: x\ndescription: d\n---\n")
    },
    "/skills/x/SKILL.md has no frontmatter",
  ],
  [
    "a SKILL.md whose frontmatter is not YAML",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: [x\n---\n")
    },
    /\/skills\/x\/SKILL\.md holds frontmatter that is not YAML \(.+\)/,
  ],
  [
    "a SKILL.md whose frontmatter holds no field",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\n# x\n---\n")
    },
    "/skills/x/SKILL.md names no skill or description",
  ],
  [
    "a SKILL.md that names no skill",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\ndescription: d\n---\n")
    },
    "/skills/x/SKILL.md names no skill or description",
  ],
  [
    "a SKILL.md that names no description",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: x\n---\n")
    },
    "/skills/x/SKILL.md names no skill or description",
  ],
  [
    "a SKILL.md whose name is not a string",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: 5\ndescription: d\n---\n")
    },
    "/skills/x/SKILL.md names no skill or description",
  ],
  [
    "a SKILL.md whose description is not a string",
    async (skills: string) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: x\ndescription: 5\n---\n")
    },
    "/skills/x/SKILL.md names no skill or description",
  ],
])("refuses an install with %s", async (_, build, message) => refuses(build, message))

// Root reads a file whatever its permissions, so no SKILL.md is unreadable to it.
test.skipIf(process.getuid?.() === 0)(
  "refuses an install with a SKILL.md it may not read",
  async () =>
    refuses(async (skills) => {
      await mkdir(join(skills, "x"), { recursive: true })
      await writeFile(join(skills, "x", "SKILL.md"), "---\nname: x\ndescription: d\n---\n")
      await chmod(join(skills, "x", "SKILL.md"), 0)
    }, /\/skills\/x\/SKILL\.md cannot be read \(.*EACCES.*\)/),
)

async function refuses(build: Build, message: string | RegExp) {
  await installed(build, async (setup) => {
    await expect(start(setup)).rejects.toThrow(message)
    await expect(start(setup)).rejects.toThrow("reinstall the nustack plugin")
  })
}

// Runs the check on a copy of the plugin beside the skills folder the build makes.
async function installed(build: Build, check: (setup: typeof plugin.setup) => Promise<void>) {
  // An import reads a relative path with no leading ./ as a package's name, so this makes a relative TMPDIR absolute:
  // https://nodejs.org/api/esm.html#import-specifiers
  const root = await mkdtemp(join(resolve(tmpdir()), "nustack-"))
  try {
    await cp(join(PLUGIN, "opencode.ts"), join(root, "opencode.ts"))
    const undo = await build(join(root, "skills"))
    try {
      await check((await import(join(root, "opencode.ts"))).default.setup)
    } finally {
      await undo?.()
    }
  } finally {
    await rm(root, { recursive: true })
  }
}

// What the plugin registers of each skill: its SKILL.md's path, and the text below that file's frontmatter. The test
// that compares it reads the files, so a skill folder that is gone fails that test alone, but for nus-mode's, whose
// text this file reads as it loads.
async function registered() {
  return Object.fromEntries(
    await Promise.all(
      [...HIDDEN, ...OFFERED].map(async (id) => {
        const path = join(PLUGIN, "skills", id, "SKILL.md")
        return [id, { path, content: contentOf(await Bun.file(path).text()) }]
      }),
    ),
  )
}

// The text below a SKILL.md's frontmatter, which the plugin's own pattern finds: FRONTMATTER in plugin/opencode.ts,
// without its capture group.
function contentOf(file: string) {
  return file.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "")
}
