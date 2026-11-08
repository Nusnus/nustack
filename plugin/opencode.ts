/**
 * The OpenCode plugin: it registers each skill folder's SKILL.md as its frontmatter asks, failing with one error that
 * names each folder or file it cannot load and the fix, or the missing mode, and puts the mode back after a summary.
 */
import { readdir, readFile } from "node:fs/promises"
import { dirname, join } from "node:path"
import type { Plugin, Skill } from "@opencode/plugin"
// OpenCode's opencode command runs the binary Bun compiles for the platform, so plugins run under Bun
// (https://github.com/anomalyco/opencode/blob/v2.2.5/packages/cli/bin/opencode.cjs#L36-L42;
// https://github.com/anomalyco/opencode/blob/v2.2.5/packages/cli/script/build.ts#L160-L185), and the loader parses
// frontmatter with Bun's YAML parser: https://bun.com/docs/runtime/yaml
import { YAML } from "bun"

/** The parts of OpenCode's plugin context the loader uses. */
export type Context = {
  skill: Pick<Plugin.Context["skill"], "transform">
  session: Pick<Plugin.Context["session"], "hook">
  tool: Pick<Plugin.Context["tool"], "hook">
  storage: Pick<Plugin.Context["storage"], "get" | "set">
}

/** A hook's registration, which disposes the hook. */
type Registration = Awaited<ReturnType<Context["session"]["hook"]>>

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

/** A value in the plugin's storage that the reload never stores, which it refuses rather than guess its meaning. */
export class StorageError extends Error {
  override name = "StorageError"
}

/** A SKILL.md's text, read into the skill OpenCode registers, or an error that names the fix. */
export class SkillFile {
  static readonly FRONTMATTER = /^---\r?\n([\s\S]*?)(?<=\n)---(?:\r?\n|$)/
  static readonly BARE_CR = /^---\r(?!\n)/
  static readonly OPENING = /^---(?:\r?\n|$)/
  // A SKILL.md is UTF-8, and ignoreBOM keeps a byte order mark in the text, for split to refuse:
  // https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/ignoreBOM
  static readonly UTF8 = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true })
  // Bun's YAML parser crashes the process, rather than throwing, on frontmatter nested 10813 levels deep as flow
  // collections, or 7858 as block mappings, whose levels each take a deeper indent, under a 64 MB stack on macOS. Each
  // level takes at least one character, so frontmatter this long reaches neither. Set when nustack's longest frontmatter
  // held 500 characters, the cap refuses longer frontmatter however shallow it nests.
  static readonly MOST_CHARACTERS = 4096
  // The deepest the loader parses frontmatter, counted on the value the parser builds.
  static readonly MOST_LEVELS = 200
  // Unicode's White_Space characters and the zero-width ones, which the loader and the check take as blank:
  // https://www.unicode.org/Public/UCD/latest/ucd/PropList.txt
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
   * stack of its own, so a deep value fails with an error rather than overflowing the stack: a value an alias shares is
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
    if (this.text.startsWith("\ufeff"))
      throw this.error("opens with a byte order mark; save it without one")
    if (SkillFile.BARE_CR.test(this.text))
      throw this.error("has lines that end in a bare CR; save it with LF line endings")
    const match = SkillFile.FRONTMATTER.exec(this.text)
    if (match?.[1] === undefined) {
      if (SkillFile.OPENING.test(this.text))
        throw this.error("opens with --- and never closes; end it with a --- line")
      throw this.error(
        "has no frontmatter; open it with a line that holds only ---, and save it with no byte order mark and with LF or CRLF line endings",
      )
    }
    // An empty block holds no fields, which Bun's YAML parser reads as null; it reads a block of blank lines as null
    // too, and split refuses that block, which is not empty, as lines that are not key: value lines
    const fields = match[1] === "" ? {} : this.parse(match[1])
    if (typeof fields !== "object" || fields === null || Array.isArray(fields))
      throw this.error("has frontmatter that is not key: value lines; write it as key: value lines")
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
    if (value === undefined) throw this.error(`has no ${key} in its frontmatter; add one`)
    if (typeof value !== "string") throw this.error(`has a ${key} that is not text; write its text`)
    if (SkillFile.BLANK.test(value)) throw this.error(`has a blank ${key}; fill it in`)
    return value
  }

  hidden(frontmatter: ReadonlyMap<string, unknown>): boolean {
    const value = frontmatter.get("disable-model-invocation")
    if (value === undefined) return false
    if (typeof value !== "boolean")
      throw this.error(
        "has a disable-model-invocation that is not true or false; set it to true or false",
      )
    return value
  }

  error(problem: string): SkillError {
    return SkillError.at(this.path, problem)
  }
}

/**
 * A skills folder's entry, as SkillFolder.read finds it: a folder with its SKILL.md's bytes or the error reading them,
 * a symlink, or a file.
 */
export type SkillEntry = Readonly<
  | { name: string; kind: "file" }
  | { name: string; kind: "symlink" }
  | { name: string; kind: "folder"; data: Uint8Array }
  | { name: string; kind: "folder"; error: unknown }
>

/**
 * The plugin's skills folder: read takes its entries from disk, the one place the loader reads files, and skills turns
 * them into skills.
 */
export class SkillFolder {
  private static readonly SYMLINK =
    "is a symlink, which the loader does not follow; put the skill folder itself there"
  readonly path: string

  constructor(path: string) {
    this.path = path
    Object.freeze(this)
  }

  async read(): Promise<readonly SkillEntry[]> {
    const entries = await readdir(this.path, { withFileTypes: true }).catch((error: unknown) => {
      throw SkillError.at(
        this.path,
        `cannot be read (${errorCode(error)}); restore the plugin's skills folder`,
        { cause: error },
      )
    })
    return Promise.all(
      entries.map(async (entry): Promise<SkillEntry> => {
        const { name } = entry
        if (entry.isSymbolicLink()) return { name, kind: "symlink" }
        if (!entry.isDirectory()) return { name, kind: "file" }
        return readFile(this.file(name)).then(
          (data): SkillEntry => ({ name, kind: "folder", data }),
          (error: unknown): SkillEntry => ({ name, kind: "folder", error }),
        )
      }),
    )
  }

  skills(entries: readonly SkillEntry[]): readonly Skill.Info[] {
    const skills: Skill.Info[] = []
    const failures: SkillError[] = []
    for (const entry of entries) {
      try {
        const skill = this.skill(entry)
        if (skill !== undefined) skills.push(skill)
      } catch (error) {
        // Any other error is a bug in the loader, so it goes on whole, with its stack.
        if (!(error instanceof SkillError)) throw error
        failures.push(error)
      }
    }
    if (failures.length > 0) {
      failures.sort((a, b) => (a.message < b.message ? -1 : 1))
      throw new SkillError(failures.map((failure) => failure.message).join("\n"), {
        cause: failures,
      })
    }
    return Object.freeze(skills)
  }

  private skill(entry: SkillEntry): Skill.Info | undefined {
    if (entry.kind === "file") return undefined
    if (entry.kind === "symlink")
      throw SkillError.at(join(this.path, entry.name), SkillFolder.SYMLINK)
    const path = this.file(entry.name)
    if ("error" in entry)
      throw SkillError.at(
        path,
        `cannot be read (${errorCode(entry.error)}); give the skill a readable SKILL.md`,
        { cause: entry.error },
      )
    return SkillFile.decode(path, entry.data).info(entry.name)
  }

  file(id: string): string {
    return join(this.path, id, "SKILL.md")
  }
}

/**
 * Puts the mode's text and folder back in each agent request of a session that loaded the mode whose messages lack
 * the mode's whole text, as after a summary, keeping each session's state in storage.
 * Each OpenCode call cites its section of server.mdx:
 * https://github.com/anomalyco/opencode/blob/v2.2.5/services/www/src/docs/content/build/plugins/server.mdx
 */
export class ModeReload {
  private static readonly ID = "nus-mode"
  private static readonly STATES = Object.freeze(["selected", "loaded"] as const)
  private readonly storage: Context["storage"]
  private readonly escapedBody: string
  readonly reloadText: string

  constructor(skill: Skill.Info, storage: Context["storage"]) {
    this.storage = storage
    // The skill tool sends the body without frontmatter and the skill's base directory, as OpenCode's skills page says
    // under Loading: https://github.com/anomalyco/opencode/blob/v2.2.5/services/www/src/docs/content/skills.mdx, in
    // these words: https://github.com/anomalyco/opencode/blob/v2.2.5/packages/core/src/skill.ts#L42-L45
    const body = skill.content.trim()
    this.escapedBody = JSON.stringify(body).slice(1, -1)
    this.reloadText = `${body}\n\nBase directory for this skill: ${dirname(skill.path)}\nRelative paths in this skill (e.g., scripts/, reference/) are relative to this base directory.`
    Object.freeze(this)
  }

  static mode(folder: SkillFolder, skills: readonly Skill.Info[]): Skill.Info {
    const skill = skills.find((candidate) => candidate.id === ModeReload.ID)
    if (skill === undefined)
      throw SkillError.at(folder.file(ModeReload.ID), "is missing; restore the mode")
    return skill
  }

  register({ session, tool }: Pick<Context, "session" | "tool">): Promise<Registration[]> {
    return Promise.all([
      // Hooks › Sessions › Prompt admission: the prompt holds the skills its user selected, each skill's id typed
      // by the package. It runs before OpenCode admits the prompt, and a request can run before the selected skill's
      // text reaches its messages, so selecting the mode marks it selected: the first request or summary request
      // whose messages hold the mode's whole text counts it as a load. A selection no messages show, as when a rule
      // denies the mode or OpenCode drops the prompt, stays selected and adds nothing.
      // It settles a selection by the messages, not by asking whether a rule denies the mode: server.mdx documents no
      // read of a skill's permission, only permission.assert, which prompts the user on ask, and says prompt hooks are
      // not an exactly-once side-effect boundary, so a hook may run more than once and ask more than once.
      // A prompt holds only its skills' ids, so this hook knows the mode by its id alone.
      // A failed read or write of the storage rejects, and Prompt admission says that OpenCode then does not admit
      // the prompt.
      session.hook("prompt", async ({ sessionID, prompt }) => {
        if (!prompt.skills?.some((skill) => skill.id === ModeReload.ID)) return
        const state = await this.state(sessionID)
        switch (state) {
          case undefined:
            return this.set(sessionID, "selected")
          case "selected":
          case "loaded":
            return
          default:
            return state satisfies never
        }
      }),
      // Hooks › Tools: execute.after's example reads the call's status and result. A load counts only when its result
      // holds the shipped body, so a nus-mode from another skills folder counts as none. A departure from the page,
      // which lists no other field of ToolExecuteCompleted: only the call's tool, input and sessionID tell which
      // session loaded which skill. The published @opencode/plugin types declare tool and sessionID and leave input
      // unknown; the skill tool's input is {"id": ...}, as OpenCode's skills page says under Loading:
      // https://github.com/anomalyco/opencode/blob/v2.2.5/services/www/src/docs/content/skills.mdx
      // Permissions' evaluate hook lists its own fields, but runs before a skill loads, and for ask too, so it cannot
      // tell that the load happened. A failed write rejects, so OpenCode fails the skill tool's call with the storage's
      // error.
      tool.hook("execute.after", async (event) => {
        if (event.tool !== "skill" || Object(event.input).id !== ModeReload.ID) return
        if (event.status === "completed" && JSON.stringify(event.result).includes(this.escapedBody))
          await this.set(event.sessionID, "loaded")
      }),
      // Hooks › Sessions › Model requests: compaction runs for checkpoint summaries, with the messages the summary is
      // written from, so a selection still unsettled counts as a load if those messages hold the mode's whole text.
      session.hook("compaction", async ({ sessionID, messages }) => {
        const state = await this.state(sessionID)
        switch (state) {
          case undefined:
          case "loaded":
            return
          case "selected":
            if (this.shows(messages)) await this.set(sessionID, "loaded")
            return
          default:
            return state satisfies never
        }
      }),
      // Hooks › Sessions › Model requests: context runs for the agent loop, with the request's messages, and may add
      // system text. The page leaves unsaid which messages a summary, a summary written ahead and swapped in, or a
      // revert keeps, so each request of a session that loaded the mode, or selected it, looks for the mode's whole
      // text in its messages' JSON, reading no field of theirs, and adds the mode only where that text is missing, at
      // one stringify of the request's messages per request. It writes only a selection's load. The one write a race
      // can leave stale is a prompt's selection over a load the tool hook stored, and the next request settles it,
      // since its messages hold the tool's result.
      // A failed read or write of the storage rejects, and OpenCode's plugin adapter runs the hook as Effect.promise, so the
      // model request fails: https://github.com/anomalyco/opencode/blob/v2.2.5/packages/plugin/src/promise/adapter.ts#L625
      session.hook("context", async ({ sessionID, system, messages }) => {
        const state = await this.state(sessionID)
        switch (state) {
          case undefined:
            return
          case "selected":
            if (this.shows(messages)) await this.set(sessionID, "loaded")
            return
          case "loaded":
            if (this.shows(messages)) return
            break
          default:
            return state satisfies never
        }
        system.push({ type: "text", text: this.reloadText })
      }),
    ])
  }

  // API › Storage: set keeps a JSON value scoped to the plugin, which get reads back.
  private set(sessionID: string, state: (typeof ModeReload.STATES)[number]): Promise<void> {
    return this.storage.set(this.key(sessionID), state)
  }

  private shows(messages: readonly unknown[]): boolean {
    return JSON.stringify(messages).includes(this.escapedBody)
  }

  // API › Storage: get reads back what set kept, parsed here, where it enters, into the state set stores.
  private async state(sessionID: string): Promise<(typeof ModeReload.STATES)[number] | undefined> {
    const key = this.key(sessionID)
    const value = await this.storage.get(key)
    const state = ModeReload.STATES.find((each) => each === value)
    if (value !== undefined && state === undefined)
      throw new StorageError(
        `the plugin's storage holds ${JSON.stringify(value)} under ${key}, a value the loader never stores; continue in a new session, whose state starts empty`,
      )
    return state
  }

  // Each session that loads the mode keeps its key after it ends, as 0.0.2's keys do: a few bytes each, accepted.
  private key(sessionID: string): string {
    return `${ModeReload.ID}/${sessionID}`
  }
}

export default {
  // OpenCode knows the plugin by this id, which the loader's unit test holds to plugin/package.json's name, so
  // the plugin reads no file until it starts.
  id: "nustack",
  setup: (context: Context) => start(context, new SkillFolder(join(import.meta.dirname, "skills"))),
} satisfies Plugin.Plugin

export async function start(context: Context, folder: SkillFolder): Promise<() => Promise<void>> {
  const skills = folder.skills(await folder.read())
  const reload = new ModeReload(ModeReload.mode(folder, skills), context.storage)
  const registrations = [
    // server.mdx › API › Skills: a transform adds skills.
    await context.skill.transform((editor) => {
      for (const skill of skills) editor.add(skill)
    }),
    ...(await reload.register(context)),
  ]
  // server.mdx › Hooks: dispose each returned registration once it is no longer needed.
  return async () =>
    void (await Promise.all(registrations.map((registration) => registration.dispose())))
}

function errorCode(error: unknown): string {
  return error instanceof Error && "code" in error && typeof error.code === "string"
    ? error.code
    : "no error code"
}
