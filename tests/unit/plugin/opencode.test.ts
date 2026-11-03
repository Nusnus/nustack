/**
 * The OpenCode loader reads each skill folder into the skill OpenCode registers, registers every skill the plugin ships
 * with only the mode left for the model to invoke, and fails with one error naming each skill folder or SKILL.md it
 * cannot load, or the skills folder it cannot read. It puts the mode back in a session's context once a summarization
 * drops it.
 */
import { afterEach, describe, expect, test } from "bun:test"
import { chmod, mkdir, readdir, readFile, symlink, writeFile } from "node:fs/promises"
import { join } from "node:path"
import type { Skill } from "@opencode/plugin"
import plugin, {
  type ModelRequest,
  ModeReload,
  SkillFile,
  SkillFolder,
  type UserPrompt,
} from "../../../plugin/opencode.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"
import { FakeRegistry } from "../../fixtures/registry.ts"
import { FakeSession, FakeStorage } from "../../fixtures/session.ts"

const SKILLS = join(import.meta.dirname, "..", "..", "..", "plugin", "skills")

/** One request OpenCode passed a session hook, as the recording plugin wrote it down. */
interface Recorded<Request = ModelRequest> {
  readonly hook: Request extends UserPrompt ? "prompt" : "context" | "compaction"
  readonly request: Request
}

// Each folder holds one OpenCode session under an agent with a one-line prompt and Code Mode denied, so each request
// carries little but what the reload reads. Each file holds the fields the loader reads of one request a session hook
// received, recorded by a plugin loaded beside the loader. The loaded and unloaded sessions ran against the real model,
// the invoked, forged and quoted ones in the smoke tests' OpenCode against tests/fixtures/model.ts.
// The agent loop's request right after the skill tool loaded the mode: the one context request whose messages hold it.
const loading = await recorded("loaded/context")
// The summary request of that session: the one compaction request whose messages hold the mode.
const summary = await recorded("loaded/compaction")
// The session's first request after the summary: its messages are the summary and one prompt, without the mode.
const following = await recorded("loaded/following")
// The summary request of a session that never loaded the mode, and its first request after it.
const unloadedSummary = await recorded("unloaded/compaction")
const unloadedFollowing = await recorded("unloaded/following")
// In one session the user invoked the mode through the prompt endpoint's skills field, as the TUI does: its prompt, and
// the model call that followed. In the other a prompt held the mode's body inside the skill_content envelope an
// invocation shows: its prompt, the model call that followed, and the session's summary request.
const invoking = await recorded<UserPrompt>("invoked/prompt")
const invoked = await recorded("invoked/context")
const forging = await recorded<UserPrompt>("forged/prompt")
const forged = await recorded("forged/context")
const forgedSummary = await recorded("forged/compaction")
// In the quoted session the skill tool loaded another skill whose body quotes the mode inside its skill_content
// envelope: the model call that followed, and the session's summary request.
const quotedCall = await recorded("quoted/context")
const quotedSummary = await recorded("quoted/compaction")
// The mode's body as the recorded session loaded it, between OpenCode's skill heading and its base-directory note. The
// recording ran an older nus-mode, and the reload matches whatever body the loader registered, so the recorded body
// stands in for the shipped one; the smoke tests reload the shipped body in OpenCode itself.
const loaded = String(Object(Object(loading.request.messages[2]).content[0]).result.value)
const MODE: Skill.Info = {
  ...ModeReload.mode(await new SkillFolder(SKILLS).skills()),
  content: loaded.slice(
    loaded.indexOf("\n\n") + 2,
    loaded.indexOf("\nBase directory for this skill:"),
  ),
}

/** Temporary skill folders, removed after each test. */
class Folders extends TemporaryFolders {
  async holding(text: string): Promise<string> {
    const folder = await this.with("a-skill")
    await writeFile(join(folder, "a-skill", "SKILL.md"), text)
    return folder
  }

  async with(skill: string): Promise<string> {
    const folder = await this.make()
    await mkdir(join(folder, skill))
    return folder
  }
}

async function recorded<Request = ModelRequest>(name: string): Promise<Recorded<Request>> {
  const path = join(import.meta.dirname, "..", "..", "fixtures", "opencode", `${name}.json`)
  return JSON.parse(await readFile(path, "utf8"))
}

/**
 * A SKILL.md loads as `nustack check` reads it, or fails naming its file and the fix. Frontmatter reads CRLF as LF and
 * breaks at a stray CR while the body keeps both, and the frontmatter may close at the end of the file.
 */
describe("SkillFile", () => {
  const path = "/s/a-skill/SKILL.md"

  test("decodes a UTF-8 SKILL.md and refuses one that is not UTF-8, naming the fix", () => {
    const text = "---\nname: café\ndescription: A.\n---\n"
    expect(SkillFile.decode(path, new TextEncoder().encode(text)).text).toBe(text)
    expect(SkillFile.decode(path, new TextEncoder().encode(`\ufeff${text}`)).text).toBe(
      `\ufeff${text}`,
    )
    expect(() => SkillFile.decode(path, Uint8Array.of(0x2d, 0xff))).toThrow(
      new Error(
        "/s/a-skill/SKILL.md is not valid UTF-8; save it as UTF-8, or reinstall the nustack plugin",
      ),
    )
  })

  test("keeps the file's name over its folder's, and its description, path and body", () => {
    const text = '---\nname: a-skill\ndescription: "A skill: \\"quoted\\"."\n---\n# A\n---\nB\n'
    expect(new SkillFile(path, text).info("a-folder")).toEqual({
      id: "a-folder" as Skill.ID,
      name: "a-skill" as Skill.Name,
      description: 'A skill: "quoted".',
      autoinvoke: true,
      path: path as Skill.Info["path"],
      content: "# A\n---\nB\n",
    })
  })

  test("hands out a skill and a file that never change", () => {
    const file = new SkillFile(path, "---\nname: a\ndescription: A.\n---\n")
    expect([Object.isFrozen(file), Object.isFrozen(file.info("a"))]).toEqual([true, true])
  })

  test("reads frontmatter that closes at the end of the file", () => {
    const info = new SkillFile(path, "---\nname: a\ndescription: A.\n---").info("a")
    expect([info.name, info.content]).toEqual(["a", ""])
  })

  test("closes the frontmatter only at a line that holds ---", () => {
    const info = new SkillFile(path, "---\nname: a\ndescription: x---\n---\n# A\n").info("a")
    expect([info.description, info.content]).toEqual(["x---", "# A\n"])
  })

  test("reads a --- line that ends in a bare CR in the body as text", () => {
    const info = new SkillFile(path, "---\nname: a\ndescription: A.\n---\n# A\n---\rX\n").info("a")
    expect(info.content).toBe("# A\n---\rX\n")
  })

  test("keeps the body's opening blank line", () => {
    const info = new SkillFile(path, "---\nname: a\ndescription: A.\n---\n\n# A\n").info("a")
    expect(info.content).toBe("\n# A\n")
  })

  test("reads CRLF lines as LF in the frontmatter and keeps them in the body", () => {
    const skill = new SkillFile(path, "---\r\nname: a\r\ndescription: A.\r\n---\r\n# A\r\n").info(
      "a",
    )
    expect([skill.name, skill.content]).toEqual(["a", "# A\r\n"])
  })

  test.each([
    [
      "\ufeff---\nname: a\ndescription: A.\n---\n",
      "/s/a-skill/SKILL.md opens with a byte order mark; save it without one, or reinstall the nustack plugin",
    ],
    [
      "---\rname: a\rdescription: A.\r---\r",
      "/s/a-skill/SKILL.md has lines that end in a bare CR; save it with LF line endings, or reinstall the nustack plugin",
    ],
    [
      "# A\n",
      "/s/a-skill/SKILL.md has no frontmatter; open it with a --- block, or reinstall the nustack plugin",
    ],
    [
      "A\n---\nname: a\ndescription: A.\n---\n",
      "/s/a-skill/SKILL.md has no frontmatter; open it with a --- block, or reinstall the nustack plugin",
    ],
    [
      "---\nname: a\ndescription: A.\n---x\n",
      "/s/a-skill/SKILL.md has no frontmatter; open it with a --- block, or reinstall the nustack plugin",
    ],
    [
      "--- \nname: a\ndescription: A.\n---\n",
      "/s/a-skill/SKILL.md has no frontmatter; open it with a --- block, or reinstall the nustack plugin",
    ],
    [
      "---\nname: a\ndescription: A.\n--- \n",
      "/s/a-skill/SKILL.md has no frontmatter; open it with a --- block, or reinstall the nustack plugin",
    ],
    [
      "---\n- a\n---\n",
      "/s/a-skill/SKILL.md has frontmatter that is not key: value lines; write it as key: value lines, or reinstall the nustack plugin",
    ],
    [
      "---\nnull\n---\n",
      "/s/a-skill/SKILL.md has frontmatter that is not key: value lines; write it as key: value lines, or reinstall the nustack plugin",
    ],
    [
      "---\n7\n---\n",
      "/s/a-skill/SKILL.md has frontmatter that is not key: value lines; write it as key: value lines, or reinstall the nustack plugin",
    ],
  ])(
    "refuses a file %j whose frontmatter does not split from its body, naming the fix",
    (text, message) => {
      expect(() => new SkillFile(path, text).info("a")).toThrow(new Error(message))
    },
  )

  test("breaks a frontmatter line at a stray CR", () => {
    const text = "---\nname: a\ndescription: a\r\r\n b\n---\n"
    expect(new SkillFile(path, text).info("a").description).toBe("a\nb")
  })

  test("refuses frontmatter that is not valid YAML, naming the fix", () => {
    expect(() => new SkillFile(path, "---\nname: [a\n---\n").info("a")).toThrow(
      new Error(
        "/s/a-skill/SKILL.md has frontmatter that is not valid YAML; fix it, or reinstall the nustack plugin",
      ),
    )
  })

  test.each([
    [
      "---\ndescription: A.\n---\n",
      "/s/a-skill/SKILL.md has no name in its frontmatter; add one, or reinstall the nustack plugin",
    ],
    [
      "---\nname: a\n---\n",
      "/s/a-skill/SKILL.md has no description in its frontmatter; add one, or reinstall the nustack plugin",
    ],
    [
      "---\nname: 7\ndescription: A.\n---\n",
      "/s/a-skill/SKILL.md has a name that is not text; write its text, or reinstall the nustack plugin",
    ],
    [
      "---\nname:\ndescription: A.\n---\n",
      "/s/a-skill/SKILL.md has a name that is not text; write its text, or reinstall the nustack plugin",
    ],
    [
      '---\nname: a\ndescription: " "\n---\n',
      "/s/a-skill/SKILL.md has a blank description; fill it in, or reinstall the nustack plugin",
    ],
    [
      '---\nname: a\ndescription: "\\u200B"\n---\n',
      "/s/a-skill/SKILL.md has a blank description; fill it in, or reinstall the nustack plugin",
    ],
    [
      '---\nname: a\ndescription: "\\u2060"\n---\n',
      "/s/a-skill/SKILL.md has a blank description; fill it in, or reinstall the nustack plugin",
    ],
    [
      '---\nname: a\ndescription: "\\x85"\n---\n',
      "/s/a-skill/SKILL.md has a blank description; fill it in, or reinstall the nustack plugin",
    ],
  ])("refuses a field %j it cannot register, naming the fix", (text, message) => {
    expect(() => new SkillFile(path, text).info("a")).toThrow(new Error(message))
  })

  test.each([
    ["true # hidden from the model", false],
    ["true", false],
    ["True", false],
    ["false", true],
  ])("sets autoinvoke from disable-model-invocation: %s to %p", (value, autoinvoke) => {
    const text = `---\nname: a\ndescription: A.\ndisable-model-invocation: ${value}\n---\n`
    expect(new SkillFile(path, text).info("a").autoinvoke).toBe(autoinvoke)
  })

  test.each(["yes", "null"])("refuses disable-model-invocation: %s, naming the fix", (value) => {
    const text = `---\nname: a\ndescription: A.\ndisable-model-invocation: ${value}\n---\n`
    expect(() => new SkillFile(path, text).info("a")).toThrow(
      new Error(
        "/s/a-skill/SKILL.md has a disable-model-invocation that is not true or false; set it to true or false, or reinstall the nustack plugin",
      ),
    )
  })
})

/**
 * OpenCode gets every skill, or one error that lets the user fix them all at once. That error lists the failing skills
 * in path order, and a symlinked skill folder or one without a SKILL.md fails.
 */
describe("SkillFolder", () => {
  const folders = new Folders()

  afterEach(() => folders.clear())

  test("reads each skill folder, and no file beside them", async () => {
    const folder = await folders.holding("---\nname: a-skill\ndescription: A skill.\n---\n")
    await writeFile(join(folder, "README.md"), "# Skills\n")
    const skills = await new SkillFolder(folder).skills()
    expect([skills.map((skill): string => skill.id), Object.isFrozen(skills)]).toEqual([
      ["a-skill"],
      true,
    ])
  })

  test("refuses a skills folder it cannot read, naming the errno and the fix", async () => {
    const folder = join(await folders.with("a-skill"), "missing")
    const error = await new SkillFolder(folder).skills().catch((caught: unknown) => caught)
    expect(String(error)).toBe(
      `Error: ${folder} cannot be read (ENOENT); restore the plugin's skills folder, or reinstall the nustack plugin`,
    )
  })

  test("reports every skill that fails in one error", async () => {
    const folder = await folders.with("a-skill")
    await mkdir(join(folder, "b-skill"))
    await writeFile(join(folder, "b-skill", "SKILL.md"), "# B\n")
    const error = await new SkillFolder(folder).skills().catch((caught: unknown) => caught)
    expect(error).toEqual(
      new Error(
        `${join(folder, "a-skill", "SKILL.md")} cannot be read (ENOENT); give the skill a readable SKILL.md, or reinstall the nustack plugin\n` +
          `${join(folder, "b-skill", "SKILL.md")} has no frontmatter; open it with a --- block, or reinstall the nustack plugin`,
      ),
    )
  })

  test("lists the failing skills in path order", async () => {
    const folder = await folders.with("h-skill")
    await Promise.all(
      ["g", "f", "e", "d", "c", "b", "a"].map((name) => mkdir(join(folder, `${name}-skill`))),
    )
    const error = await new SkillFolder(folder).skills().catch((caught: unknown) => caught)
    expect(
      String(error)
        .split("\n")
        .map((line) => line.split("/").at(-2)),
    ).toEqual([
      "a-skill",
      "b-skill",
      "c-skill",
      "d-skill",
      "e-skill",
      "f-skill",
      "g-skill",
      "h-skill",
    ])
  })

  test("refuses a symlinked skill folder, naming the fix", async () => {
    const folder = await folders.holding("---\nname: a-skill\ndescription: A skill.\n---\n")
    await symlink(join(folder, "a-skill"), join(folder, "b-skill"))
    const error = await new SkillFolder(folder).skills().catch((caught: unknown) => caught)
    expect(error).toEqual(
      new Error(
        `${join(folder, "b-skill")} is a symlink, which the loader does not follow; put the skill folder itself there, or reinstall the nustack plugin`,
      ),
    )
  })

  test("refuses a skill folder without a SKILL.md, naming the errno and the fix", async () => {
    const folder = await folders.with("a-skill")
    const error = await new SkillFolder(folder).skills().catch((caught: unknown) => caught)
    expect(error).toEqual(
      new Error(
        `${join(folder, "a-skill", "SKILL.md")} cannot be read (ENOENT); give the skill a readable SKILL.md, or reinstall the nustack plugin`,
      ),
    )
  })

  test("refuses a SKILL.md that is not UTF-8, naming the fix", async () => {
    const folder = await folders.with("a-skill")
    await writeFile(join(folder, "a-skill", "SKILL.md"), Uint8Array.of(0x2d, 0xff))
    const error = await new SkillFolder(folder).skills().catch((caught: unknown) => caught)
    expect(error).toEqual(
      new Error(
        `${join(folder, "a-skill", "SKILL.md")} is not valid UTF-8; save it as UTF-8, or reinstall the nustack plugin`,
      ),
    )
  })

  test.skipIf(process.getuid?.() === 0)(
    "keeps the errno of a SKILL.md it may not read; root reads every file, so it skips as root",
    async () => {
      const folder = await folders.holding("---\nname: a\ndescription: A.\n---\n")
      await chmod(join(folder, "a-skill", "SKILL.md"), 0)
      const error = await new SkillFolder(folder).skills().catch((caught: unknown) => caught)
      expect(String(error)).toBe(
        `Error: ${join(folder, "a-skill", "SKILL.md")} cannot be read (EACCES); give the skill a readable SKILL.md, or reinstall the nustack plugin`,
      )
    },
  )

  test("names an error without a code as one", () => {
    expect([SkillFolder.code(new Error("x")), SkillFolder.code("x")]).toEqual([
      "no error code",
      "no error code",
    ])
  })

  test("reads the reason of anything thrown", () => {
    expect([SkillFolder.reason(new Error("x")), SkillFolder.reason("y")]).toEqual(["x", "y"])
  })

  test("lets the model invoke the mode alone", async () => {
    const skills = await new SkillFolder(SKILLS).skills()
    expect(skills.filter((skill) => skill.autoinvoke).map((skill): string => skill.id)).toEqual([
      "nus-mode",
    ])
  })
})

/**
 * No model call after a summary leaves out the mode in a session that loaded it, through a skill call that names the
 * mode or its user's invocation. A summary request or a shorter message list counts as a summary, and plugin storage
 * keeps which sessions loaded it. The requests are records of the real OpenCode sessions the setup above names. A
 * session that loaded another plugin's nus-mode, or whose other tool took the mode's id, gets nothing, and one whose
 * messages still hold the mode gets no second copy.
 */
describe("ModeReload", () => {
  const restored: ModelRequest["system"] = [
    {
      type: "text",
      text: `${MODE.content.trim()}\n\nBase directory for this skill: ${join(SKILLS, "nus-mode")}\nRelative paths in this skill are relative to this base directory.`,
    },
  ]

  /** One session's model requests, replayed through the session hooks. */
  class Conversation {
    readonly session = new FakeSession()
    readonly storage: FakeStorage
    readonly mode: Skill.Info

    constructor(storage = new FakeStorage(), mode = MODE) {
      this.storage = storage
      this.mode = mode
    }

    async start(): Promise<this> {
      await new ModeReload([this.mode], this.storage).register(this.session)
      return this
    }

    async prompt(record: Recorded<UserPrompt>): Promise<void> {
      await this.session.run("prompt", structuredClone(record.request))
    }

    async replay(
      record: Recorded,
      messages = record.request.messages,
    ): Promise<ModelRequest["system"]> {
      const request = { ...structuredClone(record.request), messages }
      await this.session.run(record.hook, request)
      return request.system.slice(record.request.system.length)
    }
  }

  test("fails with the remedy for skills without the mode", () => {
    expect(() => ModeReload.mode([])).toThrow(
      "skills/nus-mode/SKILL.md is missing; restore the mode, or reinstall the nustack plugin",
    )
  })

  test("gives the mode from skills that hold it", () => {
    expect(ModeReload.mode([MODE])).toBe(MODE)
  })

  test("gives its text back to a session the summarization caught loading the mode", async () => {
    const conversation = await new Conversation().start()
    await conversation.replay(summary)
    expect(await conversation.replay(following)).toEqual(restored)
  })

  test("gives its text back to a session that loaded the mode once a summarization drops it", async () => {
    const conversation = await new Conversation().start()
    expect(await conversation.replay(loading)).toEqual([])
    await conversation.replay(summary)
    expect(await conversation.replay(following)).toEqual(restored)
  })

  test("gives nothing after a summarization to a session that loaded another plugin's skill named nus-mode", async () => {
    // No recorded session loaded another plugin's nus-mode; this one gives the recorded load another body.
    const messages = JSON.parse(
      JSON.stringify(loading.request.messages).replaceAll(
        JSON.stringify(MODE.content.trim()).slice(1, -1),
        "# nus-mode\\n\\nAnother plugin's mode.",
      ),
    )
    expect(messages).not.toEqual(loading.request.messages)
    const conversation = await new Conversation().start()
    await conversation.replay(loading, messages)
    expect(await conversation.replay(following)).toEqual([])
  })

  test("gives nothing after a summarization to a session that never loaded the mode", async () => {
    const conversation = await new Conversation().start()
    await conversation.replay(unloadedSummary)
    expect(await conversation.replay(unloadedFollowing)).toEqual([])
  })

  test("gives no second copy to a session whose kept messages still hold the mode", async () => {
    const conversation = await new Conversation().start()
    await conversation.replay(loading)
    await conversation.replay(summary)
    // OpenCode keeps the newest messages after a summary when compaction.keep allows
    // (https://unpkg.com/@opencode/schema@2.2.5/dist/config/compaction.js); the recording kept none, so this list puts
    // the loading request's messages, the mode among them, before its own.
    const kept = [...loading.request.messages, ...following.request.messages]
    expect(await conversation.replay(following, kept)).toEqual([])
  })

  test("stores a session's load once, however often its requests hold it", async () => {
    let sets = 0
    const storage = new FakeStorage()
    const counting = Object.assign(new FakeStorage(), {
      set: async (...args: Parameters<FakeStorage["set"]>) => {
        sets += 1
        await storage.set(...args)
      },
      get: storage.get,
    })
    const conversation = await new Conversation(counting).start()
    await conversation.replay(loading)
    await conversation.replay(summary)
    const kept = [...loading.request.messages, ...following.request.messages]
    await conversation.replay(following, kept)
    expect([sets, storage.entries.size]).toEqual([1, 1])
  })

  test("reads no message again when a request repeats the count already read", async () => {
    const conversation = await new Conversation().start()
    await conversation.replay(loading)
    let reads = 0
    const counted = {
      role: "user" as const,
      content: [],
      toJSON: () => {
        reads += 1
        return {}
      },
    }
    const messages = [...loading.request.messages.slice(0, -1), counted]
    const added = await conversation.replay(loading, messages)
    expect([added, reads, JSON.stringify(counted), reads]).toEqual([[], 0, "{}", 1])
  })

  test("gives no second copy to a session whose shorter message list still holds the mode", async () => {
    const conversation = await new Conversation().start()
    await conversation.replay(loading)
    expect(await conversation.replay(loading, loading.request.messages.slice(1))).toEqual([])
  })

  test("gives nothing after a summarization to a session whose other tool took the mode's id", async () => {
    // No recorded session called another tool with the mode's id; this one renames the recorded skill call's tool.
    const messages = JSON.parse(
      JSON.stringify(loading.request.messages).replaceAll('"name":"skill"', '"name":"other"'),
    )
    expect(messages).not.toEqual(loading.request.messages)
    const conversation = await new Conversation().start()
    await conversation.replay(loading, messages)
    expect(await conversation.replay(following)).toEqual([])
  })

  test("gives the mode back to a session whose messages shrink without a summary request", async () => {
    const conversation = await new Conversation().start()
    await conversation.replay(loading)
    expect(await conversation.replay(following)).toEqual(restored)
  })

  test("reads each of a session's messages once between summarizations", async () => {
    const conversation = await new Conversation().start()
    let reads = 0
    const readCounter = {
      get content() {
        reads += 1
        return []
      },
    }
    const messages = loading.request.messages
    await conversation.replay(loading, [readCounter as never])
    await conversation.replay(loading, [readCounter as never, ...messages])
    expect(
      await conversation.replay(loading, [readCounter as never, ...messages, ...messages]),
    ).toEqual([])
    expect(reads).toBe(1)
  })

  test("finds a CRLF mode in a session's messages and gives its text back as it reads", async () => {
    const shown = MODE.content.trim().replaceAll("\n", "\r\n")
    // A CRLF SKILL.md's body, as the loader reads it: its opening blank line and last line break kept.
    const crlf = { ...MODE, content: `\r\n${shown}\r\n` }
    // No recorded session loaded a CRLF SKILL.md; this one turns the line breaks of the body the recorded load shows
    // into CRLF ones, as OpenCode showed a CRLF body trimmed in requests captured from it.
    const messages = JSON.parse(
      JSON.stringify(loading.request.messages).replaceAll(
        JSON.stringify(MODE.content.trim()).slice(1, -1),
        JSON.stringify(shown).slice(1, -1),
      ),
    )
    const conversation = await new Conversation(new FakeStorage(), crlf).start()
    await conversation.replay(loading, messages)
    expect(await conversation.replay(following)).toEqual([
      {
        type: "text",
        text: `${shown}\n\nBase directory for this skill: ${join(SKILLS, "nus-mode")}\nRelative paths in this skill are relative to this base directory.`,
      },
    ])
  })

  test.each([
    ["summary request", summary],
    ["model call", loading],
  ])(
    "gives nothing after a summarization to a session whose %s only quoted the mode",
    async (_case, record) => {
      const conversation = await new Conversation().start()
      // No recorded session pasted the mode into a prompt; this one gives the recorded request a first prompt that
      // quotes the mode's body, and no skill call.
      const messages = [
        {
          role: "user",
          content: [{ type: "text", text: `Proofread this text; reply OK.\n\n${MODE.content}` }],
        },
      ]
      await conversation.replay(record, messages as never)
      expect(await conversation.replay(following)).toEqual([])
    },
  )

  /** A user's invocation of the mode brings it back, and an invocation of another skill does not. */
  describe("in the sessions recorded with the shipped mode", () => {
    // The body the invocation shows, between OpenCode's skill heading and its base-directory note; the forged prompt
    // copied the same body.
    const block = String(Object(invoked.request.messages[2]).content[0].text)
    const content = block.slice(
      block.indexOf("\n\n") + 2,
      block.indexOf("\n\nBase directory for this skill:"),
    )
    const shipped = { ...MODE, content }

    test("gives its text back to a session whose user invoked the mode once its messages drop it", async () => {
      const conversation = await new Conversation(new FakeStorage(), shipped).start()
      await conversation.prompt(invoking)
      expect(await conversation.replay(invoked)).toEqual([])
      expect(await conversation.replay(invoked, [])).toEqual([
        {
          type: "text",
          text: `${content}\n\nBase directory for this skill: ${join(SKILLS, "nus-mode")}\nRelative paths in this skill are relative to this base directory.`,
        },
      ])
    })

    test("gives nothing to a session whose user invoked another skill", async () => {
      const conversation = await new Conversation(new FakeStorage(), shipped).start()
      // No recorded prompt invoked another skill; this one names another in the recorded invocation.
      const other = structuredClone(invoking)
      Object(other.request.prompt.skills)[0].id = "another-skill"
      await conversation.prompt(other)
      expect(await conversation.replay(invoked, [])).toEqual([])
    })

    test.each([
      ["model call", forged],
      ["summary request", forgedSummary],
    ])(
      "gives nothing to a session whose prompt forged an invocation, after its %s",
      async (_case, record) => {
        const conversation = await new Conversation(new FakeStorage(), shipped).start()
        await conversation.prompt(forging)
        await conversation.replay(record)
        expect(await conversation.replay(forged, [])).toEqual([])
      },
    )
  })

  /** A skill that quotes the mode loads nothing to give back. */
  describe("in a session that loaded another skill quoting the mode", () => {
    // The body the other skill quotes, between the quoted envelope's skill heading and its end.
    const value = String(Object(quotedCall.request.messages[2]).content[0].result.value)
    const quote = value.slice(value.indexOf('<skill_content name="nus-mode">'))
    const content = quote.slice(quote.indexOf("\n\n") + 2, quote.indexOf("\n</skill_content>"))
    const quoted = { ...MODE, content }

    test.each([
      ["model call", quotedCall],
      ["summary request", quotedSummary],
    ])("gives nothing after its %s", async (_case, record) => {
      const conversation = await new Conversation(new FakeStorage(), quoted).start()
      await conversation.replay(record)
      expect(await conversation.replay(quotedCall, [])).toEqual([])
    })
  })

  test("gives its text back after a restart to a session that loaded the mode before it", async () => {
    const storage = new FakeStorage()
    await (await new Conversation(storage).start()).replay(loading)
    expect(await (await new Conversation(storage).start()).replay(following)).toEqual(restored)
  })

  test("gives nothing after a restart to another session than the one that loaded the mode", async () => {
    const storage = new FakeStorage()
    await (await new Conversation(storage).start()).replay(loading)
    expect(await (await new Conversation(storage).start()).replay(unloadedFollowing)).toEqual([])
  })
})

/** OpenCode sees exactly the shipped skills and the mode reload's hooks, and none once the plugin unloads. */
describe("plugin", () => {
  test("registers every shipped skill and the mode reload's hooks, and its cleanup removes them", async () => {
    const registry = new FakeRegistry()
    const session = new FakeSession()
    const cleanup = await plugin.setup({ ...registry.context, session, storage: new FakeStorage() })
    const hooks = [...session.hooks.keys()].sort()
    await cleanup()
    const shipped = await readdir(SKILLS)
    expect([
      [...registry.skills.keys()].sort(),
      hooks,
      registry.disposed,
      session.hooks.size,
    ]).toEqual([shipped.sort(), ["compaction", "context", "prompt"], true, 0])
  })
})
