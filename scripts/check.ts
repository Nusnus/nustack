/**
 * Checks what no tool checks: the manifests, skills, links and files a user would only meet broken, and each copy
 * nustack keeps of a fact, such as README.md's skill rows and the folders vendor.json records.
 */
import { lstat, readdir } from "node:fs/promises"
import { dirname, join, normalize, relative } from "node:path"
import { YAML } from "bun"
import { MANIFESTS, VERSION_SOURCE } from "./manifests.ts"

if (process.argv.length > 2) {
  console.error(`scripts/check.ts: takes no arguments; got ${process.argv.slice(2).join(" ")}`)
  process.exit(2)
}

// After a summary, Claude Code keeps only the first 5,000 tokens of an invoked skill
// (https://code.claude.com/docs/en/skills#skill-content-lifecycle), which 9,000 characters stay within for text
// of at least 1.8 characters per token.
const MODE_CAP = 9000
// plugin/opencode.ts and scripts/vendor.sh hold the same pattern, since a user's install cannot import from scripts/
// and a shell script cannot import at all.
const FRONTMATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/
const FRONTMATTER_COPIES = ["plugin/opencode.ts", "scripts/vendor.sh"] as const
// AGENTS.md keeps each frontmatter field on one line.
const FIELD_LINE = /^[a-z-]+: \S.*$/
const PLAYBOOKS = "plugin/skills/nus-mode/playbooks"
const BLUEPRINT = ".devin/blueprint.yaml"
const MARKETPLACES = [".claude-plugin/marketplace.json", ".cursor-plugin/marketplace.json"] as const
const problems: string[] = []
// Each file or folder the check cannot read or parse. When any exist, the run reports only these, since a comparison
// reading one would report a problem with wrong advice; the other problems show once these are fixed.
const fileProblems = new Set<string>()
const vendored = new Set<string>()
const RECORD = ["upstream", "source", "folder", "skills", "commit"] as const
for (const [name, copy] of Object.entries(Object(await jsonOf("vendor.json")))) {
  const record = Object(copy)
  const keys = Object.keys(record)
  const { folder, skills } = record
  const fits =
    Bun.deepEquals(keys.sort(), [...RECORD].sort()) &&
    RECORD.every((key) =>
      key === "skills"
        ? Array.isArray(skills) && skills.every((each) => typeof each === "string")
        : typeof record[key] === "string",
    )
  if (fits) for (const skill of skills) vendored.add(join(folder, skill))
  else
    problems.push(
      `vendor.json: ${name} needs exactly ${RECORD.join(", ")}, each a string but skills, a list of strings; got ${JSON.stringify(copy)}`,
    )
}

const [first, ...rest] = await Promise.all(MANIFESTS.map(jsonOf))
for (const [index, manifest] of rest.entries())
  if (!Bun.deepEquals(manifest, first))
    problems.push(`${MANIFESTS[index + 1]}: differs from ${MANIFESTS[0]}; match them`)
const name = stringAt(MANIFESTS[0], first, "name")
const version = stringAt(MANIFESTS[0], first, "version")
const description = stringAt(MANIFESTS[0], first, "description")
const author = stringAt(MANIFESTS[0], first, "author.name")
const opencode = await jsonOf("plugin/package.json")
for (const [key, expected] of [
  ["name", name],
  ["version", version],
] as const) {
  const actual = stringAt("plugin/package.json", opencode, key)
  if (actual !== undefined && expected !== undefined && actual !== expected)
    problems.push(
      `plugin/package.json: ${key} is ${actual}, where the manifests hold ${expected}; match them`,
    )
}
const marketplaces = await Promise.all(
  MARKETPLACES.map(async (path) => [path, await jsonOf(path)] as const),
)
for (const [path, marketplace] of marketplaces) {
  const { plugins } = Object(marketplace)
  const entry = Array.isArray(plugins)
    ? plugins.find((each) => Object(each).name === name)
    : undefined
  if (entry === undefined)
    problems.push(`${path}: lists no plugin named ${name} in plugins; add it`)
  else if (Object(entry).description !== description)
    problems.push(`${path}: the plugin's description differs from the manifests'; copy theirs`)
  const owner = stringAt(path, marketplace, "owner.name")
  if (owner !== undefined && owner !== author)
    problems.push(
      `${path}: the owner is ${owner}, where the manifests' author is ${author}; copy theirs`,
    )
}
// Claude Code reads a marketplace's own description at the top level
// (https://code.claude.com/docs/en/plugin-marketplaces), Cursor under metadata
// (https://cursor.com/docs/reference/plugins#marketplace-manifest-fields).
const claudeDescription = stringAt(MARKETPLACES[0], marketplaces[0]?.[1], "description")
const cursorDescription = stringAt(MARKETPLACES[1], marketplaces[1]?.[1], "metadata.description")
if (
  claudeDescription !== undefined &&
  cursorDescription !== undefined &&
  claudeDescription !== cursorDescription
)
  problems.push(
    `${MARKETPLACES[1]}: the marketplace description differs from ${MARKETPLACES[0]}'s; copy it`,
  )
if ((await textOf("plugin/LICENSE")) !== (await textOf("LICENSE")))
  problems.push("plugin/LICENSE: differs from LICENSE; copy LICENSE over it")

const files = (await listed("plugin", () => readdir("plugin", { recursive: true }))).map((path) =>
  join("plugin", path),
)
const authored: string[] = []
for (const path of files) {
  const link = await lstat(path).then(
    (stat) => stat.isSymbolicLink(),
    (error) => void fileProblems.add(failure(path, error)),
  )
  if (link)
    problems.push(
      `${path}: is a symlink, which some hosts skip; put the file it points to in its place, or remove it`,
    )
  else if (path.endsWith(".md") && ![...vendored].some((folder) => path.startsWith(`${folder}/`)))
    authored.push(path)
}

const nusMode = await textOf("plugin/skills/nus-mode/SKILL.md")
const folders = (
  await listed("plugin/skills", () => readdir("plugin/skills", { withFileTypes: true }))
).filter((each) => each.isDirectory())
for (const { name: folder } of folders) {
  if (vendored.has(join("plugin/skills", folder))) continue
  const path = `plugin/skills/${folder}/SKILL.md`
  const skill = await textOf(path)
  const match = FRONTMATTER.exec(skill)
  if (match?.[1] === undefined) {
    problems.push(
      `${path}: has no frontmatter; open it with name and description between --- lines`,
    )
    continue
  }
  if (match[1].split("\n").some((line) => !FIELD_LINE.test(line)))
    problems.push(
      `${path}: frontmatter holds a line that is not one whole field; keep each field on one line`,
    )
  const fields = fieldsOf(match[1])
  if (fields === undefined) {
    problems.push(`${path}: frontmatter is not a YAML mapping; write each field as name: value`)
    continue
  }
  if (fields.name !== folder)
    problems.push(`${path}: name ${fields.name} differs from its folder; rename one`)
  if (typeof fields.description !== "string") problems.push(`${path}: has no description; add one`)
  const hidden =
    fields["disable-model-invocation"] === true && Bun.deepEquals(fields.triggers, ["user"])
  const indexed = /^(principle|language)-/.test(folder)
  if (indexed && !hidden)
    problems.push(
      `${path}: is visible to the model; set disable-model-invocation: true and triggers: [user]`,
    )
  if (indexed && !nusMode.includes(`(../${folder}/SKILL.md)`))
    problems.push(
      `plugin/skills/nus-mode/SKILL.md: does not link ${folder}; add it with when it applies`,
    )
  if (folder === "nus-mode" && skill.length - match[0].length > MODE_CAP)
    problems.push(`${path}: body is over ${MODE_CAP} characters; shorten it`)
}
for (const playbook of await listed(PLAYBOOKS, () => readdir(PLAYBOOKS)))
  if (playbook.endsWith(".md") && !nusMode.includes(`(playbooks/${playbook})`))
    problems.push(
      `plugin/skills/nus-mode/SKILL.md: does not link playbooks/${playbook}; add it with when it applies`,
    )

// A link out of plugin/ works on GitHub but is dead once installed.
for (const path of authored) {
  const prose = (await textOf(path)).replace(/```[\s\S]*?```|`[^`\n]*`/g, "")
  for (const [, target = ""] of prose.matchAll(/\]\(([^)\s]+)\)/g)) {
    if (/^(https?:|mailto:|#)/.test(target)) continue
    const file = normalize(join(dirname(path), target.replace(/#.*/, "")))
    if (relative("plugin", file).startsWith("..") || !(await Bun.file(file).exists()))
      problems.push(
        `${path}: links ${target}, which is not a file in plugin/; link a plugin file or an https URL`,
      )
  }
}

// README.md's skills tables copy each skill's own description.
const readme = await textOf("README.md")
const rows = [...readme.matchAll(/^\| \[([^\]]+)\]\(plugin\/skills\/[^)]+\) \|/gm)].map(
  (row) => row[1],
)
for (const { name: folder } of folders) {
  const path = `plugin/skills/${folder}/SKILL.md`
  // The skills loop and scripts/vendor.sh --check report a missing SKILL.md.
  if (!(await Bun.file(path).exists())) continue
  const match = FRONTMATTER.exec(await textOf(path))
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

// README.md shows users the line the new-project playbook writes into a project's AGENTS.md.
const NEW_PROJECT = "plugin/skills/nus-mode/playbooks/new-project.md"
const MODE_LINE = /^( *)```markdown\n\1(.+)\n\1```$/m
const playbookLine = MODE_LINE.exec(await textOf(NEW_PROJECT))?.[2]
const readmeLine = MODE_LINE.exec(readme)?.[2]
if (playbookLine === undefined)
  problems.push(`${NEW_PROJECT}: holds no markdown block with the nus-mode line; add it`)
else if (readmeLine !== playbookLine)
  problems.push(
    `README.md: its first markdown block holds ${readmeLine}, not ${NEW_PROJECT}'s ${playbookLine}; copy it`,
  )

for (const path of FRONTMATTER_COPIES)
  if (!(await textOf(path)).includes(`/${FRONTMATTER.source}/`))
    problems.push(
      `${path}: its frontmatter pattern differs from scripts/check.ts's ${FRONTMATTER}; copy it`,
    )

// Each tool that keeps a vendored copy's bytes lists the folders vendor.json records.
const expected = [...vendored].sort()
const { ignores } = Object(await yamlOf(".markdownlint-cli2.yaml"))
const linked = expected.flatMap((folder) =>
  folder.startsWith(".agents/skills/")
    ? [folder, folder.replace(".agents/", ".claude/")]
    : [folder],
)
if (!Array.isArray(ignores) || !Bun.deepEquals([...ignores].sort(), linked.sort()))
  problems.push(
    `.markdownlint-cli2.yaml: ignores differ from vendor.json's folders and their .claude/skills links; list ${linked.join(", ")}`,
  )
const unset = [...(await textOf(".gitattributes")).matchAll(/^(\S+)\/\*\* -text$/gm)].map(
  (line) => line[1],
)
if (!Bun.deepEquals(unset.sort(), expected))
  problems.push(
    `.gitattributes: the folders it unsets text for differ from vendor.json's; list ${expected.join(", ")}`,
  )

// The blueprint installs the Bun package.json names on a machine that has none.
const packageManager = stringAt("package.json", await jsonOf("package.json"), "packageManager")
// Devin builds no machine from a blueprint that is not YAML:
// https://docs.devin.ai/onboard-devin/environment/git-backed-blueprints
await yamlOf(BLUEPRINT)
const blueprintBun = /bun-v([^/\s]+)/.exec(await textOf(BLUEPRINT))?.[1]
if (`bun@${blueprintBun}` !== packageManager)
  problems.push(
    `${BLUEPRINT}: installs Bun ${blueprintBun}, where package.json names ${packageManager}; match them`,
  )

// The release workflow runs on the manifest scripts/release.ts reads the version from.
const RELEASE_WORKFLOW = ".github/workflows/release.yml"
const releasePaths = Object(await yamlOf(RELEASE_WORKFLOW)).on?.push?.paths
if (!Bun.deepEquals(releasePaths, [VERSION_SOURCE]))
  problems.push(
    `${RELEASE_WORKFLOW}: runs on pushes to ${JSON.stringify(releasePaths)}, not to ${VERSION_SOURCE} alone; set on.push.paths to [${VERSION_SOURCE}]`,
  )

// The vendor workflow commits the bookkeeping files and each folder vendor.json records, and lists the files apart.
const BOOKKEEPING = ["CHANGELOG.md", "README.md", "vendor.json"] as const
const VENDOR_WORKFLOW = ".github/workflows/vendor.yml"
const vendorWorkflow = await textOf(VENDOR_WORKFLOW)
const { jobs } = Object(await yamlOf(VENDOR_WORKFLOW))
const addPaths = Object.values(Object(jobs))
  .flatMap((job) => Object(job).steps ?? [])
  .map((step) => Object(step).with?.["add-paths"])
  .find((paths) => typeof paths === "string")
const committed = addPaths
  ?.split("\n")
  .map((line: string) => line.trim())
  .filter(Boolean)
const vendorFolders = [...new Set([...vendored].map((path) => `${dirname(path)}/`))]
if (!Bun.deepEquals(committed?.sort(), [...BOOKKEEPING, ...vendorFolders].sort()))
  problems.push(
    `.github/workflows/vendor.yml: add-paths differ from ${[...BOOKKEEPING, ...vendorFolders].join(", ")}; list them`,
  )
if (!vendorWorkflow.includes(`bookkeeping='${BOOKKEEPING.join("|")}'`))
  problems.push(
    `.github/workflows/vendor.yml: bookkeeping differs from ${BOOKKEEPING.join("|")}; list them`,
  )

if (fileProblems.size > 0) {
  console.error([...fileProblems].join("\n"))
  process.exit(1)
}
if (problems.length > 0) {
  console.error(problems.join("\n"))
  process.exit(1)
}

async function listed<Entry>(path: string, list: () => Promise<Entry[]>): Promise<Entry[]> {
  try {
    return await list()
  } catch (error) {
    fileProblems.add(failure(path, error))
    return []
  }
}

// Names the path that failed, which a recursive listing reports in its error, with the advice its cause calls for.
function failure(path: string, error: unknown): string {
  const { code, path: failed = path } = Object(error)
  if (code === "ENOENT") return `${failed}: is missing; add it`
  if (code === "EACCES" || code === "EPERM")
    return `${failed}: cannot be read (${code}); fix its permissions or its folder's`
  if (code === "ELOOP") return `${failed}: is a symlink loop; remove it`
  return `${failed}: cannot be read (${code ?? error}); fix it`
}

async function textOf(path: string): Promise<string> {
  return (await read(path)) ?? ""
}

async function read(path: string): Promise<string | undefined> {
  try {
    return await Bun.file(path).text()
  } catch (error) {
    fileProblems.add(failure(path, error))
    return undefined
  }
}

async function jsonOf(path: string): Promise<unknown> {
  return parsed(path, "JSON", JSON.parse)
}

async function yamlOf(path: string): Promise<unknown> {
  return parsed(path, "YAML", YAML.parse)
}

async function parsed(
  path: string,
  format: string,
  parse: (text: string) => unknown,
): Promise<unknown> {
  const text = await read(path)
  if (text === undefined) return undefined
  try {
    return parse(text)
  } catch (error) {
    fileProblems.add(`${path}: is not ${format} (${error}); fix it`)
    return undefined
  }
}

// Reads the string at a dotted key of parsed JSON, reporting it where it is missing or not a string.
function stringAt(path: string, json: unknown, key: string): string | undefined {
  const value = key.split(".").reduce<unknown>((at, part) => Object(at)[part], json)
  if (typeof value === "string") return value
  problems.push(`${path}: has no ${key} string, got ${JSON.stringify(value)}; add it`)
  return undefined
}

function fieldsOf(frontmatter: string): Record<string, unknown> | undefined {
  try {
    const fields = YAML.parse(frontmatter)
    if (typeof fields === "object" && fields !== null && !Array.isArray(fields))
      return fields as Record<string, unknown>
  } catch {}
  return undefined
}
