/** The OpenCode plugin that registers each nustack skill with OpenCode, in the shape OpenCode's own types give a skill. */
import { readdir, readFile } from "node:fs/promises"
import { join } from "node:path"
import type { Plugin, Skill } from "@opencode/plugin"
import { YAML } from "bun"

type Frontmatter = Record<string, unknown>

export default {
  id: "nustack",
  async setup(context: {
    skill: Pick<Plugin.Context["skill"], "transform">
  }): Promise<() => Promise<void>> {
    const skills = await readSkills(join(import.meta.dirname, "skills"))
    const registration = await context.skill.transform((editor) => {
      for (const skill of skills) editor.add(skill)
    })
    return registration.dispose
  },
} satisfies Plugin.Plugin

export async function readSkills(folder: string): Promise<Skill.Info[]> {
  const entries = await readdir(folder, { withFileTypes: true })
  const results = await Promise.allSettled(
    entries.filter((entry) => entry.isDirectory()).map(({ name }) => readSkill(folder, name)),
  )
  const failures = results.flatMap((result) =>
    result.status === "rejected" ? [String(result.reason.message)] : [],
  )
  if (failures.length > 0) throw new Error(failures.join("\n"))
  return results.flatMap((result) => (result.status === "fulfilled" ? [result.value] : []))
}

async function readSkill(folder: string, id: string): Promise<Skill.Info> {
  const path = join(folder, id, "SKILL.md")
  const content = await readFile(path, "utf8").catch(() => {
    throw new Error(
      `${path} cannot be read; give the skill a readable SKILL.md, then run make check`,
    )
  })
  const [frontmatter, body] = split(content, path)
  return {
    id: id as Skill.ID,
    name: text(frontmatter, "name", path) as Skill.Name,
    description: text(frontmatter, "description", path),
    autoinvoke: !hidden(frontmatter, path),
    path: path as Skill.Info["path"],
    content: body,
  }
}

function split(content: string, path: string): [Frontmatter, string] {
  const match = content.match(/^---\r?\n([\s\S]*?\r?\n)---(?:\r?\n|$)/)
  if (/^---\r(?!\n)/.test(content)) {
    throw new Error(
      `${path} has lines that end in a bare CR; save it with LF line endings, then run make check`,
    )
  }
  if (match?.[1] === undefined) {
    throw new Error(`${path} has no frontmatter; open it with a --- block, then run make check`)
  }
  const frontmatter = parse(match[1].replace(/\r\n?/g, "\n"), path)
  if (typeof frontmatter !== "object" || frontmatter === null || Array.isArray(frontmatter)) {
    throw new Error(
      `${path} has frontmatter that is not key: value lines; write it as key: value lines, then run make check`,
    )
  }
  return [frontmatter as Frontmatter, content.slice(match[0].length)]
}

function parse(header: string, path: string): unknown {
  try {
    return YAML.parse(header)
  } catch {
    throw new Error(`${path} has frontmatter that is not valid YAML; fix it, then run make check`)
  }
}

function text(frontmatter: Frontmatter, key: string, path: string): string {
  const value = frontmatter[key]
  if (value === undefined) {
    throw new Error(`${path} has no ${key} in its frontmatter; add one, then run make check`)
  }
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${path} has a ${key} that is not text; write its text, then run make check`)
  }
  return value
}

function hidden(frontmatter: Frontmatter, path: string): boolean {
  const value = frontmatter["disable-model-invocation"]
  if (value === undefined) {
    return false
  }
  if (typeof value !== "boolean") {
    throw new Error(
      `${path} has a disable-model-invocation that is not true or false; set it to true or false, then run make check`,
    )
  }
  return value
}
