/**
 * The OpenCode plugin: registers each folder under skills/ by its SKILL.md frontmatter, and puts nus-mode's text back
 * in each request of a session that loaded it once a summary drops it, since agents often skip reloading it themselves.
 */
import { readdir } from "node:fs/promises"
import { dirname, join } from "node:path"
import type { Plugin, Skill } from "@opencode/plugin"
import { YAML } from "bun"

const SKILLS = join(import.meta.dirname, "skills")
const MODE = "nus-mode"
const UTF8 = new TextDecoder("utf-8", { fatal: true })
const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/

/** An install the plugin cannot load, with the advice that recovers every one. */
class BrokenInstall extends Error {
  constructor(problem: string) {
    super(`${problem}; reinstall the nustack plugin`)
  }
}

export default {
  id: "nustack",
  async setup(context) {
    const folders = await readdir(SKILLS, { withFileTypes: true }).catch((error) => {
      throw new BrokenInstall(`${SKILLS} is unreadable (${error})`)
    })
    const skills = await Promise.all(
      folders
        .filter((entry) => entry.isDirectory() || entry.isSymbolicLink())
        .map((entry) => {
          if (entry.isSymbolicLink())
            throw new BrokenInstall(
              `${join(SKILLS, entry.name)} is a symlink, which some hosts skip`,
            )
          return load(entry.name)
        }),
    )
    const mode = skills.find((skill) => skill.id === MODE)
    if (mode === undefined) throw new BrokenInstall(`${join(SKILLS, MODE, "SKILL.md")} is missing`)
    const body = mode.content.trim()
    const escaped = JSON.stringify(body).slice(1, -1)
    const reload = `${body}\n\nBase directory for this skill: ${dirname(mode.path)}`
    const key = (sessionID: string) => `${MODE}/${sessionID}`
    const registrations = await Promise.all([
      context.skill.transform((editor) => {
        for (const skill of skills) editor.add(skill)
      }),
      context.session.hook("prompt", async ({ sessionID, prompt }) => {
        if (prompt.skills?.some((skill) => skill.id === MODE))
          await context.storage.set(key(sessionID), true)
      }),
      context.tool.hook("execute.after", async (event) => {
        if (
          event.tool === "skill" &&
          event.status === "completed" &&
          Object(event.input).id === MODE
        )
          await context.storage.set(key(event.sessionID), true)
      }),
      context.session.hook("context", async ({ sessionID, system, messages }) => {
        if ((await context.storage.get(key(sessionID))) !== true) return
        if (!JSON.stringify(messages).includes(escaped)) system.push({ type: "text", text: reload })
      }),
    ])
    return async () => void (await Promise.all(registrations.map((each) => each.dispose())))
  },
} satisfies Plugin.Plugin

async function load(id: string): Promise<Skill.Info> {
  const path = join(SKILLS, id, "SKILL.md")
  const bytes = await Bun.file(path)
    .bytes()
    .catch((error) => {
      throw new BrokenInstall(
        error?.code === "ENOENT" ? `${path} is missing` : `${path} cannot be read (${error})`,
      )
    })
  let text: string
  try {
    text = UTF8.decode(bytes)
  } catch {
    throw new BrokenInstall(`${path} is not UTF-8`)
  }
  const match = FRONTMATTER.exec(text)
  if (match?.[1] === undefined) throw new BrokenInstall(`${path} has no frontmatter`)
  let fields: Record<string, unknown>
  try {
    fields = Object(YAML.parse(match[1]))
  } catch (error) {
    throw new BrokenInstall(`${path} holds frontmatter that is not YAML (${error})`)
  }
  if (typeof fields.name !== "string" || typeof fields.description !== "string")
    throw new BrokenInstall(`${path} names no skill or description`)
  return {
    id: id as Skill.ID,
    name: fields.name as Skill.Name,
    description: fields.description,
    autoinvoke: fields["disable-model-invocation"] !== true,
    path: path as Skill.Info["path"],
    content: text.slice(match[0].length),
  }
}
