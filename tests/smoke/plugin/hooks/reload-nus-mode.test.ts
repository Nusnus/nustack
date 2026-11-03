/**
 * Claude Code, running the release zip against tests/fixtures/model.ts, sends nus-mode's folder and body in its first
 * request after a manual or an automatic summarization of a session that loaded the mode, and leaves it out of a
 * session that never did, even one that invoked another plugin's skill of the same name. Each test checks that request
 * also lacks the session's first prompt, so the summary replaced it.
 * A host's requests carry IDs and times that change on each run, so each test checks what the request holds.
 */
import { afterAll, beforeAll, describe, expect, test } from "bun:test"
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { Bundle } from "../../../fixtures/bundle.ts"
import { FakeModel } from "../../../fixtures/model.ts"
import { finished } from "../../../fixtures/process.ts"

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

describe("reload-nus-mode.sh in Claude Code", () => {
  let bundle: Bundle
  let model: FakeModel
  let home: string

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
        "claude-haiku-5-5",
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
        },
        stdin: "ignore",
        stderr: "pipe",
      },
    )
    const { code, stdout, stderr } = await finished(run)
    if (code !== 0)
      throw new Error(`claude exited with ${code}\nstderr: ${stderr}\nstdout: ${stdout}`)
    return JSON.parse(stdout).session_id
  }

  beforeAll(async () => {
    bundle = await Bundle.unpacked()
    model = new FakeModel("claude-code")
    home = await mkdtemp(join(tmpdir(), "nustack-claude-"))
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
    await Promise.all([bundle?.remove(), model?.stop(), home && rm(home, { recursive: true })])
  })

  test("sends nus-mode again after /compact", async () => {
    const session = await ask(null, FakeModel.LOAD)
    await ask(session, "/compact")
    await ask(session, FakeModel.AFTER)
    const sent = model.sentWith(FakeModel.AFTER)
    expect([
      sent.includes(bundle.needle),
      sent.includes(bundle.base),
      sent.includes(FakeModel.LOAD),
    ]).toEqual([true, true, false])
  })

  test("sends nus-mode again after an automatic summarization", async () => {
    const session = await ask(null, FakeModel.LOAD)
    await ask(session, FakeModel.FILL)
    await ask(session, FakeModel.AFTER)
    const sent = model.sentWith(FakeModel.AFTER)
    expect([
      sent.includes(bundle.needle),
      sent.includes(bundle.base),
      sent.includes(FakeModel.LOAD),
    ]).toEqual([true, true, false])
  })

  test("leaves nus-mode out after summarizing a session that invoked another plugin's nus-mode", async () => {
    const first = "/other:nus-mode"
    const session = await ask(null, first)
    await ask(session, "/compact")
    await ask(session, FakeModel.AFTER)
    const sent = model.sentWith(FakeModel.AFTER)
    expect([
      sent.includes(bundle.needle),
      sent.includes(bundle.base),
      sent.includes(first),
    ]).toEqual([false, false, false])
  })

  test("leaves nus-mode out after summarizing a session that never loaded it", async () => {
    const first = FakeModel.UNLOADED
    const session = await ask(null, first)
    await ask(session, "/compact")
    await ask(session, FakeModel.AFTER)
    const sent = model.sentWith(FakeModel.AFTER)
    expect([
      sent.includes(bundle.needle),
      sent.includes(bundle.base),
      sent.includes(first),
    ]).toEqual([false, false, false])
  })
})
