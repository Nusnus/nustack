/**
 * Checks what no tool checks: the manifests, skills, links and files a user would only meet broken, and each copy
 * nustack keeps of a fact, such as README.md's skill rows and the folders vendor.json records.
 */
import { lstat, readdir } from "node:fs/promises"
import { dirname, join, normalize, relative } from "node:path"
import { YAML } from "bun"
import { MANIFESTS } from "./manifests.ts"

// After a summary, Claude Code keeps only the first 5,000 tokens of an invoked skill
// (https://code.claude.com/docs/en/skills#skill-content-lifecycle), which 9,000 characters stay within for text
// of at least 1.8 characters per token.
const MODE_CAP = 9000
// The same pattern plugin/opencode.ts reads, which a user's install cannot import from scripts/.
const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/
// Some hosts drop every field once one spans lines or holds ---.
const FIELD_LINE = /^[a-z-]+: \S.*$/
const MARKETPLACES = [".claude-plugin/marketplace.json", ".cursor-plugin/marketplace.json"]
const vendor = (await Bun.file("vendor.json").json()) as Record<
  string,
  { folder: string; skills: string[] }
>
const vendored = new Set(
  Object.values(vendor).flatMap((copy) => copy.skills.map((skill) => join(copy.folder, skill))),
)
const problems: string[] = []

const [first, ...rest] = await Promise.all(MANIFESTS.map((path) => Bun.file(path).json()))
for (const [index, manifest] of rest.entries())
  if (!Bun.deepEquals(manifest, first))
    problems.push(`${MANIFESTS[index + 1]}: differs from ${MANIFESTS[0]}; match them`)
const opencode = await Bun.file("plugin/package.json").json()
if (opencode.name !== first.name || opencode.version !== first.version)
  problems.push("plugin/package.json: name or version differs from the manifests; match them")
const marketplaces = await Promise.all(MARKETPLACES.map((path) => Bun.file(path).json()))
for (const [index, { owner, plugins }] of marketplaces.entries()) {
  const path = MARKETPLACES[index]
  const entry = plugins.find((each: { name: string }) => each.name === first.name)
  if (entry === undefined) problems.push(`${path}: lists no plugin named as the manifests; add it`)
  else if (entry.description !== first.description)
    problems.push(`${path}: the plugin's description differs from the manifests'; copy theirs`)
  if (owner.name !== first.author.name)
    problems.push(`${path}: the owner differs from the manifests' author; copy theirs`)
}
// Claude Code reads a marketplace's own description at the top level, Cursor under metadata.
const [claudeMarketplace, cursorMarketplace] = marketplaces
if (claudeMarketplace.description !== cursorMarketplace.metadata.description)
  problems.push(
    `${MARKETPLACES[1]}: the marketplace description differs from ${MARKETPLACES[0]}'s; copy it`,
  )
if ((await Bun.file("plugin/LICENSE").text()) !== (await Bun.file("LICENSE").text()))
  problems.push("plugin/LICENSE: differs from LICENSE; copy LICENSE over it")

const files = (await readdir("plugin", { recursive: true })).map((path) => join("plugin", path))
const authored: string[] = []
for (const path of files) {
  if ((await lstat(path)).isSymbolicLink())
    problems.push(`${path}: is a symlink, which some hosts skip; copy the file`)
  else if (path.endsWith(".md") && ![...vendored].some((folder) => path.startsWith(`${folder}/`)))
    authored.push(path)
}

const index = await Bun.file("plugin/skills/nus-mode/SKILL.md").text()
const folders = (await readdir("plugin/skills", { withFileTypes: true })).filter((each) =>
  each.isDirectory(),
)
for (const { name: folder } of folders) {
  if (vendored.has(join("plugin/skills", folder))) continue
  const path = `plugin/skills/${folder}/SKILL.md`
  const text = await Bun.file(path).text()
  const match = FRONTMATTER.exec(text)
  if (match?.[1] === undefined) {
    problems.push(
      `${path}: has no frontmatter; open it with name and description between --- lines`,
    )
    continue
  }
  if (match[1].split("\n").some((line) => !FIELD_LINE.test(line) || line.includes("---")))
    problems.push(
      `${path}: frontmatter holds a line that is not one whole field, or holds ---; keep each field on one line`,
    )
  const fields = fieldsOf(match[1])
  if (fields === undefined) {
    problems.push(`${path}: frontmatter is not a YAML mapping; write each field as name: value`)
    continue
  }
  if (fields.name !== folder) problems.push(`${path}: name differs from its folder; rename one`)
  if (typeof fields.description !== "string") problems.push(`${path}: has no description; add one`)
  const hidden =
    fields["disable-model-invocation"] === true && Bun.deepEquals(fields.triggers, ["user"])
  const indexed = /^(principle|language)-/.test(folder)
  if (indexed && !hidden)
    problems.push(
      `${path}: is visible to the model; set disable-model-invocation: true and triggers: [user]`,
    )
  if (indexed && !index.includes(`(../${folder}/SKILL.md)`))
    problems.push(
      `plugin/skills/nus-mode/SKILL.md: does not link ${folder}; add it with when it applies`,
    )
  if (folder === "nus-mode" && text.length - match[0].length > MODE_CAP)
    problems.push(`${path}: body is over ${MODE_CAP} characters; shorten it`)
}
for (const playbook of await readdir("plugin/skills/nus-mode/playbooks"))
  if (playbook.endsWith(".md") && !index.includes(`(playbooks/${playbook})`))
    problems.push(
      `plugin/skills/nus-mode/SKILL.md: does not link playbooks/${playbook}; add it with when it applies`,
    )

// A link out of plugin/ works on GitHub but is dead once installed.
for (const path of authored) {
  const text = (await Bun.file(path).text()).replace(/```[\s\S]*?```|`[^`\n]*`/g, "")
  for (const [, target = ""] of text.matchAll(/\]\(([^)\s]+)\)/g)) {
    if (/^(https?:|mailto:|#)/.test(target)) continue
    const file = normalize(join(dirname(path), target.replace(/#.*/, "")))
    if (relative("plugin", file).startsWith("..") || !(await Bun.file(file).exists()))
      problems.push(
        `${path}: links ${target}, which is not a file in plugin/; link a plugin file or an https URL`,
      )
  }
}

// README.md's skills tables copy each skill's own description.
const readme = await Bun.file("README.md").text()
const rows = [...readme.matchAll(/^\| \[([^\]]+)\]\(plugin\/skills\/[^)]+\) \|/gm)].map(
  (row) => row[1],
)
for (const { name: folder } of folders) {
  const path = `plugin/skills/${folder}/SKILL.md`
  const match = FRONTMATTER.exec(await Bun.file(path).text())
  const description = match?.[1] === undefined ? undefined : fieldsOf(match[1])?.description
  if (typeof description !== "string") {
    // The skills loop reports an authored skill's frontmatter.
    if (vendored.has(join("plugin/skills", folder)))
      problems.push(`${path}: has no description in YAML frontmatter; vendor it again`)
    continue
  }
  const row = `| [${folder}](plugin/skills/${folder}/SKILL.md) | ${description} |`
  if (!readme.split("\n").includes(row))
    problems.push(`README.md: has no row ${row}; copy the skill's description into its row`)
}
for (const row of new Set(rows))
  if (!folders.some((each) => each.name === row))
    problems.push(
      `README.md: a skills-table row names ${row}, which plugin/skills/ does not hold; drop it`,
    )
  else if (rows.filter((each) => each === row).length > 1)
    problems.push(`README.md: ${row} has more than one skills-table row; keep one`)

// Each tool that keeps a vendored copy's bytes lists the folders vendor.json records.
const expected = [...vendored].sort()
const lint = YAML.parse(await Bun.file(".markdownlint-cli2.yaml").text()) as { ignores: string[] }
const linked = expected.flatMap((folder) =>
  folder.startsWith(".agents/skills/")
    ? [folder, folder.replace(".agents/", ".claude/")]
    : [folder],
)
if (!Bun.deepEquals([...lint.ignores].sort(), linked.sort()))
  problems.push(
    `.markdownlint-cli2.yaml: ignores differ from vendor.json's folders and their .claude/skills links; list ${linked.join(", ")}`,
  )
const unset = [...(await Bun.file(".gitattributes").text()).matchAll(/^(\S+)\/\*\* -text$/gm)].map(
  (line) => line[1],
)
if (!Bun.deepEquals(unset.sort(), expected))
  problems.push(
    `.gitattributes: the folders it unsets text for differ from vendor.json's; list ${expected.join(", ")}`,
  )

// Devin sessions build with the Bun that package.json names.
const { packageManager } = await Bun.file("package.json").json()
const blueprintBun = /bun-v(\S+)/.exec(await Bun.file(".devin/blueprint.yaml").text())?.[1]
if (`bun@${blueprintBun}` !== packageManager)
  problems.push(
    `.devin/blueprint.yaml: installs Bun ${blueprintBun}, where package.json names ${packageManager}; match them`,
  )

if (problems.length > 0) {
  console.error(problems.join("\n"))
  process.exit(1)
}

function fieldsOf(frontmatter: string): Record<string, unknown> | undefined {
  try {
    const fields = YAML.parse(frontmatter)
    if (typeof fields === "object" && fields !== null && !Array.isArray(fields))
      return fields as Record<string, unknown>
  } catch {}
  return undefined
}
