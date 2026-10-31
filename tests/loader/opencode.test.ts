/** The OpenCode plugin registers every nustack skill as OpenCode reads it, and fails on a skill it cannot read. */
import { afterEach, expect, test } from "bun:test"
import { mkdir, mkdtemp, readdir, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import type { Plugin, Skill } from "@opencode/plugin"
import plugin, { readSkills } from "../../plugin/opencode.ts"

type SkillEditor = Parameters<Parameters<Plugin.Context["skill"]["transform"]>[0]>[0]

const SKILLS = join(import.meta.dirname, "..", "..", "plugin", "skills")

const folders: string[] = []

function editorOf(skills: Skill.Info[]): SkillEditor {
  return {
    list: expect.unreachable,
    get: expect.unreachable,
    add: (skill) => {
      skills.push(skill)
    },
    update: expect.unreachable,
    remove: expect.unreachable,
  }
}

async function folderWith(skill: string): Promise<string> {
  const folder = await mkdtemp(join(tmpdir(), "nustack-"))
  folders.push(folder)
  await mkdir(join(folder, skill))
  return folder
}

async function skillIn(text: string): Promise<string> {
  const folder = await folderWith("a-skill")
  await writeFile(join(folder, "a-skill", "SKILL.md"), text)
  return folder
}

afterEach(async () => {
  await Promise.all(folders.splice(0).map((folder) => rm(folder, { recursive: true })))
})

test("the plugin registers every shipped skill, and its cleanup removes them", async () => {
  const added: Skill.Info[] = []
  const dispose = expect.unreachable
  const cleanup = await plugin.setup({
    skill: {
      transform: async (edit) => {
        edit(editorOf(added))
        return { dispose }
      },
    },
  })
  expect(added.map((skill): string => skill.id).sort()).toEqual((await readdir(SKILLS)).sort())
  expect(cleanup).toBe(dispose)
})

test("a file beside the skill folders is not a skill", async () => {
  const folder = await skillIn("---\nname: a-skill\ndescription: A skill.\n---\n")
  await writeFile(join(folder, "README.md"), "# Skills\n")
  expect((await readSkills(folder)).map((skill): string => skill.id)).toEqual(["a-skill"])
})

test("a skill keeps its file's name, description, path and body", async () => {
  const text = '---\nname: a-skill\ndescription: "A skill: \\"quoted\\"."\n---\n# A\n---\nB\n'
  const folder = await skillIn(text)
  const path = join(folder, "a-skill", "SKILL.md")
  expect(await readSkills(folder)).toEqual([
    {
      id: "a-skill",
      name: "a-skill",
      description: 'A skill: "quoted".',
      autoinvoke: true,
      path,
      content: "# A\n---\nB\n",
    },
  ] as Skill.Info[])
})

test("a skill folder without a SKILL.md fails with the remedy", async () => {
  await expect(readSkills(await folderWith("a-skill"))).rejects.toThrow(
    "cannot be read; give the skill a readable SKILL.md, then run make check",
  )
})

test("every skill that fails is reported in the same run", async () => {
  const folder = await folderWith("a-skill")
  await mkdir(join(folder, "b-skill"))
  const error = await readSkills(folder).catch((caught: unknown) => caught)
  expect(String(error)).toContain(join(folder, "a-skill", "SKILL.md"))
  expect(String(error)).toContain(join(folder, "b-skill", "SKILL.md"))
})

test("a skill whose lines end in CRLF loads", async () => {
  const folder = await skillIn("---\r\nname: a-skill\r\ndescription: A skill.\r\n---\r\n# A\r\n")
  expect((await readSkills(folder)).map((skill) => [skill.name, skill.content])).toEqual([
    ["a-skill", "# A\r\n"],
  ])
})

test("a stray CR in frontmatter breaks a line", async () => {
  const folder = await skillIn("---\nname: a-skill\ndescription: a\r\r\n b\n---\n")
  expect((await readSkills(folder)).map((skill) => skill.description)).toEqual(["a\nb"])
})

test("a skill whose frontmatter is not YAML fails without the parser's detail", async () => {
  const folder = await skillIn("---\nname: [a\n---\n")
  const path = join(folder, "a-skill", "SKILL.md")
  await expect(readSkills(folder)).rejects.toThrow(
    new Error(`${path} has frontmatter that is not valid YAML; fix it, then run make check`),
  )
})

test("a skill with disable-model-invocation: true is hidden from the model", async () => {
  const folder = await skillIn(
    "---\nname: a-skill\ndescription: A skill.\ndisable-model-invocation: true\n---\n",
  )
  expect((await readSkills(folder)).map((skill) => skill.autoinvoke)).toEqual([false])
})

test.each([
  ["true # hidden from the model", false],
  ["True", false],
  ["false", true],
])("disable-model-invocation: %s sets autoinvoke to %p", async (value, autoinvoke) => {
  const folder = await skillIn(
    `---\nname: a-skill\ndescription: A skill.\ndisable-model-invocation: ${value}\n---\n`,
  )
  expect((await readSkills(folder)).map((skill) => skill.autoinvoke)).toEqual([autoinvoke])
})

test("a principle is hidden from the model and the mode is not", async () => {
  const skills = await readSkills(SKILLS)
  const mode = skills.find((skill) => skill.id === "nus-mode")
  expect(mode?.autoinvoke).toBe(true)
  expect(
    skills.filter((skill) => skill.id.startsWith("principle-")).every((skill) => !skill.autoinvoke),
  ).toBe(true)
})

test.each([
  ["# A\n", "has no frontmatter; open it with a --- block"],
  [
    "---\nname: a-skill\ndescription: A skill.\n---x\n",
    "has no frontmatter; open it with a --- block",
  ],
  ["---\rname: a-skill\rdescription: A skill.\r---\r", "end in a bare CR; save it with LF"],
  ["---\nname: [a\n---\n", "has frontmatter that is not valid YAML"],
  ["---\n- a\n---\n", "has frontmatter that is not key: value lines"],
  ["---\nnull\n---\n", "has frontmatter that is not key: value lines"],
  ["---\n7\n---\n", "has frontmatter that is not key: value lines"],
  ["---\ndescription: A skill.\n---\n", "has no name in its frontmatter; add one"],
  ["---\nname: a-skill\n---\n", "has no description in its frontmatter; add one"],
  ["---\nname: 7\ndescription: A skill.\n---\n", "has a name that is not text; write its text"],
  [
    '---\nname: a-skill\ndescription: " "\n---\n',
    "has a description that is not text; write its text",
  ],
  [
    "---\nname: a-skill\ndescription: A skill.\ndisable-model-invocation: yes\n---\n",
    "has a disable-model-invocation that is not true or false; set it to true or false",
  ],
  [
    "---\nname: a-skill\ndescription: A skill.\ndisable-model-invocation: null\n---\n",
    "has a disable-model-invocation that is not true or false; set it to true or false",
  ],
])("a skill whose frontmatter is %j fails with the remedy", async (text, message) => {
  const error = await readSkills(await skillIn(text)).catch((caught: unknown) => caught)
  expect(String(error)).toContain(message)
  expect(String(error)).toEndWith(", then run make check")
})

test.each([
  "---\nname: [canary\n---\n",
  "---\nname: [canary]\ndescription: A skill.\n---\n",
  "---\nname: a-skill\ndescription: A skill.\ndisable-model-invocation: canary\n---\n",
])("a skill whose frontmatter is %j fails without echoing its value", async (text) => {
  const error = await readSkills(await skillIn(text)).catch((caught: unknown) => caught)
  expect(error).toBeInstanceOf(Error)
  expect(String(error)).not.toContain("canary")
})
