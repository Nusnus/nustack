/**
 * Claude Code, running the release zip against tests/fixtures/model.ts, offers the model each vendored skill under the
 * plugin's name, and re-attaches nus-mode's folder and body after a manual or an automatic summary of a session that
 * loaded it, as its skills docs say: https://code.claude.com/docs/en/skills#skill-content-lifecycle. Those docs promise
 * nothing for a skill invoked before a session was resumed, so each session runs in one process, its prompts sent on
 * stdin.
 */
import { afterAll, beforeAll, expect, test } from "bun:test"
import { join } from "node:path"
import { Bundle } from "../../fixtures/bundle.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"
import { FakeModel } from "../../fixtures/model.ts"
import { VENDORED_SKILLS } from "../../fixtures/vendored.ts"

/** claude failed while a smoke test drove it. */
class ClaudeError extends Error {
  override name = "ClaudeError"
}

const claude = join(import.meta.dirname, "../../fixtures/smoke/node_modules/.bin/claude")
const folders = new TemporaryFolders()
const model = new FakeModel("claude-code")
let bundle: Bundle

beforeAll(async () => {
  bundle = await Bundle.unpacked(undefined, await folders.make())
})

afterAll(async () => {
  await Promise.all([model.stop(), folders.clear()])
})

// Sends each prompt once Claude Code answers the last, as stream-json: https://code.claude.com/docs/en/cli-reference
async function session(...prompts: string[]): Promise<void> {
  const home = await folders.make()
  const flags = ["--input-format", "stream-json", "--output-format", "stream-json", "--verbose"]
  const args = ["-p", "--model", FakeModel.MODEL, "--allowedTools=Skill", "--plugin-dir"]
  // Claude Code gives FakeModel.MODEL a window FakeModel.FILL leaves far from full, so it is held to the fake's:
  // https://code.claude.com/docs/en/model-config#set-the-auto-compact-window
  const env = { HOME: home, PATH: process.env.PATH, ANTHROPIC_BASE_URL: model.url }
  const fake = { ANTHROPIC_API_KEY: "fake", CLAUDE_CODE_AUTO_COMPACT_WINDOW: `${FakeModel.WINDOW}` }
  const options = { cwd: home, env: { ...env, ...fake }, stdin: "pipe", stderr: "inherit" } as const
  const child = Bun.spawn([claude, ...args, bundle.root, ...flags], options)
  const message = (content: string) =>
    `${JSON.stringify({ type: "user", message: { role: "user", content } })}\n`
  const send = (content = prompts.shift()) =>
    content === undefined ? child.stdin.end() : child.stdin.write(message(content))
  send()
  let output = ""
  for await (const chunk of child.stdout.pipeThrough(new TextDecoderStream())) {
    const lines = (output + chunk).split("\n")
    output = lines.pop() ?? ""
    for (const line of lines) if (JSON.parse(line).type === "result") send()
  }
  const code = await child.exited
  if (code !== 0) throw new ClaudeError(`claude exited ${code}; its stderr is above`)
}

test("offers the model each vendored skill", async () => {
  await session(FakeModel.UNLOADED)
  const turn = model.turnWith(FakeModel.UNLOADED)
  expect(VENDORED_SKILLS.filter((name) => !turn.includes(`nustack:${name}`))).toEqual([])
})

test.each<[string, boolean, string, string]>([
  ["loaded it, summarized on request", true, FakeModel.LOAD, "/compact"],
  ["loaded it, auto-summarized", true, FakeModel.LOAD, FakeModel.FILL],
  ["invoked it, summarized on request", true, "/nustack:nus-mode", "/compact"],
  ["never loaded it", false, FakeModel.UNLOADED, "/compact"],
])("a session that %s gets nus-mode back: %p", async (_case, sent, first, summarize) => {
  await session(first, summarize, FakeModel.AFTER)
  const turn = model.turnWith(FakeModel.AFTER)
  expect([
    turn.includes(bundle.escapedBody),
    turn.includes(bundle.base),
    turn.includes(first),
  ]).toEqual([sent, sent, false])
})
