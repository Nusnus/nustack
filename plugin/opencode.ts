/**
 * The OpenCode plugin: it reads each skill folder's SKILL.md as nustack check reads it and registers the skill with
 * OpenCode as its frontmatter asks, and puts the mode's text and folder back in a session's context once a
 * summarization drops them. A skills folder it cannot read, or any skill folder or SKILL.md it cannot load, fails the
 * load with one error naming each and its fix; once every skill loads, a missing mode fails it.
 */
import { readdir, readFile } from "node:fs/promises"
import { dirname, join } from "node:path"
import type { Plugin, Skill } from "@opencode/plugin"
import type { SessionContext, SessionPrompt } from "@opencode/plugin/promise/session"
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
interface Progress {
  loaded: boolean
  scanned: number
  present: boolean
}

/** A SKILL.md's text, read into the skill OpenCode registers, or an error that names the fix. */
export class SkillFile {
  static readonly FRONTMATTER = /^---\r?\n([\s\S]*?\r?\n)---(?:\r?\n|$)/
  static readonly BARE_CR = /^---\r(?!\n)/
  // A SKILL.md is UTF-8, as nustack check requires, and ignoreBOM keeps a byte order mark in the text, so split refuses
  // it as nustack check does: https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/ignoreBOM
  static readonly UTF8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true })
  // Unicode's White_Space characters and the zero-width ones, as nustack check's
  // Pattern.NON_BLANK counts them: https://www.unicode.org/Public/UCD/latest/ucd/PropList.txt
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
      throw new Error(
        `${path} is not valid UTF-8; save it as UTF-8, or reinstall the nustack plugin`,
      )
    }
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
      throw this.error("has no frontmatter; open it with a --- block")
    }
    const fields = this.parse(match[1])
    if (typeof fields !== "object" || fields === null || Array.isArray(fields)) {
      throw this.error("has frontmatter that is not key: value lines; write it as key: value lines")
    }
    return Object.freeze([new Map(Object.entries(fields)), this.text.slice(match[0].length)])
  }

  parse(header: string): unknown {
    try {
      return YAML.parse(header)
    } catch {
      throw this.error("has frontmatter that is not valid YAML; fix it")
    }
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

  error(what: string): Error {
    return new Error(`${this.path} ${what}, or reinstall the nustack plugin`)
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
      throw new Error(
        `${this.path} cannot be read (${SkillFolder.code(error)}); restore the plugin's skills folder, or reinstall the nustack plugin`,
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
      result.status === "rejected" ? [SkillFolder.reason(result.reason)] : [],
    )
    if (failures.length > 0) throw new Error(failures.sort().join("\n"))
    return Object.freeze(
      results.flatMap((result) => (result.status === "fulfilled" ? [result.value] : [])),
    )
  }

  async symlink(name: string): Promise<never> {
    throw new Error(
      `${join(this.path, name)} is a symlink, which the loader does not follow; put the skill folder itself there, or reinstall the nustack plugin`,
    )
  }

  async skill(id: string): Promise<Skill.Info> {
    const path = join(this.path, id, "SKILL.md")
    const data = await readFile(path).catch((error: unknown) => {
      throw new Error(
        `${path} cannot be read (${SkillFolder.code(error)}); give the skill a readable SKILL.md, or reinstall the nustack plugin`,
        { cause: error },
      )
    })
    return SkillFile.decode(path, data).info(id)
  }

  static code(error: unknown): string {
    return error instanceof Error && "code" in error && typeof error.code === "string"
      ? error.code
      : "no error code"
  }

  static reason(error: unknown): string {
    return error instanceof Error ? error.message : String(error)
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
  readonly needle: string
  readonly text: string
  readonly sessions = new Map<string, Progress>()

  constructor(skills: readonly Skill.Info[], store: Store) {
    this.skill = ModeReload.mode(skills)
    this.store = store
    // OpenCode's skill tool shows the body trimmed, its CRLF lines kept, so the reload looks for and gives back that,
    // as tests/fixtures/opencode/loaded/context.json records.
    const body = this.skill.content.trim()
    this.needle = JSON.stringify(body).slice(1, -1)
    // The mode's links are relative to its folder, so the folder follows its text, as OpenCode's skill tool gives it in
    // tests/fixtures/opencode/loaded/context.json.
    this.text = `${body}\n\nBase directory for this skill: ${dirname(this.skill.path)}\nRelative paths in this skill are relative to this base directory.`
    Object.freeze(this)
  }

  static mode(skills: readonly Skill.Info[]): Skill.Info {
    const skill = skills.find((candidate) => candidate.id === ModeReload.ID)
    if (skill === undefined) {
      throw new Error(
        `skills/${ModeReload.ID}/SKILL.md is missing; restore the mode, or reinstall the nustack plugin`,
      )
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
    progress.scanned = 0
    progress.present = false
  }

  async calling(request: ModelRequest): Promise<void> {
    const progress = await this.progress(request.sessionID)
    if (request.messages.length < progress.scanned) {
      progress.scanned = 0
      progress.present = false
    }
    const fresh = request.messages.slice(progress.scanned)
    if (fresh.some((message) => JSON.stringify(message).includes(this.needle))) {
      progress.present = true
      if (!progress.loaded && this.loads(fresh)) await this.remember(request.sessionID, progress)
    }
    progress.scanned = request.messages.length
    if (progress.loaded && !progress.present) {
      request.system.push({ type: "text", text: this.text })
    }
  }

  async progress(sessionID: string): Promise<Progress> {
    const known = this.sessions.get(sessionID)
    if (known !== undefined) return known
    const loaded = (await this.store.get(this.key(sessionID))) === true
    const progress = { loaded, scanned: 0, present: false }
    this.sessions.set(sessionID, progress)
    return progress
  }

  async remember(sessionID: string, progress: Progress): Promise<void> {
    progress.loaded = true
    await this.store.set(this.key(sessionID), true)
  }

  // A load is the skill tool's result for a call that names the mode, as tests/fixtures/opencode/loaded/context.json
  // records; a prompt or another skill's result can hold the mode's body, as forged/ and quoted/ there record.
  loads(messages: readonly unknown[]): boolean {
    const parts = messages.flatMap((message): unknown[] => {
      const content: unknown = Object(message).content
      return Array.isArray(content) ? content : []
    })
    const calls = new Set(
      parts
        .filter(
          (part) =>
            Object(part).type === "tool-call" &&
            Object(part).name === "skill" &&
            Object(Object(part).input).id === this.skill.id,
        )
        .map((part) => Object(part).id),
    )
    return parts.some(
      (part) =>
        Object(part).type === "tool-result" &&
        calls.has(Object(part).id) &&
        JSON.stringify(Object(part).result).includes(this.needle),
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
    const skills = await new SkillFolder(join(import.meta.dirname, "skills")).skills()
    const reload = new ModeReload(skills, context.storage)
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
