/**
 * The fake Messages API answers Claude Code's /api/hello check, and each request recorded in tests/fixtures/messages
 * beside its `<name>.reply`, with the reply the real API sent it, and the prompt that fills the context window with the
 * real reply to a full window. It answers OK to OpenCode's title request, to Claude Code's request to load sample-mode
 * and to a request whose last user message holds the result of loading a skill. It keeps every Messages API request it
 * answers and finds the last one holding a prompt, and refuses a request with no user message, as the real API does, a
 * body that is not a Messages API request, naming the field that does not fit, or a path it does not serve, with the
 * Messages API's error body.
 */
import { afterAll, describe, expect, test } from "bun:test"
import { readFile } from "node:fs/promises"
import { join } from "node:path"
import { FakeModel, type Host, PromptNotSentError } from "../../fixtures/model.ts"
import { thrown } from "../../fixtures/thrown.ts"

/**
 * FakeModel keeps each Messages API request it answers and finds the last one holding a prompt, and finding a prompt no
 * request held fails. Each recorded request beside its `<name>.reply` draws the real API's reply to it. Two requests
 * cut to what the fake reads draw OK: OpenCode's title request, which quotes the load prompt but offers no skill tool,
 * and Claude Code's request after its skill tool loaded the mode, whose last user message holds no load prompt. Claude
 * Code's request that offers its skill tool and asks for sample-mode draws OK too, since only OpenCode's smoke tests
 * load it. The reply to a full context window goes only to the prompt that fills it. A body that breaks the shape the
 * fake reads, in each field it reads, is refused with that field's path.
 */
describe("FakeModel", () => {
  const models = {
    "claude-code": new FakeModel("claude-code"),
    opencode: new FakeModel("opencode"),
  }

  afterAll(async () => {
    await Promise.all(Object.values(models).map((model) => model.stop()))
  })

  async function post(host: Host, body: string): Promise<string> {
    return (await fetch(`${models[host].url}/v1/messages`, { method: "POST", body })).text()
  }

  test.each([
    [
      "a request with no user message",
      "/v1/messages",
      { messages: [] },
      "the request holds no user message, which the Messages API requires",
    ],
    [
      "a body that is not an object",
      "/v1/messages",
      [],
      "the request body must be an object, got a list; send it as a JSON object",
    ],
    [
      "a body without messages",
      "/v1/messages",
      {},
      "messages must be a list, got nothing; send it as a JSON array",
    ],
    [
      "a body whose messages are not a list",
      "/v1/messages",
      { messages: "Hi." },
      "messages must be a list, got a string; send it as a JSON array",
    ],
    [
      "a message that is not an object",
      "/v1/messages",
      { messages: ["Hi."] },
      "messages[0] must be an object, got a string; send it as a JSON object",
    ],
    [
      "a message without a role",
      "/v1/messages",
      { messages: [{ role: "user", content: "Hi." }, { content: "Hi." }] },
      "messages[1].role must be text, got nothing; send it as a JSON string",
    ],
    [
      "a message whose role is null",
      "/v1/messages",
      { messages: [{ role: null, content: "Hi." }] },
      "messages[0].role must be text, got null; send it as a JSON string",
    ],
    [
      "a message without content",
      "/v1/messages",
      { messages: [{ role: "user" }] },
      "messages[0].content is missing; give the message its content",
    ],
    [
      "tools that are not a list",
      "/v1/messages",
      { messages: [{ role: "user", content: "Hi." }], tools: {} },
      "tools must be a list, got an object; send it as a JSON array",
    ],
    [
      "a tool that is not an object",
      "/v1/messages",
      { messages: [{ role: "user", content: "Hi." }], tools: ["skill"] },
      "tools[0] must be an object, got a string; send it as a JSON object",
    ],
    [
      "a tool without a name",
      "/v1/messages",
      { messages: [{ role: "user", content: "Hi." }], tools: [{ name: "skill" }, {}] },
      "tools[1].name must be text, got nothing; send it as a JSON string",
    ],
    [
      "a path it does not serve",
      "/v1/models",
      { messages: [] },
      "the fake model serves only /v1/messages, not /v1/models",
    ],
  ])("refuses %s with the Messages API's error body", async (_case, path, body, message) => {
    const reply = await fetch(`${models.opencode.url}${path}`, {
      method: "POST",
      body: JSON.stringify(body),
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

  test("fails to find a prompt that no request held", async () => {
    expect(await thrown(() => models.opencode.sentWith("Never sent."))).toEqual(
      new PromptNotSentError('no request held the prompt "Never sent."'),
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
