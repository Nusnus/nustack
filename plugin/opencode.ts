/**
 * The OpenCode plugin: it reads each skill folder's SKILL.md as scripts/check.ts reads it and registers the skill with
 * OpenCode as its frontmatter asks, and puts the mode's text and folder back in a session's context once a
 * summarization drops them. A skills folder it cannot read, or any skill folder or SKILL.md it cannot load, fails the
 * load with one error naming each and its fix; once every skill loads, a missing mode fails it.
 */
import { readdir, readFile } from "node:fs/promises"
import { dirname, join } from "node:path"
import type { Plugin, Skill } from "@opencode/plugin"
import type { SessionContext, SessionPrompt } from "@opencode/plugin/promise/session"
// OpenCode's opencode command runs the binary Bun compiles for the platform, so plugins run under Bun
// (https://github.com/anomalyco/opencode/blob/v2.2.5/packages/cli/bin/opencode.cjs#L36-L42;
// https://github.com/anomalyco/opencode/blob/v2.2.5/packages/cli/script/build.ts#L160-L185), and the loader parses
// frontmatter with Bun's YAML parser: https://bun.com/docs/runtime/yaml
import { YAML } from "bun"
import manifest from "./package.json" with { type: "json" }

/** A model request OpenCode lets a plugin read, and add system text to, before it goes out. */
export type ModelRequest = Pick<SessionContext, "sessionID" | "messages" | "system">

/** A prompt OpenCode lets a plugin read as it admits it into a session, with the skills its user invoked. */
export type UserPrompt = Pick<SessionPrompt, "sessionID" | "prompt">

/**
 * The part of OpenCode's session API the mode reload uses: hooks on the agent loop's requests and the summary requests.
 */
export type SessionHooks = Pick<Plugin.Context["session"], "hook">

/** The part of OpenCode's plugin storage the mode reload uses. */
export type Store = Pick<Plugin.Context["storage"], "get" | "set">

/** How far the mode reload has read one session's messages since its last summarization. */
class Progress {
  loaded: boolean
  // restart sets both, which tsc cannot see from the constructor:
  // https://www.typescriptlang.org/docs/handbook/2/classes.html#--strictpropertyinitialization
  scanned!: number
  present!: boolean

  constructor(loaded: boolean) {
    this.loaded = loaded
    this.restart()
  }

  restart(): void {
    this.scanned = 0
    this.present = false
  }
}

/**
 * The plugin's skills folder, a skill folder or a SKILL.md the loader cannot load, or a missing mode, named with its
 * fix; one error lists every skill that fails.
 */
export class SkillError extends Error {
  override name = "SkillError"

  static at(path: string, problem: string, options?: ErrorOptions): SkillError {
    return new SkillError(`${path} ${problem}, or reinstall the nustack plugin`, options)
  }
}

/** A SKILL.md's text, read into the skill OpenCode registers, or an error that names the fix. */
export class SkillFile {
  static readonly FRONTMATTER = /^---\r?\n([\s\S]*?)(?<=\n)---(?:\r?\n|$)/
  static readonly BARE_CR = /^---\r(?!\n)/
  static readonly OPENING = /^---(?:\r?\n|$)/
  // A SKILL.md is UTF-8, as scripts/check.ts requires, and ignoreBOM keeps a byte order mark in the text, so split refuses
  // it as scripts/check.ts does: https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/ignoreBOM
  static readonly UTF8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true })
  // Bun's YAML parser crashes the process, rather than throwing, on frontmatter nested 10813 levels deep as flow
  // collections, or 7858 as block mappings, whose levels each take a deeper indent, under a 64 MB stack on macOS. Each
  // level takes at least one character, so frontmatter this long reaches neither. Set when nustack's longest frontmatter
  // held 500 characters, the cap refuses longer frontmatter however shallow it nests.
  static readonly MOST_CHARACTERS = 4096
  // The bound scripts/check.ts holds JSON, YAML and TOML to, counted on the value the parser builds.
  static readonly MOST_LEVELS = 200
  // Unicode's White_Space characters and the zero-width ones, as BLANK in scripts/metadata.ts counts them for
  // scripts/check.ts: https://www.unicode.org/Public/UCD/latest/ucd/PropList.txt
  static readonly BLANK =
    /^[\t\n\v\f\r \x85\xa0\u1680\u2000-\u200d\u2028\u2029\u202f\u205f\u2060\u3000\ufeff]*$/
  readonly path: string
  readonly text: string

  constructor(path: string, text: string) {
    this.path = path
    this.text = text
    Object.freeze(this)
  }

  static decode(path: string, data: Uint8Array): SkillFile {
    try {
      return new SkillFile(path, SkillFile.UTF8.decode(data))
    } catch {
      throw SkillError.at(path, "is not valid UTF-8; save it as UTF-8")
    }
  }

  /**
   * Whether a parsed value nests more than MOST_LEVELS arrays and objects deep, the outermost included, walked with a
   * stack of its own as scripts/check.ts walks it through nestsTooDeep in scripts/tree.ts: a value an alias shares is
   * walked again only when reached deeper than before, so each value is walked at most MOST_LEVELS times and a cycle
   * counts as too deep.
   */
  static nestsTooDeep(value: unknown): boolean {
    const deepest = new Map<object, number>()
    const pending: [unknown, number][] = [[value, 1]]
    for (let next = pending.pop(); next !== undefined; next = pending.pop()) {
      const [item, level] = next
      if (typeof item !== "object" || item === null || (deepest.get(item) ?? 0) >= level) continue
      if (level > SkillFile.MOST_LEVELS) return true
      deepest.set(item, level)
      for (const child of Object.values(item)) pending.push([child, level + 1])
    }
    return false
  }

  info(id: string): Skill.Info {
    const [frontmatter, body] = this.split()
    return Object.freeze({
      id: id as Skill.ID,
      name: this.field(frontmatter, "name") as Skill.Name,
      description: this.field(frontmatter, "description"),
      autoinvoke: !this.hidden(frontmatter),
      path: this.path as Skill.Info["path"],
      content: body,
    })
  }

  split(): readonly [ReadonlyMap<string, unknown>, string] {
    if (this.text.startsWith("\ufeff")) {
      throw this.error("opens with a byte order mark; save it without one")
    }
    if (SkillFile.BARE_CR.test(this.text)) {
      throw this.error("has lines that end in a bare CR; save it with LF line endings")
    }
    const match = SkillFile.FRONTMATTER.exec(this.text)
    if (match?.[1] === undefined) {
      if (SkillFile.OPENING.test(this.text)) {
        throw this.error("opens with --- and never closes; end it with a --- line")
      }
      throw this.error(
        "has no frontmatter; open it with a line that holds only ---, and save it with no byte order mark and with LF or CRLF line endings",
      )
    }
    // scripts/check.ts reads an empty block as no fields, where Bun's YAML parser reads it as null; a block of blank
    // lines is not empty, and scripts/check.ts refuses its lines as no fields, as this does
    const fields = match[1] === "" ? {} : this.parse(match[1])
    if (typeof fields !== "object" || fields === null || Array.isArray(fields)) {
      throw this.error("has frontmatter that is not key: value lines; write it as key: value lines")
    }
    return Object.freeze([new Map(Object.entries(fields)), this.text.slice(match[0].length)])
  }

  parse(frontmatter: string): unknown {
    if (frontmatter.length > SkillFile.MOST_CHARACTERS) {
      throw this.error(
        `has frontmatter longer than ${SkillFile.MOST_CHARACTERS} characters; shorten it`,
      )
    }
    const tooDeep = `has frontmatter that nests values more than ${SkillFile.MOST_LEVELS} levels deep; flatten them`
    let value: unknown
    try {
      value = YAML.parse(frontmatter)
    } catch (error) {
      // Bun's parser throws a SyntaxError for text that is not YAML, and a RangeError once the frontmatter outruns the
      // stack, whose size depends on the host.
      if (
        error instanceof RangeError &&
        error.message.startsWith("Maximum call stack size exceeded")
      )
        throw this.error(tooDeep)
      if (!(error instanceof SyntaxError)) throw error
      throw this.error("has frontmatter that is not valid YAML; fix it")
    }
    if (SkillFile.nestsTooDeep(value)) throw this.error(tooDeep)
    return value
  }

  field(frontmatter: ReadonlyMap<string, unknown>, key: string): string {
    const value = frontmatter.get(key)
    if (value === undefined) {
      throw this.error(`has no ${key} in its frontmatter; add one`)
    }
    if (typeof value !== "string") {
      throw this.error(`has a ${key} that is not text; write its text`)
    }
    if (SkillFile.BLANK.test(value)) {
      throw this.error(`has a blank ${key}; fill it in`)
    }
    return value
  }

  hidden(frontmatter: ReadonlyMap<string, unknown>): boolean {
    const value = frontmatter.get("disable-model-invocation")
    if (value === undefined) {
      return false
    }
    if (typeof value !== "boolean") {
      throw this.error(
        "has a disable-model-invocation that is not true or false; set it to true or false",
      )
    }
    return value
  }

  error(problem: string): SkillError {
    return SkillError.at(this.path, problem)
  }
}

/** The plugin's skills folder, the one place the loader reads files. */
export class SkillFolder {
  readonly path: string

  constructor(path: string) {
    this.path = path
    Object.freeze(this)
  }

  async skills(): Promise<readonly Skill.Info[]> {
    const entries = await readdir(this.path, { withFileTypes: true }).catch((error: unknown) => {
      throw SkillError.at(
        this.path,
        `cannot be read (${errorCode(error)}); restore the plugin's skills folder`,
        { cause: error },
      )
    })
    const results = await Promise.allSettled(
      entries.flatMap((entry) => {
        if (entry.isSymbolicLink()) return [this.symlink(entry.name)]
        return entry.isDirectory() ? [this.skill(entry.name)] : []
      }),
    )
    const failures = results.flatMap((result) =>
      result.status === "rejected" ? [errorMessage(result.reason)] : [],
    )
    if (failures.length > 0) throw new SkillError(failures.sort().join("\n"))
    return Object.freeze(
      results.flatMap((result) => (result.status === "fulfilled" ? [result.value] : [])),
    )
  }

  async symlink(name: string): Promise<never> {
    throw SkillError.at(
      join(this.path, name),
      "is a symlink, which the loader does not follow; put the skill folder itself there",
    )
  }

  async skill(id: string): Promise<Skill.Info> {
    const path = this.file(id)
    const data = await readFile(path).catch((error: unknown) => {
      throw SkillError.at(
        path,
        `cannot be read (${errorCode(error)}); give the skill a readable SKILL.md`,
        { cause: error },
      )
    })
    return SkillFile.decode(path, data).info(id)
  }

  file(id: string): string {
    return join(this.path, id, "SKILL.md")
  }
}

/**
 * Puts the mode's text back in the system instructions of a session that loaded the mode, through the skill tool or its
 * user's invocation, once a summarization drops it from the session's messages. The mode's body anywhere in a message
 * puts the mode in the context, but only a skill call that names the mode loads it. Which sessions loaded the mode is
 * kept in storage, so it survives a restart.
 */
export class ModeReload {
  static readonly ID = "nus-mode"
  readonly skill: Skill.Info
  readonly store: Store
  readonly sessions = new Map<string, Progress>()
  readonly escapedBody: string
  readonly reloadText: string

  constructor(skill: Skill.Info, store: Store) {
    this.skill = skill
    this.store = store
    // OpenCode's skill tool shows the body trimmed, its CRLF lines kept, so the reload looks for and gives back that,
    // as tests/fixtures/opencode/loaded/context.json records.
    const body = this.skill.content.trim()
    this.escapedBody = JSON.stringify(body).slice(1, -1)
    // The mode's links are relative to its folder, so the folder follows its text, as OpenCode's skill tool gives it in
    // tests/fixtures/opencode/loaded/context.json.
    this.reloadText = `${body}\n\nBase directory for this skill: ${dirname(this.skill.path)}\nRelative paths in this skill are relative to this base directory.`
    Object.freeze(this)
  }

  static mode(folder: SkillFolder, skills: readonly Skill.Info[]): Skill.Info {
    const skill = skills.find((candidate) => candidate.id === ModeReload.ID)
    if (skill === undefined) {
      throw SkillError.at(folder.file(ModeReload.ID), "is missing; restore the mode")
    }
    return skill
  }

  register(session: SessionHooks): Promise<{ dispose: () => Promise<void> }[]> {
    return Promise.all([
      session.hook("prompt", (request) => this.prompting(request)),
      session.hook("compaction", (request) => this.summarizing(request)),
      session.hook("context", (request) => this.calling(request)),
    ])
  }

  // OpenCode records a user's invocation only in the prompt's skills, which prompt text cannot add to, as
  // tests/fixtures/opencode/invoked/prompt.json and forged/prompt.json record.
  async prompting(request: UserPrompt): Promise<void> {
    if (!request.prompt.skills?.some((skill) => skill.id === this.skill.id)) return
    await this.remember(request.sessionID, await this.progress(request.sessionID))
  }

  async summarizing(request: ModelRequest): Promise<void> {
    const progress = await this.progress(request.sessionID)
    if (!progress.loaded && this.loads(request.messages))
      await this.remember(request.sessionID, progress)
    progress.restart()
  }

  async calling(request: ModelRequest): Promise<void> {
    const progress = await this.progress(request.sessionID)
    if (request.messages.length < progress.scanned) progress.restart()
    const fresh = request.messages.slice(progress.scanned)
    if (fresh.some((message) => JSON.stringify(message).includes(this.escapedBody))) {
      progress.present = true
      if (!progress.loaded && this.loads(fresh)) await this.remember(request.sessionID, progress)
    }
    progress.scanned = request.messages.length
    if (progress.loaded && !progress.present) {
      request.system.push({ type: "text", text: this.reloadText })
    }
  }

  async progress(sessionID: string): Promise<Progress> {
    const known = this.sessions.get(sessionID)
    if (known !== undefined) return known
    const progress = new Progress((await this.store.get(this.key(sessionID))) === true)
    this.sessions.set(sessionID, progress)
    return progress
  }

  async remember(sessionID: string, progress: Progress): Promise<void> {
    await this.store.set(this.key(sessionID), true)
    progress.loaded = true
  }

  // A load is the skill tool's result for a call that names the mode, as tests/fixtures/opencode/loaded/context.json
  // records; a prompt or another skill's result can hold the mode's body, as forged/ and quoted/ there record.
  loads(messages: ModelRequest["messages"]): boolean {
    const parts = messages.flatMap((message) => message.content)
    const calls = new Set(
      parts.flatMap((part) =>
        part.type === "tool-call" &&
        part.name === "skill" &&
        Object(part.input).id === this.skill.id
          ? [part.id]
          : [],
      ),
    )
    return parts.some(
      (part) =>
        part.type === "tool-result" &&
        calls.has(part.id) &&
        JSON.stringify(part.result).includes(this.escapedBody),
    )
  }

  key(sessionID: string): string {
    return `${this.skill.id}/loaded/${sessionID}`
  }
}

export default {
  id: manifest.name,
  async setup(context: {
    skill: Pick<Plugin.Context["skill"], "transform">
    session: SessionHooks
    storage: Store
  }): Promise<() => Promise<void>> {
    const folder = new SkillFolder(join(import.meta.dirname, "skills"))
    const skills = await folder.skills()
    const reload = new ModeReload(ModeReload.mode(folder, skills), context.storage)
    const registrations = [
      await context.skill.transform((editor) => {
        for (const skill of skills) editor.add(skill)
      }),
      ...(await reload.register(context.session)),
    ]
    return async () => {
      await Promise.all(registrations.map((registration) => registration.dispose()))
    }
  },
} satisfies Plugin.Plugin

export function errorCode(error: unknown): string {
  return error instanceof Error && "code" in error && typeof error.code === "string"
    ? error.code
    : "no error code"
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
