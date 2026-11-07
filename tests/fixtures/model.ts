/**
 * A stand-in for Anthropic's Messages API that Claude Code and OpenCode call instead of a model, so the smoke tests run
 * both hosts without an API key. It keeps each Messages API request it answers and answers it with a streamed reply the
 * real API sent, recorded once in tests/fixtures/messages as `<name>.reply`, in a folder named for the host where only
 * one host sends it: the host's summary when it asks for one, the host's skill tool call when a request that offers a
 * skill tool asks it to load nus-mode, OpenCode's for sample-mode when one asks for that, `full.reply` to the prompt
 * that fills the context window, and OK, `text.reply`, to anything else. It finds a session's turn by a prompt as the
 * last request that offers a skill tool and holds that prompt in its last user message's last block, since OpenCode's
 * title request quotes a session's first prompt, offers no skill tool and races that turn's request
 * (https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/session/runner/llm.ts#L58-L59). Each
 * `<name>.request.json` beside its `<name>.reply` drew that reply; OpenCode's `title.request.json` draws `text.reply`,
 * as does Claude Code's `skill-result.request.json`, whose last user message, a skill load's result, holds no load
 * prompt. Claude Code's /api/hello check draws the real API's reply too. It refuses a body that is not JSON, a request
 * with no user message, as the real API does, a last user message whose content is neither text nor a list whose last
 * item is an object, any other field it reads whose shape does not fit, and a path it does not serve. Each refusal
 * names what is wrong in the Messages API's error body, so a host stops instead of retrying.
 */
import { readFileSync } from "node:fs"
import { join } from "node:path"

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

/** The host whose skill tool and summary request the fake answers. */
export type Host = "claude-code" | "opencode"

/** A request the fake refuses. */
class RequestError extends Error {
  override name = "RequestError"
}

/**
 * A turn a test looks for by its prompt that the fake never answered: no request that offers a skill tool held that
 * prompt in its last user message's last block.
 */
export class TurnNotFoundError extends Error {
  override name = "TurnNotFoundError"
}

/**
 * A local Messages API server that answers the hosts' requests and keeps each Messages API request for the tests to
 * read.
 */
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
  static readonly MESSAGES = join(import.meta.dirname, "messages")
  // Only OpenCode's smoke tests load sample-mode, so only OpenCode has a recorded reply that loads it.
  private static readonly LOADS = Object.freeze({
    "claude-code": Object.freeze({ [FakeModel.LOAD]: "skill" }),
    opencode: Object.freeze({ [FakeModel.LOAD]: "skill", [FakeModel.LOAD_SAMPLE]: "sample-skill" }),
  })
  // Claude Code's summary request ends by asking for these two blocks; OpenCode's holds its summary template, as
  // tests/fixtures/messages/<host>/summary.request.json records.
  static readonly SUMMARY_ASKS = Object.freeze({
    "claude-code": "an <analysis> block followed by a <summary> block",
    opencode: "<template>",
  })
  private readonly host: Host
  private readonly requests: { readonly raw: string; readonly reading: Reading }[] = []
  private readonly server: Bun.Server<undefined>

  constructor(host: Host) {
    this.host = host
    this.server = Bun.serve({
      port: 0,
      fetch: (request) => this.answer(request),
      error: (error) => FakeModel.refusal(error),
    })
  }

  get url(): string {
    return this.server.url.href.replace(/\/$/, "")
  }

  // The Messages API's answer to a request it refuses: https://docs.anthropic.com/en/api/errors
  private static refusal(error: Error): Response {
    return Response.json(
      { type: "error", error: { type: "invalid_request_error", message: error.message } },
      { status: 400 },
    )
  }

  turnWith(prompt: string): string {
    const found = this.requests.findLast(
      ({ reading }) => reading.offersSkill && reading.lastBlock.includes(prompt),
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
    const path = new URL(request.url).pathname
    if (path === "/api/hello")
      return new Response(FakeModel.recorded("hello"), {
        headers: { "content-type": "application/json" },
      })
    if (path !== "/v1/messages")
      throw new RequestError(
        `the fake model serves only /v1/messages, not ${path}; send the request to /v1/messages`,
      )
    const raw = await request.text()
    const reading = FakeModel.parsed(raw)
    this.requests.push({ raw, reading })
    const load = Object.entries(FakeModel.LOADS[this.host]).find(([prompt]) =>
      reading.lastBlock.includes(prompt),
    )
    let reply = FakeModel.recorded("text")
    if (reading.lastBlock.includes(FakeModel.SUMMARY_ASKS[this.host]))
      reply = FakeModel.recorded(`${this.host}/summary`)
    else if (reading.offersSkill && load !== undefined)
      reply = FakeModel.recorded(`${this.host}/${load[1]}`)
    // full.reply is the real reply to "Reply OK. " followed by "OK " 99,496 times, 199,006 tokens, which makes a host
    // summarize on its own once its test holds it to WINDOW; that 300 KB request is not recorded.
    else if (reading.lastBlock.includes(FakeModel.FILL)) reply = FakeModel.recorded("full")
    return new Response(reply, { headers: { "content-type": "text/event-stream" } })
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
      if (!message.has("content")) {
        throw new RequestError(`${path}.content is missing; give the message its content`)
      }
      return { role, content: message.get("content") }
    })
    const last = messages.findLastIndex((each) => each.role === "user")
    if (last === -1)
      throw new RequestError(
        "the request holds no user message, which the Messages API requires; give it a user message",
      )
    const content = messages[last]?.content
    if (typeof content !== "string" && !Array.isArray(content))
      throw new RequestError(
        `messages[${last}].content must be text or a list, got ${kindOf(content)}; send it as a JSON string or array`,
      )
    if (Array.isArray(content)) {
      if (content.length === 0)
        throw new RequestError(
          `messages[${last}].content is an empty list; give the last user message at least one content block`,
        )
      objectAt(`messages[${last}].content[${content.length - 1}]`, content.at(-1))
    }
    const tools = request.has("tools")
      ? listAt("tools", request.get("tools")).map((each, index) =>
          textAt(`tools[${index}].name`, objectAt(`tools[${index}]`, each).get("name")),
        )
      : []
    return {
      lastBlock: JSON.stringify(typeof content === "string" ? content : content.at(-1)),
      offersSkill: tools.some((name) => name.toLowerCase() === "skill"),
    }
  }

  private static recorded(name: string): string {
    return readFileSync(join(FakeModel.MESSAGES, `${name}.reply`), "utf8")
  }
}

function objectAt(path: string, value: unknown): ReadonlyMap<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new RequestError(
      `${path} must be an object, got ${kindOf(value)}; send it as a JSON object`,
    )
  }
  return new Map(Object.entries(value))
}

function listAt(path: string, value: unknown): readonly unknown[] {
  if (!Array.isArray(value)) {
    throw new RequestError(`${path} must be a list, got ${kindOf(value)}; send it as a JSON array`)
  }
  return value
}

function textAt(path: string, value: unknown): string {
  if (typeof value !== "string") {
    throw new RequestError(`${path} must be text, got ${kindOf(value)}; send it as a JSON string`)
  }
  return value
}

function kindOf(value: unknown): string {
  if (value === undefined) return "nothing"
  if (value === null) return "null"
  if (Array.isArray(value)) return "a list"
  return typeof value === "object" ? "an object" : `a ${typeof value}`
}
