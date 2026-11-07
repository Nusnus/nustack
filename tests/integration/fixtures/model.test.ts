/**
 * The fake Messages API answers Claude Code's /api/hello check and each request recorded in tests/fixtures/messages
 * beside its `<name>.reply` with the reply the real API sent it, and the prompt that fills the context window with the
 * real reply to a full window. It answers OK to OpenCode's title request, to Claude Code's request to load sample-mode,
 * to a request whose last user message holds a skill load's result, to Claude Code's turn whose user message holds a
 * summary before its prompt, and to a request with an empty system message. It keeps every Messages API request it
 * answers and finds a session's turn: the last request that offers a skill tool and holds a given prompt in its last
 * user message's last block. It refuses a body that is not JSON, a request with no user message, as the real API does,
 * a last user message whose content is neither text nor a list whose last item is an object, any other field it reads
 * whose shape does not fit, and a path it does not serve, each with the Messages API's error body.
 */
import { afterAll, describe, expect, test } from "bun:test"
import { readFile } from "node:fs/promises"
import { join } from "node:path"
import { FakeModel, type Host, TurnNotFoundError } from "../../fixtures/model.ts"
import { thrown } from "../../fixtures/thrown.ts"

/**
 * FakeModel keeps each Messages API request it answers and finds a session's turn: the last request that offers a skill
 * tool and holds a given prompt in its last user message's last block, even after a summary in an earlier block, past a
 * later title request, which offers no skill tool, and a later summary request, which holds that prompt only in an
 * earlier block; finding a prompt no such request held fails. Each recorded request beside its `<name>.reply` draws the
 * real API's reply to it, and so does a summary request whose ask ends a list of blocks. These draw OK: OpenCode's
 * title request, which quotes the load prompt but offers no skill tool; Claude Code's request after its skill tool
 * loaded the mode, whose last user message holds no load prompt; Claude Code's request to load sample-mode, since only
 * OpenCode's smoke tests load it; Claude Code's first turn after a summary, whose user message holds the summary, which
 * quotes the summary request's ask, a load prompt or the prompt that fills the context window, before its prompt; and a
 * request with an empty system message, as Claude Code sends after /compact in the session that loads nustack's
 * nus-mode. The reply to a full context window goes only to the prompt that fills it. A body that breaks the shape the
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

  function realReply(name: string): Promise<string> {
    return readFile(join(FakeModel.MESSAGES, `${name}.reply`), "utf8")
  }

  test.each([
    [
      "a path it does not serve",
      "/v1/models",
      { messages: [] },
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
      "a request with no user message",
      "/v1/messages",
      { messages: [] },
      "the request holds no user message, which the Messages API requires; give it a user message",
    ],
    [
      "a last user message whose content is a number",
      "/v1/messages",
      { messages: [{ role: "user", content: 1 }] },
      "messages[0].content must be text or a list, got a number; send it as a JSON string or array",
    ],
    [
      "a last user message whose content is an empty list",
      "/v1/messages",
      {
        messages: [
          { role: "user", content: "Hi." },
          { role: "user", content: [] },
        ],
      },
      "messages[1].content is an empty list; give the last user message at least one content block",
    ],
    [
      "a last user message whose last block is not an object",
      "/v1/messages",
      { messages: [{ role: "user", content: [{ type: "text", text: "Hi." }, 1] }] },
      "messages[0].content[1] must be an object, got a number; send it as a JSON object",
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
    const reply = await fetch(`${models.opencode.url}${path}`, {
      method: "POST",
      body: typeof body === "string" ? body : JSON.stringify(body),
    })
    expect([reply.status, await reply.json()]).toEqual([
      400,
      { type: "error", error: { type: "invalid_request_error", message } },
    ])
  })

  test("keeps each Messages API request and finds the last one that offers a skill tool and holds a prompt", async () => {
    const tools = [{ name: "Skill" }]
    const first = JSON.stringify({ messages: [{ role: "user", content: "Kept." }], tools, n: 1 })
    const last = JSON.stringify({ messages: [{ role: "user", content: "Kept." }], tools, n: 2 })
    const title = JSON.stringify({ messages: [{ role: "user", content: '"Kept."' }] })
    await post("claude-code", first)
    await post("claude-code", last)
    await post("claude-code", title)
    expect(models["claude-code"].turnWith("Kept.")).toBe(last)
  })

  test("finds Claude Code's turn whose user message holds a summary before its prompt", async () => {
    const turn = JSON.stringify({
      messages: [
        {
          role: "user",
          content: [
            {
              type: "text",
              text: `Summary, asked for as ${FakeModel.SUMMARY_ASKS["claude-code"]}.`,
            },
            { type: "text", text: "Resumed." },
          ],
        },
      ],
      tools: [{ name: "Skill" }],
    })
    await post("claude-code", turn)
    expect(models["claude-code"].turnWith("Resumed.")).toBe(turn)
  })

  test("finds a turn past a later summary request that offers a skill tool and holds its prompt", async () => {
    const tools = [{ name: "Skill" }]
    const turn = JSON.stringify({ messages: [{ role: "user", content: "Summarized." }], tools })
    const summary = JSON.stringify({
      messages: [
        {
          role: "user",
          content: [
            { type: "text", text: "Summarized." },
            { type: "text", text: FakeModel.SUMMARY_ASKS["claude-code"] },
          ],
        },
      ],
      tools,
    })
    await post("claude-code", turn)
    await post("claude-code", summary)
    expect(models["claude-code"].turnWith("Summarized.")).toBe(turn)
  })

  test.each([
    [
      "no request held",
      "Never sent.",
      JSON.stringify({
        messages: [{ role: "user", content: "Another turn." }],
        tools: [{ name: "skill" }],
      }),
      new TurnNotFoundError(
        'no request that offers a skill tool held the prompt "Never sent." in its last user message\'s last block; send it in a turn before finding that turn',
      ),
    ],
    [
      "only a request without a skill tool held",
      "Only titled.",
      JSON.stringify({ messages: [{ role: "user", content: "Only titled." }] }),
      new TurnNotFoundError(
        'no request that offers a skill tool held the prompt "Only titled." in its last user message\'s last block; send it in a turn before finding that turn',
      ),
    ],
  ])("fails to find a turn whose prompt %s", async (_case, prompt, body, error) => {
    await post("opencode", body)
    expect(await thrown(() => models.opencode.turnWith(prompt))).toEqual(error)
  })

  test("answers Claude Code's /api/hello check with the real API's reply", async () => {
    const reply = await fetch(`${models["claude-code"].url}/api/hello`)
    expect(await reply.text()).toBe(await realReply("hello"))
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
    expect(await post(host, request)).toBe(await realReply(name))
  })

  test("answers Claude Code's summary request whose ask ends a list of blocks with the real API's reply", async () => {
    // Shaped as the smoke tests' Claude Code sends its summary request on /compact after a skill loaded: the skill
    // load's result and the skill's text come before the block that asks for the summary.
    const request = {
      messages: [
        {
          role: "user",
          content: [
            { type: "tool_result", tool_use_id: "toolu_1", content: "Launching skill: nus-mode" },
            { type: "text", text: "Base directory for this skill: nus-mode" },
            { type: "text", text: `Reply with ${FakeModel.SUMMARY_ASKS["claude-code"]}.` },
          ],
        },
      ],
    }
    expect(await post("claude-code", JSON.stringify(request))).toBe(
      await realReply("claude-code/summary"),
    )
  })

  test.each([
    ["the summary request's ask", FakeModel.SUMMARY_ASKS["claude-code"]],
    ["the load prompt", FakeModel.LOAD],
    ["the prompt that fills the context window", FakeModel.FILL],
  ])(
    "answers OK to Claude Code's turn whose summary quotes %s before its prompt",
    async (_case, quoted) => {
      // Shaped as the smoke tests' Claude Code can send its first turn after a summary: the turn's own user message
      // opens with a system reminder, then holds the summary and ends with the prompt.
      const request = {
        tools: [{ name: "Skill" }],
        messages: [
          {
            role: "user",
            content: [
              { type: "text", text: "<system-reminder>A reminder.</system-reminder>" },
              { type: "text", text: `Summary, quoting ${quoted}` },
              { type: "text", text: FakeModel.AFTER },
            ],
          },
        ],
      }
      expect(await post("claude-code", JSON.stringify(request))).toBe(await realReply("text"))
    },
  )

  test("answers OK to Claude Code's request that holds a system message whose content is an empty list", async () => {
    // Shaped as the smoke tests' Claude Code sends its turn after /compact in the session that loads nustack's
    // nus-mode: an empty system message follows the first user message, and a system message ends the request.
    const request = {
      messages: [
        { role: "user", content: "Hi." },
        { role: "system", content: [] },
        { role: "assistant", content: "OK" },
        { role: "user", content: FakeModel.AFTER },
        { role: "system", content: [] },
      ],
    }
    expect(await post("claude-code", JSON.stringify(request))).toBe(await realReply("text"))
  })

  test("answers OK to Claude Code's request that offers its skill tool and asks to load sample-mode", async () => {
    const request = {
      tools: [{ name: "Skill" }],
      messages: [{ role: "user", content: FakeModel.LOAD_SAMPLE }],
    }
    expect(await post("claude-code", JSON.stringify(request))).toBe(await realReply("text"))
  })

  test("answers OK to OpenCode's title request, which quotes the load prompt but offers no skill tool", async () => {
    const request = await readFile(
      join(FakeModel.MESSAGES, "opencode", "title.request.json"),
      "utf8",
    )
    expect(await post("opencode", request)).toBe(await realReply("text"))
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
    expect(await post("claude-code", request)).toBe(await realReply("text"))
  })

  test("answers the prompt that fills the context window with the real reply to a full window", async () => {
    const reply = await post(
      "opencode",
      JSON.stringify({ messages: [{ role: "user", content: FakeModel.FILL }] }),
    )
    expect([reply, reply.includes('"input_tokens":199006')]).toEqual([
      await realReply("full"),
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
