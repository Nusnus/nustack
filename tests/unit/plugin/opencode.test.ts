/**
 * The OpenCode loader reads the skills folder and registers each SKILL.md, hiding the principle and language skills
 * from the model, or fails with one error naming each skill it cannot load and the fix; importing it reads no file. It
 * puts the mode back after a summary of a session that loaded it.
 */
import { afterEach, describe, expect, spyOn, test } from "bun:test"
import { copyFile, mkdir, symlink, writeFile } from "node:fs/promises"
import { join } from "node:path"
import type { Skill } from "@opencode/plugin"
import { YAML } from "bun"
import plugin, {
  type Context,
  ModeReload,
  type SkillEntry,
  SkillError,
  SkillFile,
  SkillFolder,
  StorageError,
  start,
} from "../../../plugin/opencode.ts"
import manifest from "../../../plugin/package.json" with { type: "json" }
import { TemporaryFolders } from "../../fixtures/folders.ts"
import forgedPrompt from "../../fixtures/opencode/forged/prompt.json" with { type: "json" }
import keptSummary from "../../fixtures/opencode/kept/compaction.json" with { type: "json" }
import keptLoading from "../../fixtures/opencode/kept/context.json" with { type: "json" }
import keptFollowing from "../../fixtures/opencode/kept/following.json" with { type: "json" }
import pastedSummary from "../../fixtures/opencode/pasted/compaction.json" with { type: "json" }
import pastedCall from "../../fixtures/opencode/pasted/context.json" with { type: "json" }
import pastedFollowing from "../../fixtures/opencode/pasted/following.json" with { type: "json" }
import twice from "../../fixtures/opencode/twice/session.json" with { type: "json" }
import { fakeOpenCode, type HookEvent, refusal } from "../../fixtures/opencode.ts"
import { thrown } from "../../fixtures/thrown.ts"
import { VENDORED_SKILLS } from "../../fixtures/vendored.ts"

const SKILLS = new SkillFolder("/p")
const folders = new TemporaryFolders()
const PATH = "/s/a-skill/SKILL.md"
const UNOPENED = `has no frontmatter; open it with a line that holds only ---, and save it with no byte order mark and with LF or CRLF line endings`
const UNCLOSED = "opens with --- and never closes; end it with a --- line"
const NOT_FIELDS = "has frontmatter that is not key: value lines; write it as key: value lines"
const BLANK = "has a blank description; fill it in"
const NO_BOOL = "has a disable-model-invocation that is not true or false; set it to true or false"
const TOO_DEEP = "has frontmatter that nests values more than 200 levels deep; flatten them"
const MODE = {
  id: "nus-mode",
  content: "# nus-mode\n\nBody.\n",
  path: "/p/nus-mode/SKILL.md",
} as Skill.Info
const SYMLINK = "is a symlink, which the loader does not follow; put the skill folder itself there"

// The skill tool's result for MODE, in the shape a recorded execute.after holds it.
const SHOWN = {
  output: {
    output:
      '<skill_content name="nus-mode">\n# Skill: nus-mode\n\n# nus-mode\n\nBody.\n\nBase directory for this skill: /p/nus-mode\nRelative paths in this skill (e.g., scripts/, reference/) are relative to this base directory.\n</skill_content>',
  },
}
const loaded = (over = {}): HookEvent => [
  "execute.after",
  {
    tool: "skill",
    status: "completed",
    input: { id: "nus-mode" },
    result: SHOWN,
    ...over,
  },
]
const invoked = (id = "nus-mode"): HookEvent => ["prompt", { prompt: { skills: [{ id }] } }]
const request = (messages: object[] = []): HookEvent => ["context", { system: [], messages }]
const summary = (messages: object[] = []): HookEvent => ["compaction", { messages }]
const SUMMARIZED = summary()
// Messages that hold MODE's whole text, as a request's messages hold a skill the session loaded.
const SHOWING = [{ role: "tool", content: [{ result: SHOWN }] }]
// Each recorded event holds one request an OpenCode hook received, as a recording plugin wrote it down; the copy
// takes the system text a hook adds.
const replayed = ({ hook, request }: { hook: string; request: object }): HookEvent => [
  hook,
  structuredClone(request),
]

afterEach(() => folders.clear())

/** A SKILL.md loads into the skill OpenCode registers, or fails naming its file and the fix. */
describe("SkillFile", () => {
  test("hands out a file and a skill that never change", () => {
    const file = SkillFile.decode(
      PATH,
      new TextEncoder().encode("---\nname: a\ndescription: A.\n---\n"),
    )
    expect([Object.isFrozen(file), Object.isFrozen(file.info("a"))]).toEqual([true, true])
  })

  test("decodes UTF-8, a byte order mark kept for split to refuse, and refuses other bytes", async () => {
    const text = "\ufeff---\nname: café\n---\n"
    expect(SkillFile.decode(PATH, new TextEncoder().encode(text)).text).toBe(text)
    const decoded = thrown(() => SkillFile.decode(PATH, Uint8Array.of(0x2d, 0xff)))
    expect(await decoded).toEqual(refusal(PATH, "is not valid UTF-8; save it as UTF-8"))
  })

  test.each([
    ['name: b\ndescription: "A: \\"q\\"."\n---\n', { id: "a", name: "b", description: 'A: "q".' }],
    ["name: a\ndescription: A.\n---", { content: "", autoinvoke: true, path: PATH }],
    ["name: a\ndescription: x---\n---\n# A\n", { description: "x---", content: "# A\n" }],
    ["name: a\ndescription: A.\n---\n# A\n---\rX\n", { content: "# A\n---\rX\n" }],
    ["name: a\ndescription: A.\n---\n\n# A\n", { content: "\n# A\n" }],
    ["\rname: a\r\ndescription: A.\r\n---\r\n# A\r\n", { name: "a", content: "# A\r\n" }],
    ["name: a\ndescription: a\r\r\n b\n---\n", { description: "a\nb" }],
    ["name: a\ndescription: A.\ndisable-model-invocation: true # x\n---\n", { autoinvoke: false }],
    ["name: a\ndescription: A.\ndisable-model-invocation: True\n---\n", { autoinvoke: false }],
    ["name: a\ndescription: A.\ndisable-model-invocation: false\n---\n", { autoinvoke: true }],
  ])("reads ---\\n%j", (text, expected) => {
    expect(new SkillFile(PATH, `---\n${text}`).info("a")).toMatchObject(expected)
  })

  test.each([
    ["\ufeff---\nname: a\n---\n", "opens with a byte order mark; save it without one"],
    ["---\rname: a\r---\r", "has lines that end in a bare CR; save it with LF line endings"],
    ["# A\n", UNOPENED],
    ["# A\n---\nname: a\ndescription: A.\n---\n", UNOPENED],
    ["--- \nname: a\n---\n", UNOPENED],
    ["---\nname: a\n", UNCLOSED],
    ["---", UNCLOSED],
    ["---\nname: a\n---x\n", UNCLOSED],
    ["---\nname: a\n--- \n", UNCLOSED],
    ["---\n- a\n---\n", NOT_FIELDS],
    ["---\n\n\n---\n", NOT_FIELDS],
    ["---\n7\n---\n", NOT_FIELDS],
    ["---\nname: [a\n---\n", "has frontmatter that is not valid YAML; fix it"],
    ["---\ndescription: A.\n---\n", "has no name in its frontmatter; add one"],
    ["---\n---\n# A\n", "has no name in its frontmatter; add one"],
    ["---\nname: a\n---\n", "has no description in its frontmatter; add one"],
    ["---\nname: 7\ndescription: A.\n---\n", "has a name that is not text; write its text"],
    ['---\nname: a\ndescription: " "\n---\n', BLANK],
    ['---\nname: a\ndescription: "\\u200B\\u2060\\x85"\n---\n', BLANK],
    ["---\nname: a\ndescription: A.\ndisable-model-invocation: yes\n---\n", NO_BOOL],
    [
      `---\nname: a\ndescription: A.\nmetadata: ${"[".repeat(200)}${"]".repeat(200)}\n---\n`,
      TOO_DEEP,
    ],
    [
      `---\nname: a\ndescription: A.\nmetadata: [[&x ${"[".repeat(198)}${"]".repeat(198)}]]\nother: *x\n---\n`,
      TOO_DEEP,
    ],
    ["---\nname: a\ndescription: A.\nmetadata: &x [*x]\n---\n", TOO_DEEP],
  ])("refuses %j, naming the fix", async (text, problem) => {
    expect(await thrown(() => new SkillFile(PATH, text).info("a"))).toEqual(refusal(PATH, problem))
  })

  test("reads frontmatter nested 200 levels deep, the most it reads", () => {
    const text = `---\nname: a\ndescription: A.\nmetadata: ${"[".repeat(199)}${"]".repeat(199)}\n---\n`
    expect(new SkillFile(PATH, text).split()[0].get("name")).toBe("a")
  })

  test("reads frontmatter of 4096 characters, the most it reads", () => {
    const text = `---\nname: a\ndescription: ${"A".repeat(4074)}\n---\n`
    expect(new SkillFile(PATH, text).info("a").description).toHaveLength(4074)
  })

  test.each([
    ["4097 characters", () => `name: a\ndescription: ${"A".repeat(4075)}\n`],
    [
      "a quote holding a bracket, then a map 6000 levels deep",
      () => {
        const deepMap = Array.from({ length: 6000 }, (_, at) => `${"  ".repeat(at)}k:`).join("\n")
        return `name: x\ndescription: see "[docs]" here\n${deepMap} 1\n`
      },
    ],
  ])(
    "refuses frontmatter of %s before Bun's YAML parser reads it, naming the fix",
    async (_, frontmatter) => {
      expect(
        await thrown(() => new SkillFile(PATH, `---\n${frontmatter()}---\n`).info("a")),
      ).toEqual(refusal(PATH, "has frontmatter longer than 4096 characters; shorten it"))
    },
  )

  test("reads frontmatter whose apostrophe comes before 201 flow lists, 2 levels deep", () => {
    const lists = Array.from({ length: 201 }, (_, at) => `k${at}: [1]`).join("\n")
    const text = `---\nname: x\ndescription: it's\n${lists}\n---\n`
    expect(new SkillFile(PATH, text).info("x").description).toBe("it's")
  })

  test.each([
    ["a bracket in a comment", "metadata: 1 # [[[\n", 1],
    ["brackets in a block scalar", "metadata: |\n  [[[\n", "[[[\n"],
    ["a '' escape before a bracket", "metadata: 'it''s ]'\n", "it's ]"],
    ['a \\" escape before a bracket', 'metadata: "a \\" ]"\n', 'a " ]'],
    ["brackets in a quoted value over two lines", 'metadata: "a [\n  ]]"\n', "a [ ]]"],
  ])("reads frontmatter whose text holds %s, which nest nothing", (_, field, value) => {
    const text = `---\nname: a\ndescription: A.\n${field}---\n`
    expect(new SkillFile(PATH, text).split()[0].get("metadata")).toEqual(value)
  })

  test("reads a stack overflow in Bun's YAML parser as frontmatter nested too deep, naming the fix", async () => {
    const parse = spyOn(YAML, "parse").mockImplementation(() => {
      throw new RangeError("Maximum call stack size exceeded.")
    })
    try {
      const file = new SkillFile(PATH, "---\nname: a\ndescription: A.\n---\n")
      expect(await thrown(() => file.info("a"))).toEqual(refusal(PATH, TOO_DEEP))
    } finally {
      parse.mockRestore()
    }
  })

  test.each([
    new RangeError("Invalid array length"),
    new Error("Maximum call stack size exceeded."),
    new TypeError("bug"),
  ])(
    "lets an error of Bun's YAML parser other than a syntax error or a stack overflow through, such as %p",
    async (bug) => {
      const parse = spyOn(YAML, "parse").mockImplementation(() => {
        throw bug
      })
      try {
        const file = new SkillFile(PATH, "---\nname: a\ndescription: A.\n---\n")
        expect(await thrown(() => file.info("a"))).toBe(bug)
      } finally {
        parse.mockRestore()
      }
    },
  )
})

/** The loader reads each entry of a skills folder as its kind needs, or fails naming the folder and the fix. */
describe("SkillFolder.read", () => {
  test("lets the model invoke the mode and the vendored skills alone", async () => {
    const folder = new SkillFolder(join(import.meta.dirname, "../../../plugin/skills"))
    const skills = folder.skills(await folder.read())
    const invocable = skills.flatMap((info) => (info.autoinvoke ? [info.id] : []))
    expect<string[]>(invocable.sort()).toEqual([...VENDORED_SKILLS, "nus-mode"].sort())
  })

  test("refuses a skills folder it cannot read, naming the errno and the fix, with readdir's error as its cause", async () => {
    const folder = join(await folders.make(), "missing")
    const error = await thrown(() => new SkillFolder(folder).read())
    expect(`${error}`).toBe(
      `${refusal(folder, "cannot be read (ENOENT); restore the plugin's skills folder")}`,
    )
    expect(error).toMatchObject({ cause: { code: "ENOENT", path: folder } })
  })

  test("reads each folder's SKILL.md, or the error reading it, and names each symlink and file", async () => {
    const folder = await folders.make()
    await Promise.all(["empty", "valid"].map((name) => mkdir(join(folder, name))))
    await writeFile(join(folder, "valid", "SKILL.md"), "x")
    await writeFile(join(folder, "README.md"), "# Skills\n")
    await symlink(join(folder, "valid"), join(folder, "link"))
    const entries = await new SkillFolder(folder).read()
    expect(entries.toSorted((a, b) => (a.name < b.name ? -1 : 1))).toEqual([
      { name: "README.md", kind: "file" },
      {
        name: "empty",
        kind: "folder",
        error: expect.objectContaining({ code: "ENOENT" }),
      },
      { name: "link", kind: "symlink" },
      { name: "valid", kind: "folder", data: Buffer.from("x") },
    ])
  })
})

/** OpenCode gets every skill the folder's entries hold, or one error, in path order, that lets the user fix them all. */
describe("SkillFolder.skills", () => {
  const VALID = new TextEncoder().encode("---\nname: valid\ndescription: V.\n---\n")

  test("turns each folder's SKILL.md into a skill, and skips files", () => {
    const entries: SkillEntry[] = [
      { name: "valid", kind: "folder", data: VALID },
      { name: "README.md", kind: "file" },
    ]
    expect<string[]>(SKILLS.skills(entries).map((skill) => skill.id)).toEqual(["valid"])
  })

  test("names each SKILL.md it cannot read or decode, and each symlink, by path", async () => {
    const missing = Object.assign(new Error("no such file"), {
      code: "ENOENT",
    })
    const entries: SkillEntry[] = [
      { name: "d-skill", kind: "symlink" },
      { name: "c-skill", kind: "folder", data: Uint8Array.of(0x2d, 0xff) },
      { name: "b-skill", kind: "folder", error: missing },
      { name: "a-skill", kind: "folder", error: "not an Error" },
      { name: "valid", kind: "folder", data: VALID },
    ]
    const unreadable = "give the skill a readable SKILL.md"
    const expected = [
      refusal("/p/a-skill/SKILL.md", `cannot be read (no error code); ${unreadable}`).message,
      refusal("/p/b-skill/SKILL.md", `cannot be read (ENOENT); ${unreadable}`).message,
      refusal("/p/c-skill/SKILL.md", "is not valid UTF-8; save it as UTF-8").message,
      refusal("/p/d-skill", SYMLINK).message,
    ]
    expect(`${await thrown(() => SKILLS.skills(entries))}`).toBe(
      `${new SkillError(expected.join("\n"))}`,
    )
  })

  test("says a read error has no error code unless it is an Error with a string code", async () => {
    const entries: SkillEntry[] = [
      {
        name: "a-skill",
        kind: "folder",
        error: Object.assign(new Error("odd"), { code: 5 }),
      },
      { name: "b-skill", kind: "folder", error: { code: "EACCES" } },
    ]
    const problem = "cannot be read (no error code); give the skill a readable SKILL.md"
    const expected = ["a", "b"].map((id) => refusal(`/p/${id}-skill/SKILL.md`, problem).message)
    expect(`${await thrown(() => SKILLS.skills(entries))}`).toBe(
      `${new SkillError(expected.join("\n"))}`,
    )
  })

  test("keeps each failure as the error's cause, with the error that failed its read", async () => {
    const missing = Object.assign(new Error("no such file"), {
      code: "ENOENT",
    })
    const error = await thrown(() =>
      SKILLS.skills([{ name: "b-skill", kind: "folder", error: missing }]),
    )
    expect(error).toHaveProperty(["cause", "0", "cause"], missing)
  })

  test("passes on, unchanged, an error that is not the loader's own", async () => {
    const bug = new RangeError("a bug")
    const entry: SkillEntry = {
      name: "a",
      kind: "folder",
      get data(): Uint8Array {
        throw bug
      },
    }
    expect(await thrown(() => SKILLS.skills([entry]))).toBe(bug)
  })
})

/**
 * Each agent request of a session that loaded the mode, by the skill tool or its user, gets the mode's text and folder
 * back where its messages lack the mode's whole text, as after a summary; storage keeps the load across a restart. No
 * other session does.
 */
describe("ModeReload", () => {
  async function reloads(events: HookEvent[], opencode = fakeOpenCode(), messages: object[] = []) {
    await new ModeReload(MODE, opencode.context.storage).register(opencode.context)
    for (const event of events) await opencode.run(event)
    const system: { text: string }[] = []
    for (const _request of [1, 2]) await opencode.run(["context", { system, messages }])
    const reload =
      "# nus-mode\n\nBody.\n\nBase directory for this skill: /p/nus-mode\nRelative paths in this skill (e.g., scripts/, reference/) are relative to this base directory."
    return system.filter((part) => part.text === reload).length
  }

  test("gives back the trimmed body, CRLF lines kept, then the mode's folder", () => {
    const skill = {
      ...MODE,
      content: "\n# M\r\nx\r\n",
      path: "/p/nus-mode/SKILL.md",
    } as Skill.Info
    expect(new ModeReload(skill, fakeOpenCode().context.storage).reloadText).toBe(
      "# M\r\nx\n\nBase directory for this skill: /p/nus-mode\nRelative paths in this skill (e.g., scripts/, reference/) are relative to this base directory.",
    )
  })

  test("picks the mode out of the skills", () => {
    const other = { ...MODE, id: "a-skill" } as Skill.Info
    expect(ModeReload.mode(SKILLS, [other, MODE])).toBe(MODE)
  })

  test.each<[string, number, HookEvent[]]>([
    ["a skill tool load", 2, [loaded(), SUMMARIZED]],
    ["a revert that cut the load, with no summary", 2, [loaded()]],
    [
      "a load whose summary was written ahead, from messages that show the mode's text, then swapped in with no hook",
      2,
      [loaded(), summary(SHOWING), request(SHOWING)],
    ],
    [
      "a user's invocation that the next request shows",
      2,
      [invoked(), request(SHOWING), SUMMARIZED],
    ],
    [
      "a user's invocation beside another skill's, that the next request shows",
      2,
      [
        ["prompt", { prompt: { skills: [{ id: "b" }, { id: "nus-mode" }] } }],
        request(SHOWING),
        SUMMARIZED,
      ],
    ],
    ["a user's invocation that the next request lacks", 0, [invoked(), request(), SUMMARIZED]],
    [
      "a user's invocation that a later request shows, after one that lacks it",
      2,
      [invoked(), request(), request(SHOWING), SUMMARIZED],
    ],
    ["a user's invocation that the summary request shows", 2, [invoked(), summary(SHOWING)]],
    ["a user's invocation that the summary request lacks", 0, [invoked(), SUMMARIZED]],
    [
      "a user's invocation that the summary request lacks, before a request that shows the mode's text",
      2,
      [invoked(), SUMMARIZED, request(SHOWING), SUMMARIZED],
    ],
    [
      "a user's invocation, while the mode is due back, that the next requests lack",
      2,
      [loaded(), SUMMARIZED, request(), invoked()],
    ],
    ["no load", 0, [SUMMARIZED]],
    ["a failed skill tool call", 0, [loaded({ status: "error" }), SUMMARIZED]],
    ["another skill's load", 0, [loaded({ input: { id: "b" } }), SUMMARIZED]],
    [
      "a load of a nus-mode from the config's skills folder",
      0,
      [
        loaded({
          result: { output: { output: "# nus-mode\n\nAnother body." } },
        }),
        SUMMARIZED,
      ],
    ],
    ["another tool given the mode's id", 0, [loaded({ tool: "read" }), SUMMARIZED]],
    [
      "a user's invocation of another skill, whose next request shows the mode's text",
      0,
      [invoked("b"), request(SHOWING), SUMMARIZED],
    ],
    [
      "session t's load",
      0,
      [loaded({ sessionID: "t" }), ["compaction", { sessionID: "t", messages: [] }]],
    ],
  ])(
    "after %s, puts the mode in %d of two requests that lack its text",
    async (_case, count, events) => {
      expect(await reloads(events)).toBe(count)
    },
  )

  test.each<[string, number, HookEvent[]]>([
    [
      "a user's invocation, while the mode is due back, that the next request shows",
      0,
      [loaded(), SUMMARIZED, request(), invoked(), request(SHOWING)],
    ],
    [
      "a user's invocation, while the mode is due back, that a later request shows, after one that lacks it",
      0,
      [loaded(), SUMMARIZED, request(), invoked(), request(), request(SHOWING)],
    ],
    [
      "a user's invocation right after a summary, that a later request shows, after one that lacks it",
      0,
      [loaded(), SUMMARIZED, invoked(), request(), request(SHOWING)],
    ],
    ["no summary since the load", 0, [loaded()]],
    ["a load again after the summary", 0, [loaded(), SUMMARIZED, loaded()]],
  ])(
    "after %s, puts the mode in %d of two requests that show its text",
    async (_case, count, events) => {
      expect(await reloads(events, fakeOpenCode(), SHOWING)).toBe(count)
    },
  )

  test("gives nothing to a request whose messages hold a CRLF mode's whole text", async () => {
    const mode = {
      ...MODE,
      content: "# nus-mode\r\n\r\nBody.\r\n",
    } as Skill.Info
    const opencode = fakeOpenCode(new Map([["nus-mode/s", "loaded"]]))
    await new ModeReload(mode, opencode.context.storage).register(opencode.context)
    const system: { text: string }[] = []
    const messages = [
      {
        role: "tool",
        content: [{ result: { value: "# nus-mode\r\n\r\nBody." } }],
      },
    ]
    await opencode.run(["context", { system, messages }])
    expect(system).toEqual([])
  })

  test("keeps a session's load across a restart", async () => {
    const { stored } = fakeOpenCode()
    await reloads([loaded()], fakeOpenCode(stored))
    expect(await reloads([SUMMARIZED], fakeOpenCode(stored))).toBe(2)
  })

  test("refuses a value the reload never stores, at a summary and at a request", async () => {
    const opencode = fakeOpenCode(new Map([["nus-mode/s", "loaded/s"]]))
    await new ModeReload(MODE, opencode.context.storage).register(opencode.context)
    const error = new StorageError(
      'the plugin\'s storage holds "loaded/s" under nus-mode/s, a value the loader never stores; continue in a new session, whose state starts empty',
    )
    expect(await thrown(() => opencode.run(SUMMARIZED))).toEqual(error)
    expect(await thrown(() => opencode.run(["context", { system: [], messages: [] }]))).toEqual(
      error,
    )
  })

  test("stores a load once under the session's key, however many requests and summaries follow", async () => {
    const opencode = fakeOpenCode()
    const stored: unknown[] = []
    const storage: Context["storage"] = {
      get: opencode.context.storage.get,
      set: async (key, value) => {
        stored.push([key, value])
        await opencode.context.storage.set(key, value)
      },
    }
    await new ModeReload(MODE, storage).register(opencode.context)
    const next = request()
    for (const event of [loaded(), next, next, SUMMARIZED, next, next]) await opencode.run(event)
    expect(stored).toEqual([["nus-mode/s", "loaded"]])
  })

  test("adds the mode once when a selection lands between a loaded session's read and its check", async () => {
    const opencode = fakeOpenCode(new Map([["nus-mode/s", "loaded"]]))
    const held = holdFirstRead(opencode)
    await new ModeReload(MODE, held.storage).register(opencode.context)
    const first: { text: string }[] = []
    const reading = opencode.run(["context", { system: first, messages: [] }])
    await opencode.run(invoked())
    held.release()
    await reading
    const next: { text: string }[] = []
    await opencode.run(["context", { system: next, messages: SHOWING }])
    expect([first.length, next.length]).toEqual([1, 0])
  })

  test("keeps a selection that lands while a summary that lacks the mode's text reads", async () => {
    const opencode = fakeOpenCode(new Map([["nus-mode/s", "selected"]]))
    const held = holdFirstRead(opencode)
    await new ModeReload(MODE, held.storage).register(opencode.context)
    const summarizing = opencode.run(SUMMARIZED)
    await opencode.run(invoked())
    held.release()
    await summarizing
    for (const event of [request(SHOWING), SUMMARIZED]) await opencode.run(event)
    const system: { text: string }[] = []
    for (const _request of [1, 2]) await opencode.run(["context", { system, messages: [] }])
    expect(system.length).toBe(2)
  })

  test("settles a selection whose prompt read the state before a load stored it", async () => {
    const opencode = fakeOpenCode()
    const held = holdFirstRead(opencode)
    await new ModeReload(MODE, held.storage).register(opencode.context)
    const prompting = opencode.run(invoked())
    await opencode.run(loaded())
    held.release()
    await prompting
    for (const event of [request(SHOWING), SUMMARIZED]) await opencode.run(event)
    const system: { text: string }[] = []
    for (const _request of [1, 2]) await opencode.run(["context", { system, messages: [] }])
    expect([opencode.stored.get("nus-mode/s"), system.length]).toEqual(["loaded", 2])
  })

  // The reload learns of a load only from its event, so no later request can store it again.
  test("fails the tool hook with the storage's error when it cannot store a load", async () => {
    const opencode = fakeOpenCode()
    const failure = new Error("storage is full")
    const storage: Context["storage"] = {
      get: opencode.context.storage.get,
      set: () => Promise.reject(failure),
    }
    await new ModeReload(MODE, storage).register(opencode.context)
    expect(await thrown(() => opencode.run(loaded()))).toBe(failure)
  })

  /** In sessions OpenCode recorded, the mode comes back once a summary drops its whole text, and only after a load. */
  describe("in recorded sessions", () => {
    // A recorded load's mode, and the text OpenCode's skill tool showed for it: the body after the tool's heading, then
    // the base-directory note through its line on relative paths.
    function shown(messages: readonly object[]): {
      mode: Skill.Info
      text: string
      result: object
    } {
      const [{ result }] = Object(
        messages.find((message) => Object(message).role === "tool"),
      ).content
      const match =
        /(?<=\n\n)([\s\S]*)\n\nBase directory for this skill: (.*)\n.* are relative to this base directory\./.exec(
          String(result.value),
        )
      if (match === null)
        throw new Error("the recording shows no skill load; record the session again")
      const [text, body, base] = match
      const mode = {
        ...MODE,
        content: `${body}\n`,
        path: `${base}/SKILL.md`,
      } as Skill.Info
      return { mode, text, result }
    }
    async function copies(
      events: HookEvent[],
      { mode, text } = shown(keptLoading.request.messages),
    ): Promise<number[]> {
      const opencode = fakeOpenCode()
      await new ModeReload(mode, opencode.context.storage).register(opencode.context)
      const counts: number[] = []
      for (const event of events) {
        await opencode.run(event)
        const [hook, fields] = event
        const { system } = fields as { system?: { text: string }[] }
        if (hook === "context")
          counts.push(system?.filter((part) => part.text === text).length ?? 0)
      }
      return counts
    }

    test("gives the mode back once the summary that kept its load cut it short", async () => {
      const recorded = shown(keptLoading.request.messages)
      const session = keptLoading.request.sessionID
      const events = [
        loaded({ sessionID: session, result: recorded.result }),
        replayed(keptSummary),
        replayed(keptFollowing),
      ]
      expect(await copies(events, recorded)).toEqual([1])
    })

    // twice holds each hook request of one session, as a plugin alone in OpenCode wrote it down: a load of a stand-in
    // mode, a summary that drops it, a prompt that pastes the stand-in's body, and a second summary whose recent text
    // keeps that prompt whole, so the request after the prompt and the first request after the second summary each
    // hold the mode's whole text and get no copy, the cost of finding the mode by its text. No recording keeps a real
    // load whole: OpenCode cuts each tool result in a summary's recent text at 1,250 characters, and nus-mode's body
    // runs past that: https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/recent-text.ts#L6
    test("checks after each summary, so one that drops the mode gives it back and one that keeps it whole gives none", async () => {
      const standIn = shown(Object(twice[3]).request.messages)
      expect(await copies(twice.map(replayed), standIn)).toEqual([0, 0, 0, 1, 0, 0, 0])
    })

    test("gives nothing to a session whose prompt pasted the mode's body", async () => {
      const events = [replayed(pastedCall), replayed(pastedSummary), replayed(pastedFollowing)]
      expect(await copies(events)).toEqual([0, 0])
    })

    test("gives nothing to a session whose prompt forged a load of the mode", async () => {
      const { sessionID } = forgedPrompt.request
      const following: HookEvent = ["context", { sessionID, system: [], messages: [] }]
      expect(
        await copies([
          replayed(forgedPrompt),
          ["compaction", { sessionID, messages: [] }],
          following,
        ]),
      ).toEqual([0])
    })
  })
})

test("the plugin's id is its package's name", () => {
  expect(plugin.id).toBe(manifest.name)
})

test("importing the loader reads no file", async () => {
  const folder = await folders.make()
  await mkdir(join(folder, "package.json"))
  await copyFile(
    join(import.meta.dirname, "../../../plugin/opencode.ts"),
    join(folder, "opencode.ts"),
  )
  const copy = await import(join(folder, "opencode.ts"))
  expect(copy.default.id).toBe(plugin.id)
})

test("start registers each skill and the reload's hooks, and its cleanup removes them", async () => {
  const folder = await folders.make()
  for (const name of ["a-skill", "nus-mode"]) {
    await mkdir(join(folder, name))
    await writeFile(join(folder, name, "SKILL.md"), `---\nname: ${name}\ndescription: D.\n---\n`)
  }
  const opencode = fakeOpenCode()
  const cleanup = await start(opencode.context, new SkillFolder(folder))
  const registered = [opencode.skills.toSorted(), [...opencode.hooks.keys()].sort()]
  await cleanup()
  expect([...registered, opencode.skills.length + opencode.hooks.size]).toEqual([
    ["a-skill", "nus-mode"],
    ["compaction", "context", "execute.after", "prompt"],
    0,
  ])
})

test("start fails without the mode, naming its SKILL.md and the fix", async () => {
  const folder = await folders.make()
  await mkdir(join(folder, "a-skill"))
  await writeFile(join(folder, "a-skill", "SKILL.md"), "---\nname: a-skill\ndescription: D.\n---\n")
  const error = refusal(join(folder, "nus-mode", "SKILL.md"), "is missing; restore the mode")
  expect(await thrown(() => start(fakeOpenCode().context, new SkillFolder(folder)))).toEqual(error)
})

function holdFirstRead(opencode: ReturnType<typeof fakeOpenCode>): {
  storage: Context["storage"]
  release: () => void
} {
  let release = () => {}
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  let holding = true
  const storage: Context["storage"] = {
    get: async (key) => {
      const value = opencode.stored.get(key)
      if (holding) {
        holding = false
        await held
      }
      return value
    },
    set: opencode.context.storage.set,
  }
  return { storage, release: () => release() }
}
