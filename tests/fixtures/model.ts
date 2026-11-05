/**
 * A stand-in for Anthropic's Messages API that Claude Code and OpenCode call instead of a model, so the smoke tests run
 * both hosts without an API key. It keeps each Messages API request it answers and answers it with a streamed reply the
 * real API sent, recorded once in tests/fixtures/messages as `<name>.reply`, in a folder named for the host where only
 * one host sends it: the host's summary when it asks for one, the host's skill tool call when a request that offers a
 * skill tool asks it to load nus-mode, OpenCode's for sample-mode when one asks for that, `full.reply` to the prompt
 * that fills the context window, and OK, `text.reply`, to anything else. Each `<name>.request.json` beside its
 * `<name>.reply` drew that reply; OpenCode's `title.request.json` quotes the load prompt but offers no skill tool, so
 * it draws `text.reply`, as does Claude Code's `skill-result.request.json`, whose last user message, a skill load's
 * result, holds no load prompt. Claude Code's /api/hello check draws the real API's reply too. It refuses a request
 * with no user message, as the real API does, a body that is not a Messages API request, naming the field that does not
 * fit, and a path it does not serve, with the Messages API's error body, so a host stops instead of retrying.
 */
import { readFileSync } from "node:fs"
import { join } from "node:path"

/** One request a host sent, as JSON. */
export interface Sent {
  readonly messages: readonly { readonly role: string; readonly content: unknown }[]
  readonly tools?: readonly { readonly name: string }[]
}

/** The host whose skill tool and summary request the fake answers. */
export type Host = "claude-code" | "opencode"

/** A request the fake refuses. */
export class RequestError extends Error {
  override name = "RequestError"
}

/** A prompt a test looks for that no request the fake answered held. */
export class PromptNotSentError extends Error {
  override name = "PromptNotSentError"
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
  static readonly LOADS = Object.freeze({
    "claude-code": Object.freeze({ [FakeModel.LOAD]: "skill" }),
    opencode: Object.freeze({ [FakeModel.LOAD]: "skill", [FakeModel.LOAD_SAMPLE]: "sample-skill" }),
  })
  // Claude Code's summary request ends by asking for these two blocks; OpenCode's holds its summary template, as
  // tests/fixtures/messages/<host>/summary.request.json records.
  static readonly SUMMARIES = Object.freeze({
    "claude-code": "an <analysis> block followed by a <summary> block",
    opencode: "<template>",
  })
  readonly host: Host
  readonly requests: { readonly raw: string; readonly sent: Sent }[] = []
  readonly server: Bun.Server<undefined>

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
  static refusal(error: Error): Response {
    return Response.json(
      { type: "error", error: { type: "invalid_request_error", message: error.message } },
      { status: 400 },
    )
  }

  sentWith(wanted: string): string {
    const found = this.requests.findLast(({ sent }) => FakeModel.prompt(sent).includes(wanted))
    if (found === undefined)
      throw new PromptNotSentError(`no request held the prompt ${JSON.stringify(wanted)}`)
    return found.raw
  }

  async stop(): Promise<void> {
    await this.server.stop(true)
  }

  async answer(request: Request): Promise<Response> {
    const path = new URL(request.url).pathname
    if (path === "/api/hello")
      return new Response(FakeModel.recorded("hello"), {
        headers: { "content-type": "application/json" },
      })
    if (path !== "/v1/messages")
      throw new RequestError(`the fake model serves only /v1/messages, not ${path}`)
    const raw = await request.text()
    const sent = FakeModel.parsed(JSON.parse(raw))
    const asked = FakeModel.prompt(sent)
    this.requests.push({ raw, sent })
    const skill = sent.tools?.some((tool) => tool.name.toLowerCase() === "skill") ?? false
    const load = Object.entries(FakeModel.LOADS[this.host]).find(([prompt]) =>
      asked.includes(prompt),
    )
    let reply = FakeModel.recorded("text")
    if (asked.includes(FakeModel.SUMMARIES[this.host]))
      reply = FakeModel.recorded(`${this.host}/summary`)
    else if (skill && load !== undefined) reply = FakeModel.recorded(`${this.host}/${load[1]}`)
    // full.reply is the real reply to "Reply OK. " followed by "OK " 99,496 times, 199,006 tokens, which makes a host
    // summarize on its own; that 300 KB request is not recorded.
    else if (asked.includes(FakeModel.FILL)) reply = FakeModel.recorded("full")
    return new Response(reply, { headers: { "content-type": "text/event-stream" } })
  }

  // Reads the fields the fake uses from a body a host sent: https://docs.anthropic.com/en/api/messages
  static parsed(body: unknown): Sent {
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
    if (!request.has("tools")) return { messages }
    const tools = listAt("tools", request.get("tools")).map((each, index) => ({
      name: textAt(`tools[${index}].name`, objectAt(`tools[${index}]`, each).get("name")),
    }))
    return { messages, tools }
  }

  static recorded(name: string): string {
    return readFileSync(join(FakeModel.MESSAGES, `${name}.reply`), "utf8")
  }

  static prompt(sent: Sent): string {
    const message = sent.messages.findLast((each) => each.role === "user")
    if (message === undefined)
      throw new RequestError("the request holds no user message, which the Messages API requires")
    return JSON.stringify(message.content)
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
