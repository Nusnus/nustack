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
const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/

export default {
  id: "nustack",
  async setup(context) {
    const folders = await readdir(SKILLS, { withFileTypes: true })
    const skills = await Promise.all(
      folders.filter((entry) => entry.isDirectory()).map((entry) => load(entry.name)),
    )
    const mode = skills.find((skill) => skill.id === MODE)
    if (mode === undefined)
      throw new Error(`${join(SKILLS, MODE, "SKILL.md")} is missing; reinstall the nustack plugin`)
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
  const file = Bun.file(path)
  if (!(await file.exists())) throw new Error(`${path} is missing; reinstall the nustack plugin`)
  const text = await file.text()
  const match = FRONTMATTER.exec(text)
  if (match?.[1] === undefined)
    throw new Error(`${path} has no frontmatter; reinstall the nustack plugin`)
  let fields: Record<string, unknown>
  try {
    fields = Object(YAML.parse(match[1]))
  } catch (error) {
    throw new Error(
      `${path} holds frontmatter that is not YAML (${error}); reinstall the nustack plugin`,
    )
  }
  if (typeof fields.name !== "string" || typeof fields.description !== "string")
    throw new Error(`${path} names no skill or description; reinstall the nustack plugin`)
  return {
    id: id as Skill.ID,
    name: fields.name as Skill.Name,
    description: fields.description,
    autoinvoke: fields["disable-model-invocation"] !== true,
    path: path as Skill.Info["path"],
    content: text.slice(match[0].length),
  }
}
