/** Checks what no tool checks and a user would only meet broken: manifests, skills, links and the plugin's files. */
import { lstat, readdir } from "node:fs/promises"
import { dirname, join, normalize, relative } from "node:path"
import { YAML } from "bun"

// After a summary, Claude Code keeps only the first 5,000 tokens of an invoked skill:
// https://code.claude.com/docs/en/skills#skill-content-lifecycle
const MODE_CAP = 9000
const FRONTMATTER = /^---\n([\s\S]*?)\n---\n/
// Some hosts drop every field once one spans lines or holds ---.
const FIELD_LINE = /^([a-z-]+: \S.*|[a-z-]+:| {2}- \S.*)$/
const MANIFESTS = [
  "plugin/.claude-plugin/plugin.json",
  "plugin/.cursor-plugin/plugin.json",
  "plugin/.devin-plugin/plugin.json",
]
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
for (const path of MARKETPLACES) {
  const { plugins } = await Bun.file(path).json()
  if (!plugins.some((entry: { name: string }) => entry.name === first.name))
    problems.push(`${path}: lists no plugin named as the manifests; add it`)
}
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
      `${path}: frontmatter holds a line that is not one field or list entry, or holds ---; keep each on one line`,
    )
  const fields = YAML.parse(match[1]) as Record<string, unknown>
  if (fields.name !== folder) problems.push(`${path}: name differs from its folder; rename one`)
  if (typeof fields.description !== "string") problems.push(`${path}: has no description; add one`)
  const hidden =
    fields["disable-model-invocation"] === true && Bun.deepEquals(fields.triggers, ["user"])
  const principle = /^(principle|language)-/.test(folder)
  if (principle && !hidden)
    problems.push(
      `${path}: is visible to the model; set disable-model-invocation: true and triggers: [user]`,
    )
  if (principle && !index.includes(`(../${folder}/SKILL.md)`))
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
    const file = normalize(join(dirname(path), target.split("#")[0] ?? ""))
    if (relative("plugin", file).startsWith("..") || !(await Bun.file(file).exists()))
      problems.push(
        `${path}: links ${target}, which is not a file in plugin/; link a plugin file or an https URL`,
      )
  }
}

if (problems.length > 0) {
  console.error(problems.join("\n"))
  process.exit(1)
}
