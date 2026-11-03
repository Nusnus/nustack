/**
 * A stand-in for Anthropic's Messages API that Claude Code and OpenCode call instead of a model, so the smoke tests run
 * both hosts without an API key. It keeps each request it answers and answers it with a streamed reply the real API
 * sent, recorded once in tests/fixtures/messages as `<name>.reply` beside the `<name>.request.json` that drew it, in a
 * folder named for the host where only one host sends it: the host's skill tool call when a prompt asks it to load
 * nus-mode, or OpenCode's for sample-mode when one asks for that, the host's summary when it asks for one, and OK to
 * anything else. Claude Code's /api/hello check draws the real API's reply too. It refuses a request with no user
 * message, as the real API does, and a path it does not serve, with the Messages API's error body, so a host stops
 * instead of retrying.
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

/** A local Messages API server that answers each host request and keeps it for the tests to read. */
export class FakeModel {
  static readonly LOAD = "Load nus-mode with the skill tool."
  static readonly LOAD_SAMPLE = "Load sample-mode with the skill tool."
  static readonly AFTER = "Reply OK after the summary."
  static readonly UNLOADED = "Reply OK without loading a skill."
  static readonly PROOFREAD = "Proofread this text; reply OK."
  static readonly PATIENCE = 120_000
  static readonly FILL = "This prompt fills the context window."
  static readonly WINDOW = 200_000
  static readonly MESSAGES = join(import.meta.dirname, "messages")
  static readonly LOADS = { [FakeModel.LOAD]: "skill", [FakeModel.LOAD_SAMPLE]: "sample-skill" }
  // Claude Code's summary request ends by asking for these two blocks; OpenCode's holds its summary template, as
  // tests/fixtures/messages/<host>/summary.request.json records.
  static readonly SUMMARIES = {
    "claude-code": "an <analysis> block followed by a <summary> block",
    opencode: "<template>",
  }
  readonly host: Host
  readonly requests: string[] = []
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
    const found = this.requests.findLast((raw) =>
      FakeModel.prompt(JSON.parse(raw)).includes(wanted),
    )
    if (found === undefined) throw new Error(`no request held the prompt ${JSON.stringify(wanted)}`)
    return found
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
      throw new Error(`the fake model serves only /v1/messages, not ${path}`)
    const raw = await request.text()
    const sent: Sent = JSON.parse(raw)
    const asked = FakeModel.prompt(sent)
    this.requests.push(raw)
    const skill = sent.tools?.some((tool) => tool.name.toLowerCase() === "skill") ?? false
    const load = Object.entries(FakeModel.LOADS).find(([prompt]) => asked.includes(prompt))
    let reply = FakeModel.recorded("text")
    if (asked.includes(FakeModel.SUMMARIES[this.host]))
      reply = FakeModel.recorded(`${this.host}/summary`)
    else if (skill && load !== undefined && !asked.includes("tool_result"))
      reply = FakeModel.recorded(`${this.host}/${load[1]}`)
    // full.reply is the real reply to "Reply OK. " followed by "OK " 99,496 times, 199,006 tokens, which makes a host
    // summarize on its own; that 300 KB request is not kept.
    else if (asked.includes(FakeModel.FILL)) reply = FakeModel.recorded("full")
    return new Response(reply, { headers: { "content-type": "text/event-stream" } })
  }

  static recorded(name: string): string {
    return readFileSync(join(FakeModel.MESSAGES, `${name}.reply`), "utf8")
  }

  static prompt(sent: Sent): string {
    const message = sent.messages.findLast((each) => each.role === "user")
    if (message === undefined)
      throw new Error("the request holds no user message, which the Messages API requires")
    return JSON.stringify(message.content).replaceAll("\\n", "\n")
  }
}
