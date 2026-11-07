/**
 * Claude Code, running the release zip against tests/fixtures/model.ts, sends nus-mode's folder and body in its first
 * request after a manual or an automatic summarization of a session that loaded the mode, and leaves it out of a
 * session that never did, even one that invoked another plugin's skill of the same name. Each test checks that request
 * also lacks the session's first prompt, so the summary replaced it.
 * It also offers the model each vendored skill tests/fixtures/vendored.ts lists, under the plugin's name.
 * A host's requests carry IDs and times that change on each run, so each test checks what the request holds.
 */
import { afterAll, beforeAll, describe, expect, test } from "bun:test"
import { mkdir, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { Bundle } from "../../../fixtures/bundle.ts"
import { TemporaryFolders } from "../../../fixtures/folders.ts"
import { FakeModel } from "../../../fixtures/model.ts"
import { finished } from "../../../fixtures/process.ts"
import { VENDORED_SKILLS } from "../../../fixtures/vendored.ts"

/** claude failed while a smoke test drove it. */
class ClaudeError extends Error {
  override name = "ClaudeError"
}

const claude = join(
  import.meta.dirname,
  "..",
  "..",
  "..",
  "fixtures",
  "smoke",
  "node_modules",
  ".bin",
  "claude",
)

/**
 * Claude Code runs each test's sessions in one temporary home, with the release zip's plugin, another plugin whose skill
 * shares the mode's name and title, and the fake model.
 */
describe("reload-nus-mode.sh in Claude Code", () => {
  const folders = new TemporaryFolders()
  let bundle: Bundle
  let model: FakeModel
  let home: string

  beforeAll(async () => {
    bundle = await Bundle.unpacked()
    model = new FakeModel("claude-code")
    home = await folders.make()
    // Another plugin, installed beside nustack, whose skill shares the mode's name and title.
    const other = join(home, "other")
    await mkdir(join(other, ".claude-plugin"), { recursive: true })
    await mkdir(join(other, "skills", "nus-mode"), { recursive: true })
    await writeFile(
      join(other, ".claude-plugin", "plugin.json"),
      JSON.stringify({ name: "other", version: "1.0.0", description: "Another plugin." }),
    )
    await writeFile(
      join(other, "skills", "nus-mode", "SKILL.md"),
      "---\nname: nus-mode\ndescription: Another plugin's mode.\n---\n\n# nus-mode\n\nAnother plugin's mode.\n",
    )
  })

  afterAll(async () => {
    // beforeAll may stop before it sets each of these.
    await Promise.all([bundle?.remove(), model?.stop(), folders.clear()])
  })

  async function ask(session: string | null, text: string): Promise<string> {
    const resume = session === null ? [] : ["--resume", session]
    const run = Bun.spawn(
      [
        claude,
        "-p",
        "--plugin-dir",
        bundle.root,
        "--plugin-dir",
        join(home, "other"),
        "--model",
        FakeModel.MODEL,
        "--output-format",
        "json",
        "--allowedTools=Skill",
        ...resume,
        text,
      ],
      {
        cwd: home,
        env: {
          PATH: process.env.PATH,
          HOME: home,
          ANTHROPIC_BASE_URL: model.url,
          ANTHROPIC_API_KEY: "fake",
          // Claude Code gives FakeModel.MODEL a window that FakeModel.FILL leaves far from full, so each run holds
          // Claude Code to the fake's window, as opencode.test.ts holds OpenCode:
          // https://code.claude.com/docs/en/model-config#set-the-auto-compact-window
          CLAUDE_CODE_AUTO_COMPACT_WINDOW: String(FakeModel.WINDOW),
        },
        stdin: "ignore",
        stderr: "pipe",
      },
    )
    const { code, stdout, stderr } = await finished(run)
    if (code !== 0)
      throw new ClaudeError(`claude exited with ${code}\nstderr: ${stderr}\nstdout: ${stdout}`)
    return JSON.parse(stdout).session_id
  }

  // The hook plays no part here. The block shares this suite's Claude Code install, bundle and fake model, which a file
  // of its own would start a second time.
  describe("the release zip's vendored skills", () => {
    test("offers the model each vendored skill", async () => {
      await ask(null, FakeModel.UNLOADED)
      const turn = model.turnWith(FakeModel.UNLOADED)
      expect(VENDORED_SKILLS.filter((name) => !turn.includes(`nustack:${name}`))).toEqual([])
    })
  })

  test("sends nus-mode again after /compact", async () => {
    const session = await ask(null, FakeModel.LOAD)
    await ask(session, "/compact")
    await ask(session, FakeModel.AFTER)
    const turn = model.turnWith(FakeModel.AFTER)
    expect([
      turn.includes(bundle.escapedBody),
      turn.includes(bundle.base),
      turn.includes(FakeModel.LOAD),
    ]).toEqual([true, true, false])
  })

  test("sends nus-mode again after an automatic summarization", async () => {
    const session = await ask(null, FakeModel.LOAD)
    await ask(session, FakeModel.FILL)
    await ask(session, FakeModel.AFTER)
    const turn = model.turnWith(FakeModel.AFTER)
    expect([
      turn.includes(bundle.escapedBody),
      turn.includes(bundle.base),
      turn.includes(FakeModel.LOAD),
    ]).toEqual([true, true, false])
  })

  test("leaves nus-mode out after summarizing a session that invoked another plugin's nus-mode", async () => {
    const first = "/other:nus-mode"
    const session = await ask(null, first)
    await ask(session, "/compact")
    await ask(session, FakeModel.AFTER)
    const turn = model.turnWith(FakeModel.AFTER)
    expect([
      turn.includes(bundle.escapedBody),
      turn.includes(bundle.base),
      turn.includes(first),
    ]).toEqual([false, false, false])
  })

  test("leaves nus-mode out after summarizing a session that never loaded it", async () => {
    const first = FakeModel.UNLOADED
    const session = await ask(null, first)
    await ask(session, "/compact")
    await ask(session, FakeModel.AFTER)
    const turn = model.turnWith(FakeModel.AFTER)
    expect([
      turn.includes(bundle.escapedBody),
      turn.includes(bundle.base),
      turn.includes(first),
    ]).toEqual([false, false, false])
  })
})
