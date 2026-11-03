/**
 * The fake Messages API answers each request recorded in tests/fixtures/messages, and Claude Code's /api/hello check,
 * with the reply the real API sent it, keeps every request it answers, and refuses a request the real API refuses or a
 * path it does not serve with the Messages API's error body.
 */
import { afterAll, describe, expect, test } from "bun:test"
import { readFile } from "node:fs/promises"
import { join } from "node:path"
import { FakeModel, type Host } from "../../fixtures/model.ts"

/**
 * Each recorded request draws the real API's reply to it, and the reply to a full context window only to the prompt
 * that fills it. Finding a prompt no request held fails.
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

  test("keeps each request and finds the last one holding a prompt", async () => {
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

  test.each<[string, Host]>([
    ["text", "claude-code"],
    ["claude-code/skill", "claude-code"],
    ["opencode/skill", "opencode"],
    ["opencode/sample-skill", "opencode"],
    ["claude-code/summary", "claude-code"],
    ["opencode/summary", "opencode"],
  ])("answers the recorded %s request with the real API's reply", async (name, host) => {
    const request = await readFile(join(FakeModel.MESSAGES, `${name}.request.json`), "utf8")
    expect(await post(host, request)).toBe(FakeModel.recorded(name))
  })

  test("answers Claude Code's /api/hello check with the real API's reply", async () => {
    const reply = await fetch(`${models["claude-code"].url}/api/hello`)
    expect(await reply.text()).toBe(FakeModel.recorded("hello"))
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

  test.each([
    [
      // No recorded request asks to load the mode without the skill tool; this one stands for a host that offers none.
      "offers no skill tool",
      { messages: [{ role: "user", content: FakeModel.LOAD }] },
    ],
    [
      // No recorded request answers the skill call with the load prompt in its result; this one stands for the turn
      // after the skill tool ran.
      "answers the skill call",
      {
        tools: [{ name: "Skill" }],
        messages: [{ role: "user", content: [{ type: "tool_result", content: FakeModel.LOAD }] }],
      },
    ],
  ])("answers OK to a load prompt in a request that %s", async (_case, request) => {
    expect(await post("claude-code", JSON.stringify(request))).toBe(FakeModel.recorded("text"))
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
