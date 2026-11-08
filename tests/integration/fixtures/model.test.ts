/**
 * The fake model answers Claude Code's /api/hello check and each recorded request with the reply the real API sent it,
 * the prompt that fills the context window with the real reply to a full window, and OK to anything else, such as
 * OpenCode's title request, Claude Code's request to load sample-mode, a request whose last user message holds a skill
 * load's result, and Claude Code's turn whose user message holds a summary before its prompt. It finds a session's
 * turn: the last request that offers a skill tool and holds a prompt in its last user message's last block. It refuses
 * each request whose shape it cannot read with the Messages API's 400, whose message names the fault.
 */
import { afterAll, describe, expect, test } from "bun:test"
import { readFile } from "node:fs/promises"
import { join } from "node:path"
import { FakeModel, type Host, TurnNotFoundError } from "../../fixtures/model.ts"
import { thrown } from "../../fixtures/thrown.ts"

/** Each host gets the real API's replies, and a test finds the turn it looks for. */
describe("FakeModel", () => {
  const models = {
    "claude-code": new FakeModel("claude-code"),
    opencode: new FakeModel("opencode"),
  }
  const model = models.opencode
  const tools = [{ name: "Skill" }]

  afterAll(() => Promise.all(Object.values(models).map((each) => each.stop())))

  async function post(host: Host, body: unknown): Promise<string> {
    const text = typeof body === "string" ? body : JSON.stringify(body)
    return (await fetch(`${models[host].url}/v1/messages`, { method: "POST", body: text })).text()
  }

  function recorded(name: string, kind: "reply" | "request.json" = "reply"): Promise<string> {
    return readFile(join(FakeModel.MESSAGES, `${name}.${kind}`), "utf8")
  }

  test("finds the last turn that offers a skill tool and holds the prompt, past a later title request", async () => {
    const first = JSON.stringify({ messages: [{ role: "user", content: "Kept." }], tools, n: 1 })
    const last = JSON.stringify({ messages: [{ role: "user", content: "Kept." }], tools, n: 2 })
    await post("claude-code", first)
    await post("claude-code", last)
    await post("claude-code", { messages: [{ role: "user", content: '"Kept."' }] })
    expect(models["claude-code"].turnWith("Kept.")).toBe(last)
  })

  test("finds Claude Code's turn whose user message holds a summary before its prompt", async () => {
    const summary = {
      type: "text",
      text: `Summary, asked for as ${FakeModel.SUMMARY_ASKS["claude-code"]}.`,
    }
    const content = [summary, { type: "text", text: "Resumed." }]
    const turn = JSON.stringify({ messages: [{ role: "user", content }], tools })
    await post("claude-code", turn)
    expect(models["claude-code"].turnWith("Resumed.")).toBe(turn)
  })

  test("finds a turn past a later summary request that holds its prompt in an earlier block", async () => {
    const turn = JSON.stringify({ messages: [{ role: "user", content: "Summarized." }], tools })
    const ask = { type: "text", text: FakeModel.SUMMARY_ASKS["claude-code"] }
    const content = [{ type: "text", text: "Summarized." }, ask]
    await post("claude-code", turn)
    await post("claude-code", { messages: [{ role: "user", content }], tools })
    expect(models["claude-code"].turnWith("Summarized.")).toBe(turn)
  })

  test.each([
    ["no request held", "Never sent.", { messages: [{ role: "user", content: "Other." }], tools }],
  ])("fails to find a turn whose prompt %s", async (_case, prompt, body) => {
    await post("opencode", body)
    expect(await thrown(() => model.turnWith(prompt))).toEqual(
      new TurnNotFoundError(
        `no request that offers a skill tool held the prompt ${JSON.stringify(prompt)} in its last user message's last block; send it in a turn before finding that turn`,
      ),
    )
  })

  test("answers Claude Code's /api/hello check with the real API's reply, as JSON", async () => {
    const reply = await fetch(`${models["claude-code"].url}/api/hello`)
    expect([reply.headers.get("content-type"), await reply.text()]).toEqual([
      "application/json",
      await recorded("hello"),
    ])
  })

  test.each<[string, Host]>([
    ["text", "claude-code"],
    ["claude-code/summary", "claude-code"],
    ["opencode/summary", "opencode"],
    ["claude-code/skill", "claude-code"],
    ["opencode/skill", "opencode"],
    ["opencode/sample-skill", "opencode"],
  ])("answers the recorded %s request with the real API's reply", async (name, host) => {
    expect(await post(host, await recorded(name, "request.json"))).toBe(await recorded(name))
  })

  test.each<[string, Host, string]>([
    [
      "OpenCode's title request, which quotes the load prompt but offers no skill tool",
      "opencode",
      "opencode/title",
    ],
    [
      "Claude Code's request after its skill tool loaded the mode",
      "claude-code",
      "claude-code/skill-result",
    ],
  ])("answers OK to %s", async (_case, host, name) => {
    expect(await post(host, await recorded(name, "request.json"))).toBe(await recorded("text"))
  })

  test("answers OK to Claude Code's request to load sample-mode, which only OpenCode's smoke tests load", async () => {
    const request = { tools, messages: [{ role: "user", content: FakeModel.LOAD_SAMPLE }] }
    expect(await post("claude-code", request)).toBe(await recorded("text"))
  })

  test("answers OK to a request that holds a system message whose content is an empty list", async () => {
    // As Claude Code sends its turn after /compact in a session that loaded nus-mode.
    const messages = [
      { role: "user", content: "Hi." },
      { role: "system", content: [] },
      { role: "user", content: FakeModel.AFTER },
      { role: "system", content: [] },
    ]
    expect(await post("claude-code", { messages })).toBe(await recorded("text"))
  })

  test.each([
    ["the summary request's ask", FakeModel.SUMMARY_ASKS["claude-code"]],
    ["the load prompt", FakeModel.LOAD],
    ["the prompt that fills the context window", FakeModel.FILL],
  ])(
    "answers OK to Claude Code's turn whose summary quotes %s before its prompt",
    async (_case, quoted) => {
      const content = [
        { type: "text", text: `Summary, quoting ${quoted}` },
        { type: "text", text: FakeModel.AFTER },
      ]
      expect(await post("claude-code", { tools, messages: [{ role: "user", content }] })).toBe(
        await recorded("text"),
      )
    },
  )

  test("answers the prompt that fills the context window with the real reply to a full window, as a stream", async () => {
    const reply = await fetch(`${model.url}/v1/messages`, {
      method: "POST",
      body: JSON.stringify({ messages: [{ role: "user", content: FakeModel.FILL }] }),
    })
    const text = await reply.text()
    expect([
      reply.headers.get("content-type"),
      text,
      text.includes('"input_tokens":199006'),
    ]).toEqual(["text/event-stream", await recorded("full"), true])
  })

  test.each([
    [
      "a path it does not serve",
      "/v1/models",
      {},
      "the fake model serves only /v1/messages, not /v1/models; send the request to /v1/messages",
    ],
    [
      "a body that is not JSON",
      "/v1/messages",
      "not JSON",
      "the request body is not JSON; send it as a JSON object",
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
      "a message without content",
      "/v1/messages",
      { messages: [{ role: "user" }] },
      "messages[0].content is missing; give the message its content",
    ],
    [
      "a request with no user message",
      "/v1/messages",
      { messages: [{ role: "assistant", content: "OK" }] },
      "the request holds no user message, which the Messages API requires; give it one",
    ],
    [
      "a last user message whose content is a number",
      "/v1/messages",
      {
        messages: [
          { role: "user", content: "Hi." },
          { role: "user", content: 1 },
        ],
      },
      "messages[1].content must be text or a list, got a number; send it as a JSON string or array",
    ],
    [
      "a last user message with no blocks",
      "/v1/messages",
      { messages: [{ role: "user", content: [] }] },
      "messages[0].content is an empty list; give the last user message at least one content block",
    ],
    [
      "a last user message whose last block is not an object",
      "/v1/messages",
      { messages: [{ role: "user", content: [{ type: "text", text: "Hi." }, 1] }] },
      "messages[0].content's last block must be an object, got a number; send it as a JSON object",
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
  ])("refuses %s with the Messages API's error body", async (_case, path, body, message) => {
    const reply = await fetch(`${model.url}${path}`, {
      method: "POST",
      body: typeof body === "string" ? body : JSON.stringify(body),
    })
    expect([reply.status, await reply.json()]).toEqual([
      400,
      { type: "error", error: { type: "invalid_request_error", message } },
    ])
  })
})
