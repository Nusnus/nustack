/**
 * The fake Messages API answers Claude Code's /api/hello check, and each request recorded in tests/fixtures/messages
 * beside its `<name>.reply`, with the reply the real API sent it, and the prompt that fills the context window with the
 * real reply to a full window. It answers OK to OpenCode's title request, to Claude Code's request to load sample-mode
 * and to a request whose last user message holds the result of loading a skill. It keeps every Messages API request it
 * answers and finds the last one holding a prompt, and refuses a request with no user message, as the real API does, or
 * a path it does not serve, with the Messages API's error body.
 */
import { afterAll, describe, expect, test } from "bun:test"
import { readFile } from "node:fs/promises"
import { join } from "node:path"
import { FakeModel, type Host } from "../../fixtures/model.ts"

/**
 * FakeModel keeps each Messages API request it answers and finds the last one holding a prompt, and finding a prompt no
 * request held fails. Each recorded request beside its `<name>.reply` draws the real API's reply to it. Two requests
 * cut to what the fake reads draw OK: OpenCode's title request, which quotes the load prompt but offers no skill tool,
 * and Claude Code's request after its skill tool loaded the mode, whose last user message holds no load prompt. Claude
 * Code's request that offers its skill tool and asks for sample-mode draws OK too, since only OpenCode's smoke tests
 * load it. The reply to a full context window goes only to the prompt that fills it.
 */
describe("FakeModel", () => {
  const models = {
    "claude-code": new FakeModel("claude-code"),
    opencode: new FakeModel("opencode"),
  }

  async function post(host: Host, body: string): Promise<string> {
    return (await fetch(`${models[host].url}/v1/messages`, { method: "POST", body })).text()
  }

  afterAll(async () => {
    await Promise.all(Object.values(models).map((model) => model.stop()))
  })

  test.each([
    [
      "a request with no user message",
      "/v1/messages",
      "the request holds no user message, which the Messages API requires",
    ],
    [
      "a path it does not serve",
      "/v1/models",
      "the fake model serves only /v1/messages, not /v1/models",
    ],
  ])("refuses %s with the Messages API's error body", async (_case, path, message) => {
    const reply = await fetch(`${models.opencode.url}${path}`, {
      method: "POST",
      body: JSON.stringify({ messages: [] }),
    })
    expect([reply.status, await reply.json()]).toEqual([
      400,
      { type: "error", error: { type: "invalid_request_error", message } },
    ])
  })

  test("keeps each Messages API request and finds the last one holding a prompt", async () => {
    const first = JSON.stringify({ messages: [{ role: "user", content: "Kept." }], n: 1 })
    const last = JSON.stringify({ messages: [{ role: "user", content: "Kept." }], n: 2 })
    await post("claude-code", first)
    await post("claude-code", last)
    expect(models["claude-code"].sentWith("Kept.")).toBe(last)
  })

  test("fails to find a prompt that no request held", () => {
    expect(() => models.opencode.sentWith("Never sent.")).toThrow(
      'no request held the prompt "Never sent."',
    )
  })

  test("answers Claude Code's /api/hello check with the real API's reply", async () => {
    const reply = await fetch(`${models["claude-code"].url}/api/hello`)
    expect(await reply.text()).toBe(FakeModel.recorded("hello"))
  })

  test.each<[string, Host]>([
    ["text", "claude-code"],
    ["claude-code/summary", "claude-code"],
    ["opencode/summary", "opencode"],
    ["claude-code/skill", "claude-code"],
    ["opencode/skill", "opencode"],
    ["opencode/sample-skill", "opencode"],
  ])("answers the recorded %s request with the real API's reply", async (name, host) => {
    const request = await readFile(join(FakeModel.MESSAGES, `${name}.request.json`), "utf8")
    expect(await post(host, request)).toBe(FakeModel.recorded(name))
  })

  test("answers OK to Claude Code's request that offers its skill tool and asks to load sample-mode", async () => {
    const request = {
      tools: [{ name: "Skill" }],
      messages: [{ role: "user", content: FakeModel.LOAD_SAMPLE }],
    }
    expect(await post("claude-code", JSON.stringify(request))).toBe(FakeModel.recorded("text"))
  })

  test("answers OK to OpenCode's title request, which quotes the load prompt but offers no skill tool", async () => {
    const request = await readFile(
      join(FakeModel.MESSAGES, "opencode", "title.request.json"),
      "utf8",
    )
    expect(await post("opencode", request)).toBe(FakeModel.recorded("text"))
  })

  test("answers OK to Claude Code's request after its skill tool loaded the mode", async () => {
    // Cut from a request the smoke tests' Claude Code sent, down to the tool names and the messages, with the loaded
    // SKILL.md cut to its opening: it offers the skill tool, and only an earlier message than its last user message
    // holds the load prompt. The fake reads none of what was dropped: model, max_tokens, stream, system, metadata,
    // which holds the machine's device_id, thinking, context_management and output_config.
    const request = await readFile(
      join(FakeModel.MESSAGES, "claude-code", "skill-result.request.json"),
      "utf8",
    )
    expect(await post("claude-code", request)).toBe(FakeModel.recorded("text"))
  })

  test("answers the prompt that fills the context window with the real reply to a full window", async () => {
    const reply = await post(
      "opencode",
      JSON.stringify({ messages: [{ role: "user", content: FakeModel.FILL }] }),
    )
    expect([reply, reply.includes('"input_tokens":199006')]).toEqual([
      FakeModel.recorded("full"),
      true,
    ])
  })

  test("answers with the content types the real API sends", async () => {
    const hello = await fetch(`${models["claude-code"].url}/api/hello`)
    const text = await readFile(join(FakeModel.MESSAGES, "text.request.json"), "utf8")
    const reply = await fetch(`${models["claude-code"].url}/v1/messages`, {
      method: "POST",
      body: text,
    })
    expect([hello.headers.get("content-type"), reply.headers.get("content-type")]).toEqual([
      "application/json",
      "text/event-stream",
    ])
  })
})
