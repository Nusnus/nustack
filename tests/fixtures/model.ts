/**
 * A stand-in for Anthropic's Messages API, so the smoke tests need no API key. It keeps each request and answers with a
 * streamed reply the real API sent, in messages/: the host's summary or skill tool call, `full.reply` to the prompt that
 * fills the context window, and OK, `text.reply`, to anything else. It refuses, with the Messages API's 400 that names
 * the fault, a body that is not JSON, a field it reads whose shape does not fit, a request with no user message, as the
 * real API does, and a path it does not serve, so a host stops instead of retrying. `make smoke` runs it under both
 * real hosts; tests/integration/fixtures/model.test.ts tests it against the recorded requests and refusals.
 */
import { readFileSync } from "node:fs"
import { join } from "node:path"

/** The host whose skill tool and summary request the fake answers. */
export type Host = "claude-code" | "opencode"

/**
 * What the fake reads of one request a host sent: its last user message's last block, as JSON, and whether it offers a
 * skill tool. Each host puts a turn's prompt, a summary request's ask, a load prompt and the prompt that fills the
 * context window in that last block, while Claude Code's turn after a summary can hold that summary, which can quote
 * each, in an earlier block of the turn's own user message. OpenCode's turn after a summary can hold the summary in
 * that last block, before the prompt; its recorded summary quotes none of them.
 */
interface Reading {
  readonly lastBlock: string
  readonly offersSkill: boolean
}

/** A request the fake refuses. */
class RequestError extends Error {
  override name = "RequestError"
}

/** A turn a test looks for by a prompt that no request offering a skill tool held in its last block. */
export class TurnNotFoundError extends Error {
  override name = "TurnNotFoundError"
}

/** A local Messages API server that answers the hosts' requests and keeps each one for the tests to read. */
export class FakeModel {
  // The model the hosts ask for, by the ID each smoke test configures; the fake answers whatever model is asked.
  static readonly MODEL = "claude-haiku-5-5"
  static readonly LOAD = "Load nus-mode with the skill tool."
  static readonly LOAD_SAMPLE = "Load sample-mode with the skill tool."
  static readonly AFTER = "Reply OK after the summary."
  static readonly UNLOADED = "Reply OK without loading a skill."
  static readonly PROOFREAD = "Proofread this text; reply OK."
  static readonly FILL = "This prompt fills the context window."
  static readonly WINDOW = 200_000
  // Claude Code's summary request ends by asking for these two blocks; OpenCode's holds its summary template, as
  // tests/fixtures/messages/<host>/summary.request.json records.
  static readonly SUMMARY_ASKS = Object.freeze({
    "claude-code": "an <analysis> block followed by a <summary> block",
    opencode: "<template>",
  })
  // Only OpenCode's smoke tests load sample-mode, so only OpenCode has a recorded reply that loads it.
  private static readonly LOADS = Object.freeze({
    "claude-code": Object.freeze({ [FakeModel.LOAD]: "skill" }),
    opencode: Object.freeze({ [FakeModel.LOAD]: "skill", [FakeModel.LOAD_SAMPLE]: "sample-skill" }),
  })
  // Each recorded reply, beside the request it answered where one is recorded, as `<name>.request.json`.
  static readonly MESSAGES = join(import.meta.dirname, "messages")
  private readonly requests: (Reading & { readonly raw: string })[] = []
  private readonly server = Bun.serve({
    port: 0,
    fetch: (request) => this.answer(request),
    error: (error) => FakeModel.refusal(error),
  })
  readonly url = this.server.url.href.replace(/\/$/, "")

  constructor(private readonly host: Host) {}

  // The last request offering a skill tool whose last user message's last block holds the prompt: OpenCode's title
  // request quotes a session's first prompt, offers no skill tool and races that turn's request:
  // https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/runner/llm.ts#L58-L59
  turnWith(prompt: string): string {
    const found = this.requests.findLast(
      (request) => request.offersSkill && request.lastBlock.includes(prompt),
    )
    if (found === undefined)
      throw new TurnNotFoundError(
        `no request that offers a skill tool held the prompt ${JSON.stringify(prompt)} in its last user message's last block; send it in a turn before finding that turn`,
      )
    return found.raw
  }

  async stop(): Promise<void> {
    await this.server.stop(true)
  }

  private async answer(request: Request): Promise<Response> {
    const { pathname } = new URL(request.url)
    // Claude Code checks the API at /api/hello before its first turn.
    if (pathname === "/api/hello") return FakeModel.reply("hello", "application/json")
    if (pathname !== "/v1/messages")
      throw new RequestError(
        `the fake model serves only /v1/messages, not ${pathname}; send the request to /v1/messages`,
      )
    const raw = await request.text()
    const { lastBlock, offersSkill } = FakeModel.parsed(raw)
    this.requests.push({ raw, lastBlock, offersSkill })
    const load = Object.entries(FakeModel.LOADS[this.host]).find(([prompt]) =>
      lastBlock.includes(prompt),
    )
    if (lastBlock.includes(FakeModel.SUMMARY_ASKS[this.host]))
      return FakeModel.reply(`${this.host}/summary`)
    if (offersSkill && load !== undefined) return FakeModel.reply(`${this.host}/${load[1]}`)
    // full.reply is the real reply to "Reply OK. " followed by "OK " 99,496 times, 199,006 tokens, which makes a host
    // summarize on its own once its test holds it to WINDOW; that 300 KB request is not recorded.
    return FakeModel.reply(lastBlock.includes(FakeModel.FILL) ? "full" : "text")
  }

  // Reads the fields the fake uses from a body a host sent: https://docs.anthropic.com/en/api/messages
  private static parsed(raw: string): Reading {
    let body: unknown
    try {
      body = JSON.parse(raw)
    } catch {
      throw new RequestError("the request body is not JSON; send it as a JSON object")
    }
    const request = objectAt("the request body", body)
    const messages = listAt("messages", request.get("messages")).map((each, index) => {
      const path = `messages[${index}]`
      const message = objectAt(path, each)
      const role = textAt(`${path}.role`, message.get("role"))
      if (!message.has("content"))
        throw new RequestError(`${path}.content is missing; give the message its content`)
      return { role, content: message.get("content") }
    })
    const last = messages.findLastIndex((message) => message.role === "user")
    if (last === -1)
      throw new RequestError(
        "the request holds no user message, which the Messages API requires; give it one",
      )
    const content = messages[last]?.content
    if (typeof content !== "string" && !Array.isArray(content))
      throw new RequestError(
        `messages[${last}].content must be text or a list, got ${kindOf(content)}; send it as a JSON string or array`,
      )
    if (Array.isArray(content) && content.length === 0)
      throw new RequestError(
        `messages[${last}].content is an empty list; give the last user message at least one content block`,
      )
    const block =
      typeof content === "string"
        ? content
        : objectAt(`messages[${last}].content's last block`, content.at(-1))
    const tools = request.has("tools") ? listAt("tools", request.get("tools")) : []
    const names = tools.map((each, index) =>
      textAt(`tools[${index}].name`, objectAt(`tools[${index}]`, each).get("name")),
    )
    return {
      lastBlock: JSON.stringify(typeof block === "string" ? block : Object.fromEntries(block)),
      offersSkill: names.some((name) => name.toLowerCase() === "skill"),
    }
  }

  // The Messages API's answer to a request it refuses: https://docs.anthropic.com/en/api/errors
  private static refusal(error: Error): Response {
    const body = { type: "error", error: { type: "invalid_request_error", message: error.message } }
    return Response.json(body, { status: 400 })
  }

  private static reply(name: string, type = "text/event-stream"): Response {
    const text = readFileSync(join(FakeModel.MESSAGES, `${name}.reply`), "utf8")
    return new Response(text, { headers: { "content-type": type } })
  }
}

function objectAt(path: string, value: unknown): ReadonlyMap<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    throw new RequestError(
      `${path} must be an object, got ${kindOf(value)}; send it as a JSON object`,
    )
  return new Map(Object.entries(value))
}

function listAt(path: string, value: unknown): readonly unknown[] {
  if (!Array.isArray(value))
    throw new RequestError(`${path} must be a list, got ${kindOf(value)}; send it as a JSON array`)
  return value
}

function textAt(path: string, value: unknown): string {
  if (typeof value !== "string")
    throw new RequestError(`${path} must be text, got ${kindOf(value)}; send it as a JSON string`)
  return value
}

function kindOf(value: unknown): string {
  if (value === undefined) return "nothing"
  if (value === null) return "null"
  if (Array.isArray(value)) return "a list"
  return typeof value === "object" ? "an object" : `a ${typeof value}`
}
