/**
 * The OpenCode loader reads each skill folder into the skill OpenCode registers, registers every skill the plugin ships
 * with the principle and language skills hidden from the model, and fails with one error naming each skill folder or
 * SKILL.md it cannot load, or the skills folder it cannot read; once every skill loads, a missing mode fails it with an
 * error naming the mode's SKILL.md. It puts the mode back in a session's context once a summarization drops it.
 */
import { afterEach, describe, expect, spyOn, test } from "bun:test"
import { chmod, mkdir, readdir, readFile, symlink, writeFile } from "node:fs/promises"
import { join } from "node:path"
import type { Skill } from "@opencode/plugin"
import { YAML } from "bun"
import plugin, {
  errorCode,
  errorMessage,
  type ModelRequest,
  ModeReload,
  SkillError,
  SkillFile,
  SkillFolder,
  type UserPrompt,
} from "../../../plugin/opencode.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"
import { skipAsRoot } from "../../fixtures/permissions.ts"
import { FakeRegistry } from "../../fixtures/registry.ts"
import { FakeSession, FakeStorage } from "../../fixtures/session.ts"
import { thrown } from "../../fixtures/thrown.ts"
import { VENDORED_SKILLS } from "../../fixtures/vendored.ts"

const SKILLS = new SkillFolder(join(import.meta.dirname, "..", "..", "..", "plugin", "skills"))

/** One request OpenCode passed a session hook, as the recording plugin wrote it down. */
interface Recorded<Request = ModelRequest> {
  readonly hook: Request extends UserPrompt ? "prompt" : "context" | "compaction"
  readonly request: Request
}

// The loaded, unloaded, invoked, forged and quoted folders each hold one OpenCode session under an agent with a
// one-line prompt and Code Mode denied, so each request carries little but what the reload reads; the crlf,
// config-skill, kept, pasted and other-skill sessions ran under OpenCode's default prompt. Each file holds the fields
// the loader reads of one request a session hook received, recorded by a plugin loaded beside the loader. The loaded
// and unloaded sessions ran against the real model, and the rest in the smoke tests' OpenCode against
// tests/fixtures/model.ts.
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
// In one the skill tool loaded a CRLF SKILL.md, and in one a nus-mode from the config's skills folder, beside
// nustack's: each load, its summary request and the first request after it.
const crlfLoading = await recorded("crlf/context")
const crlfSummary = await recorded("crlf/compaction")
const crlfFollowing = await recorded("crlf/following")
const configSkillLoading = await recorded("config-skill/context")
const configSkillSummary = await recorded("config-skill/compaction")
const configSkillFollowing = await recorded("config-skill/following")
// In the kept session the skill tool loaded the mode in the turn after a first one, the last before a summary the user
// asked for, since a session's first summary, unless its model compacts natively, never keeps its first user turn
// (https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/compaction.ts#L967-L971;
// https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/compaction.ts#L1017-L1027;
// https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/compaction.ts#L321-L323). OpenCode kept
// that turn as text in the summary's message, as compaction.keep allows, 15,000 tokens of recent conversation unless
// set (https://unpkg.com/@opencode/schema@2.2.5/dist/config/compaction.js;
// https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/compaction.ts#L47-L48;
// https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/compaction.ts#L263;
// https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/config/plugin/compaction.ts#L22),
// with the mode's text cut short at "[truncated]", since its session code cuts a tool result to 1250 characters
// (https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/recent-text.ts#L6;
// https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/recent-text.ts#L50;
// https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/recent-text.ts#L72-L84): the load, its
// summary request and the first request after it.
const keptLoading = await recorded("kept/context")
const keptSummary = await recorded("kept/compaction")
const keptFollowing = await recorded("kept/following")
// In one a prompt pasted the mode's body, with no skill call: its model call, its summary request and the next request.
const pastedCall = await recorded("pasted/context")
const pastedSummary = await recorded("pasted/compaction")
const pastedFollowing = await recorded("pasted/following")
// In one the user invoked another skill, sample-mode, as the TUI does: its prompt and the model call that followed.
const otherInvoking = await recorded<UserPrompt>("other-skill/prompt")
const otherInvoked = await recorded("other-skill/context")
// The mode's body as the recorded session loaded it, between OpenCode's skill heading and its base-directory note. The
// recording ran an older nus-mode, and the reload matches whatever body the loader registered, so the recorded body
// stands in for the shipped one; the smoke tests reload the shipped body in OpenCode itself.
const loaded = String(Object(Object(loading.request.messages[2]).content[0]).result.value)
const MODE: Skill.Info = {
  ...ModeReload.mode(SKILLS, await SKILLS.skills()),
  content: shownBody(loaded),
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

function withSet(storage: FakeStorage, set: FakeStorage["set"]): FakeStorage {
  return Object.assign(new FakeStorage(), { set, get: storage.get })
}

function shownBody(text: string, endMarker = "\n\nBase directory for this skill:"): string {
  return text.slice(text.indexOf("\n\n") + 2, text.indexOf(endMarker))
}

/**
 * A SKILL.md loads as `scripts/check.ts` reads it, or fails naming its file and the fix. Frontmatter reads CRLF as LF and
 * breaks at a stray CR while the body keeps both, and the frontmatter may close at the end of the file.
 */
describe("SkillFile", () => {
  const path = "/s/a-skill/SKILL.md"

  test("decodes a UTF-8 SKILL.md and refuses one that is not UTF-8, naming the fix", async () => {
    const text = "---\nname: café\ndescription: A.\n---\n"
    expect(SkillFile.decode(path, new TextEncoder().encode(text)).text).toBe(text)
    expect(SkillFile.decode(path, new TextEncoder().encode(`\ufeff${text}`)).text).toBe(
      `\ufeff${text}`,
    )
    expect(await thrown(() => SkillFile.decode(path, Uint8Array.of(0x2d, 0xff)))).toEqual(
      new SkillError(
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
      "/s/a-skill/SKILL.md has no frontmatter; open it with a line that holds only ---, and save it with no byte order mark and with LF or CRLF line endings, or reinstall the nustack plugin",
    ],
    [
      "---\nname: a\ndescription: A.\n",
      "/s/a-skill/SKILL.md opens with --- and never closes; end it with a --- line, or reinstall the nustack plugin",
    ],
    [
      "---",
      "/s/a-skill/SKILL.md opens with --- and never closes; end it with a --- line, or reinstall the nustack plugin",
    ],
    [
      "---\r\nname: a\r\ndescription: A.\r\n",
      "/s/a-skill/SKILL.md opens with --- and never closes; end it with a --- line, or reinstall the nustack plugin",
    ],
    [
      "A\n---\nname: a\ndescription: A.\n---\n",
      "/s/a-skill/SKILL.md has no frontmatter; open it with a line that holds only ---, and save it with no byte order mark and with LF or CRLF line endings, or reinstall the nustack plugin",
    ],
    [
      "---\nname: a\ndescription: A.\n---x\n",
      "/s/a-skill/SKILL.md opens with --- and never closes; end it with a --- line, or reinstall the nustack plugin",
    ],
    [
      "--- \nname: a\ndescription: A.\n---\n",
      "/s/a-skill/SKILL.md has no frontmatter; open it with a line that holds only ---, and save it with no byte order mark and with LF or CRLF line endings, or reinstall the nustack plugin",
    ],
    [
      "---\nname: a\ndescription: A.\n--- \n",
      "/s/a-skill/SKILL.md opens with --- and never closes; end it with a --- line, or reinstall the nustack plugin",
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
      "---\n\n\n---\n",
      "/s/a-skill/SKILL.md has frontmatter that is not key: value lines; write it as key: value lines, or reinstall the nustack plugin",
    ],
    [
      "---\n7\n---\n",
      "/s/a-skill/SKILL.md has frontmatter that is not key: value lines; write it as key: value lines, or reinstall the nustack plugin",
    ],
  ])(
    "refuses a file %j whose frontmatter does not split from its body, naming the fix",
    async (text, message) => {
      expect(await thrown(() => new SkillFile(path, text).info("a"))).toEqual(
        new SkillError(message),
      )
    },
  )

  test("breaks a frontmatter line at a stray CR", () => {
    const text = "---\nname: a\ndescription: a\r\r\n b\n---\n"
    expect(new SkillFile(path, text).info("a").description).toBe("a\nb")
  })

  test("refuses frontmatter that is not valid YAML, naming the fix", async () => {
    expect(await thrown(() => new SkillFile(path, "---\nname: [a\n---\n").info("a"))).toEqual(
      new SkillError(
        "/s/a-skill/SKILL.md has frontmatter that is not valid YAML; fix it, or reinstall the nustack plugin",
      ),
    )
  })

  test("reads frontmatter nested 200 levels deep, the most it reads", () => {
    const text = `---\nname: a\ndescription: A.\nmetadata: ${"[".repeat(199)}${"]".repeat(199)}\n---\n`
    expect(new SkillFile(path, text).split()[0].get("name")).toBe("a")
  })

  test("reads frontmatter of 4096 characters, the most it reads", () => {
    const text = `---\nname: a\ndescription: ${"A".repeat(4074)}\n---\n`
    expect(new SkillFile(path, text).info("a").description).toHaveLength(4074)
  })

  test.each([["4097 characters", `name: a\ndescription: ${"A".repeat(4075)}\n`]])(
    "refuses frontmatter of %s before Bun's YAML parser reads it, naming the fix",
    async (_, frontmatter) => {
      expect(await thrown(() => new SkillFile(path, `---\n${frontmatter}---\n`).info("a"))).toEqual(
        new SkillError(
          "/s/a-skill/SKILL.md has frontmatter longer than 4096 characters; shorten it, or reinstall the nustack plugin",
        ),
      )
    },
  )

  test("reads frontmatter whose apostrophe comes before 201 flow lists, 2 levels deep", () => {
    const lists = Array.from({ length: 201 }, (_, at) => `k${at}: [1]`).join("\n")
    const text = `---\nname: x\ndescription: it's\n${lists}\n---\n`
    expect(new SkillFile(path, text).info("x").description).toBe("it's")
  })

  test.each([
    ["a bracket in a comment", "metadata: 1 # [[[\n", 1],
    ["brackets in a block scalar", "metadata: |\n  [[[\n", "[[[\n"],
    ["a '' escape before a bracket", "metadata: 'it''s ]'\n", "it's ]"],
    ['a \\" escape before a bracket', 'metadata: "a \\" ]"\n', 'a " ]'],
    ["brackets in a quoted value over two lines", 'metadata: "a [\n  ]]"\n', "a [ ]]"],
  ])("reads frontmatter whose text holds %s, which nest nothing", (_, field, value) => {
    const text = `---\nname: a\ndescription: A.\n${field}---\n`
    expect(new SkillFile(path, text).split()[0].get("metadata")).toEqual(value)
  })

  test("reads a stack overflow in Bun's YAML parser as frontmatter nested too deep, naming the fix", async () => {
    const parse = spyOn(YAML, "parse").mockImplementation(() => {
      throw new RangeError("Maximum call stack size exceeded.")
    })
    try {
      const file = new SkillFile(path, "---\nname: a\ndescription: A.\n---\n")
      expect(await thrown(() => file.info("a"))).toEqual(
        new SkillError(
          "/s/a-skill/SKILL.md has frontmatter that nests values more than 200 levels deep; flatten them, or reinstall the nustack plugin",
        ),
      )
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
        const file = new SkillFile(path, "---\nname: a\ndescription: A.\n---\n")
        expect(await thrown(() => file.info("a"))).toBe(bug)
      } finally {
        parse.mockRestore()
      }
    },
  )

  test.each([
    [
      "---\ndescription: A.\n---\n",
      "/s/a-skill/SKILL.md has no name in its frontmatter; add one, or reinstall the nustack plugin",
    ],
    [
      "---\n---\n# A\n",
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
    [
      `---\nname: a\ndescription: A.\nmetadata: ${"[".repeat(200)}${"]".repeat(200)}\n---\n`,
      "/s/a-skill/SKILL.md has frontmatter that nests values more than 200 levels deep; flatten them, or reinstall the nustack plugin",
    ],
    [
      `---\nname: a\ndescription: A.\nmetadata: [[&x ${"[".repeat(198)}${"]".repeat(198)}]]\nother: *x\n---\n`,
      "/s/a-skill/SKILL.md has frontmatter that nests values more than 200 levels deep; flatten them, or reinstall the nustack plugin",
    ],
    [
      "---\nname: a\ndescription: A.\nmetadata: &x [*x]\n---\n",
      "/s/a-skill/SKILL.md has frontmatter that nests values more than 200 levels deep; flatten them, or reinstall the nustack plugin",
    ],
  ])("refuses a field %j it cannot register, naming the fix", async (text, message) => {
    expect(await thrown(() => new SkillFile(path, text).info("a"))).toEqual(new SkillError(message))
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

  test.each(["yes", "null"])(
    "refuses disable-model-invocation: %s, naming the fix",
    async (value) => {
      const text = `---\nname: a\ndescription: A.\ndisable-model-invocation: ${value}\n---\n`
      expect(await thrown(() => new SkillFile(path, text).info("a"))).toEqual(
        new SkillError(
          "/s/a-skill/SKILL.md has a disable-model-invocation that is not true or false; set it to true or false, or reinstall the nustack plugin",
        ),
      )
    },
  )
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

  test("lets the model invoke the mode and the vendored skills alone", async () => {
    const skills = await SKILLS.skills()
    const invocable = skills.filter((skill) => skill.autoinvoke).map((skill): string => skill.id)
    expect(invocable.sort()).toEqual([...VENDORED_SKILLS, "nus-mode"].sort())
  })

  test("refuses a skills folder it cannot read, naming the errno and the fix", async () => {
    const folder = join(await folders.with("a-skill"), "missing")
    const error = await thrown(() => new SkillFolder(folder).skills())
    expect(String(error)).toBe(
      `SkillError: ${folder} cannot be read (ENOENT); restore the plugin's skills folder, or reinstall the nustack plugin`,
    )
  })

  test("reports every skill that fails in one error", async () => {
    const folder = await folders.with("a-skill")
    await mkdir(join(folder, "b-skill"))
    await writeFile(join(folder, "b-skill", "SKILL.md"), "# B\n")
    const error = await thrown(() => new SkillFolder(folder).skills())
    expect(String(error)).toBe(
      `SkillError: ${join(folder, "a-skill", "SKILL.md")} cannot be read (ENOENT); give the skill a readable SKILL.md, or reinstall the nustack plugin\n` +
        `${join(folder, "b-skill", "SKILL.md")} has no frontmatter; open it with a line that holds only ---, and save it with no byte order mark and with LF or CRLF line endings, or reinstall the nustack plugin`,
    )
  })

  test("lists the failing skills in path order", async () => {
    const folder = await folders.with("h-skill")
    await Promise.all(
      ["g", "f", "e", "d", "c", "b", "a"].map((name) => mkdir(join(folder, `${name}-skill`))),
    )
    const error = await thrown(() => new SkillFolder(folder).skills())
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
    const error = await thrown(() => new SkillFolder(folder).skills())
    expect(error).toEqual(
      new SkillError(
        `${join(folder, "b-skill")} is a symlink, which the loader does not follow; put the skill folder itself there, or reinstall the nustack plugin`,
      ),
    )
  })

  test("refuses a skill folder without a SKILL.md, naming the errno and the fix", async () => {
    const folder = await folders.with("a-skill")
    const error = await thrown(() => new SkillFolder(folder).skills())
    expect(error).toEqual(
      new SkillError(
        `${join(folder, "a-skill", "SKILL.md")} cannot be read (ENOENT); give the skill a readable SKILL.md, or reinstall the nustack plugin`,
      ),
    )
  })

  test("refuses a SKILL.md that is not UTF-8, naming the fix", async () => {
    const folder = await folders.with("a-skill")
    await writeFile(join(folder, "a-skill", "SKILL.md"), Uint8Array.of(0x2d, 0xff))
    const error = await thrown(() => new SkillFolder(folder).skills())
    expect(error).toEqual(
      new SkillError(
        `${join(folder, "a-skill", "SKILL.md")} is not valid UTF-8; save it as UTF-8, or reinstall the nustack plugin`,
      ),
    )
  })

  skipAsRoot(
    "keeps the errno of a SKILL.md it may not read; root reads every file, so it skips as root",
    async () => {
      const folder = await folders.holding("---\nname: a\ndescription: A.\n---\n")
      await chmod(join(folder, "a-skill", "SKILL.md"), 0)
      const error = await thrown(() => new SkillFolder(folder).skills())
      expect(String(error)).toBe(
        `SkillError: ${join(folder, "a-skill", "SKILL.md")} cannot be read (EACCES); give the skill a readable SKILL.md, or reinstall the nustack plugin`,
      )
    },
  )
})

/**
 * No model call after a summary leaves out the mode in a session that loaded it, through a skill call that names the
 * mode or its user's invocation. A summary request or a shorter message list counts as a summary, and plugin storage
 * keeps which sessions loaded it. The requests are records of the real OpenCode sessions the setup above names. A
 * session that loaded a nus-mode from the config's skills folder, or whose other tool took the mode's id, gets nothing,
 * and one whose messages still hold the mode gets no second copy. A store that fails surfaces its error, and the next
 * request retries it. Skills without the mode fail with an error that names the mode's SKILL.md and its fix.
 */
describe("ModeReload", () => {
  const restored: ModelRequest["system"] = [
    {
      type: "text",
      text: `${MODE.content}\n\nBase directory for this skill: ${SKILLS.path}/nus-mode\nRelative paths in this skill are relative to this base directory.`,
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
      await new ModeReload(this.mode, this.storage).register(this.session)
      return this
    }

    async prompt(record: Recorded<UserPrompt>): Promise<void> {
      await this.session.run("prompt", structuredClone(record.request))
    }

    // messages replaces the recorded request's messages, for a session no recording shows, such as one with fewer
    // messages than its recording.
    async replay(
      record: Recorded,
      messages = record.request.messages,
    ): Promise<ModelRequest["system"]> {
      const request = { ...structuredClone(record.request), messages }
      await this.session.run(record.hook, request)
      return request.system.slice(record.request.system.length)
    }
  }

  test("gives back the trimmed body, CRLF lines kept, then the mode's folder", () => {
    const skill = {
      ...MODE,
      content: "\n# nus-mode\r\nSay hi.\n\n",
      path: "/plugin/skills/nus-mode/SKILL.md" as Skill.Info["path"],
    }
    expect(new ModeReload(skill, new FakeStorage()).reloadText).toBe(
      "# nus-mode\r\nSay hi.\n\nBase directory for this skill: /plugin/skills/nus-mode\nRelative paths in this skill are relative to this base directory.",
    )
  })

  test("fails with the remedy for skills without the mode", async () => {
    expect(await thrown(() => ModeReload.mode(new SkillFolder("/plugin/skills"), []))).toEqual(
      new SkillError(
        "/plugin/skills/nus-mode/SKILL.md is missing; restore the mode, or reinstall the nustack plugin",
      ),
    )
  })

  test("gives the mode from skills that hold it", () => {
    expect(ModeReload.mode(new SkillFolder("/plugin/skills"), [MODE])).toBe(MODE)
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

  test("gives nothing after a summarization to a session that loaded a nus-mode from the config's skills folder", async () => {
    const conversation = await new Conversation().start()
    await conversation.replay(configSkillLoading)
    await conversation.replay(configSkillSummary)
    expect(await conversation.replay(configSkillFollowing)).toEqual([])
  })

  test("gives nothing after a summarization to a session that never loaded the mode", async () => {
    const conversation = await new Conversation().start()
    await conversation.replay(unloadedSummary)
    expect(await conversation.replay(unloadedFollowing)).toEqual([])
  })

  test("gives no second copy to a session whose first request after a summarization still holds the mode", async () => {
    const conversation = await new Conversation().start()
    await conversation.replay(loading)
    await conversation.replay(summary)
    expect(await conversation.replay(loading)).toEqual([])
  })

  test("stores a session's load once, however often its requests hold it", async () => {
    let sets = 0
    const storage = new FakeStorage()
    const counting = withSet(storage, async (...args) => {
      sets += 1
      await storage.set(...args)
    })
    const conversation = await new Conversation(counting).start()
    await conversation.replay(loading)
    await conversation.replay(loading, loading.request.messages.slice(1))
    await conversation.replay(summary)
    expect([sets, storage.entries.size]).toEqual([1, 1])
  })

  test("stores a session's load again on its next request once storing it failed", async () => {
    const storage = new FakeStorage()
    let failures = 1
    const flaky = withSet(storage, async (...args) => {
      if (failures-- > 0) throw new Error("storage is down")
      await storage.set(...args)
    })
    const conversation = await new Conversation(flaky).start()
    expect(await thrown(() => conversation.replay(loading))).toEqual(new Error("storage is down"))
    await conversation.replay(loading)
    expect(storage.entries.size).toBe(1)
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
    // FakeModel plays only replies recorded from the real API, and none calls a tool other than skill with the mode's
    // id as its input, though a plugin's tool can take one; this one is the recorded load with its skill call's tool
    // renamed.
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
    const load = String(Object(Object(crlfLoading.request.messages[2]).content[0]).result.value)
    const shown = shownBody(load).trim()
    // A CRLF SKILL.md's body, as the loader reads it: its opening blank line and last line break kept.
    const crlf = { ...MODE, content: `\r\n${shown}\r\n` }
    const conversation = await new Conversation(new FakeStorage(), crlf).start()
    await conversation.replay(crlfLoading)
    await conversation.replay(crlfSummary)
    expect([shown.includes("\r\n"), await conversation.replay(crlfFollowing)]).toEqual([
      true,
      [
        {
          type: "text",
          text: `${shown}\n\nBase directory for this skill: ${SKILLS.path}/nus-mode\nRelative paths in this skill are relative to this base directory.`,
        },
      ],
    ])
  })

  test("gives nothing after a summarization to a session whose prompt only pasted the mode", async () => {
    // OpenCode's run command sent the prompt twice, each copy in quotes, so the mode's body runs from the first copy's
    // first blank line to its closing quote. The loader holds that body, so only the missing skill call keeps the mode
    // out.
    const text = String(Object(pastedCall.request.messages[0]).content[0].text)
    const pasted = {
      ...MODE,
      content: `${shownBody(text, '" "')}\n`,
    }
    const conversation = await new Conversation(new FakeStorage(), pasted).start()
    await conversation.replay(pastedCall)
    await conversation.replay(pastedSummary)
    expect(await conversation.replay(pastedFollowing)).toEqual([])
  })

  /** A user's invocation of the mode brings it back, and an invocation of another skill does not. */
  describe("in the sessions recorded with the shipped mode", () => {
    // The body the invocation shows, between OpenCode's skill heading and its base-directory note; the forged prompt
    // copied the same body.
    const block = String(Object(invoked.request.messages[2]).content[0].text)
    const content = shownBody(block)
    const shipped = { ...MODE, content }

    test("gives its text back to a session whose user invoked the mode once its messages drop it", async () => {
      const conversation = await new Conversation(new FakeStorage(), shipped).start()
      await conversation.prompt(invoking)
      expect(await conversation.replay(invoked)).toEqual([])
      expect(await conversation.replay(invoked, [])).toEqual([
        {
          type: "text",
          text: `${content}\n\nBase directory for this skill: ${SKILLS.path}/nus-mode\nRelative paths in this skill are relative to this base directory.`,
        },
      ])
    })

    test("gives nothing to a session whose user invoked another skill", async () => {
      const conversation = await new Conversation(new FakeStorage(), shipped).start()
      await conversation.prompt(otherInvoking)
      expect(await conversation.replay(otherInvoked, [])).toEqual([])
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

  /** A summary that keeps the load's turn cuts the mode short, so it comes back. */
  describe("in a session whose summary kept the turn that loaded the mode", () => {
    // The body the load shows, between OpenCode's skill heading and its base-directory note.
    const block = String(Object(keptLoading.request.messages[4]).content[0].result.value)
    const content = shownBody(block)
    const kept = { ...MODE, content }

    test("gives its text back after the summary cut it short", async () => {
      const conversation = await new Conversation(new FakeStorage(), kept).start()
      await conversation.replay(keptLoading)
      await conversation.replay(keptSummary)
      expect(await conversation.replay(keptFollowing)).toEqual([
        {
          type: "text",
          text: `${content}\n\nBase directory for this skill: ${SKILLS.path}/nus-mode\nRelative paths in this skill are relative to this base directory.`,
        },
      ])
    })
  })

  /** A skill that quotes the mode loads nothing to give back. */
  describe("in a session that loaded another skill quoting the mode", () => {
    // The body the other skill quotes, between the quoted envelope's skill heading and its end.
    const value = String(Object(quotedCall.request.messages[2]).content[0].result.value)
    const quote = value.slice(value.indexOf('<skill_content name="nus-mode">'))
    const content = shownBody(quote, "\n</skill_content>")
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
    const entries = await readdir(SKILLS.path, { withFileTypes: true })
    const shipped = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name)
    expect([
      [...registry.skills.keys()].sort(),
      hooks,
      registry.disposed,
      session.hooks.size,
    ]).toEqual([shipped.sort(), ["compaction", "context", "prompt"], true, 0])
  })
})

/** A thrown value's errno code, or a note that it has none. */
describe("errorCode", () => {
  test("names an error without a code as one", () => {
    expect([errorCode(new Error("x")), errorCode("x")]).toEqual(["no error code", "no error code"])
  })
})

/** A thrown value's message, whether or not it is an Error. */
describe("errorMessage", () => {
  test("reads the message of anything thrown", () => {
    expect([errorMessage(new Error("x")), errorMessage("y")]).toEqual(["x", "y"])
  })
})
