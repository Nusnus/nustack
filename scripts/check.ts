/**
 * nustack's commit-time check. It reads the files Git tracks, or would track, in the folders the rules cover, prints
 * each break of the rules --help lists with the file, the field and the fix, and exits 1 on any. A problem repeats no
 * value read from a file, apart from a link's target and a path or skill name a record lists.
 */
import { isUtf8 } from "node:buffer"
import { basename, dirname, join, normalize } from "node:path"
import { usage } from "./command.ts"
import { gitBytes } from "./git.ts"
import { type Link, type Markdown, markdown, type Span } from "./markdown.ts"
import { MANIFESTS, MARKETPLACES, metadataProblems, PYPROJECT } from "./metadata.ts"
import { blobOf, KEBAB, parseRecord, RECORD_FOLDERS } from "./record.ts"
import {
  decode,
  isObject,
  once,
  type Problem,
  problem,
  readEntry,
  symlinkProblem,
  type Tree,
} from "./tree.ts"
import { workflowProblems } from "./workflows.ts"

type Loader = typeof import("../plugin/opencode.ts")
// The check imports the loader as it runs, and only once its file exists, so a missing loader, which the layout rule
// names, leaves the skills unread; any failure to load it is the loader's own bug, so it stops the run.
let loader: Loader | undefined
const MISSING_LOADER = problem("plugin/opencode.ts: is missing; restore it")
const MAX_LINES = 500
// The Agent Skills limits: https://agentskills.io/specification
const NAME_CAP = 64
const DESCRIPTION_CAP = 1024
// AGENTS.md › Where things live names plugin/skills/' one mode, whose name no copy may take. It is a constant, not
// read from the tree, since a record that lists the mode's name turns its folder into a copy, which the tree then
// shows as no authored skill.
const MODE = "nus-mode"
// Claude Code keeps an invoked skill's first 5,000 tokens through a summary: https://code.claude.com/docs/en/skills
// 9,000 characters, with the base-directory line the smoke test records Claude Code adding (tests/fixtures/bundle.ts
// builds it), stay within them for text above about 1.85 characters per token.
const MODE_CAP = 9000
const AUTHORED_KEYS = Object.freeze(["name", "description", "disable-model-invocation", "triggers"])
const INDEX = Object.freeze({
  playbook: "Playbooks",
  principle: "Principles",
  language: "Languages",
} as const)

const RULES = Object.freeze({
  metadata:
    "the host manifests are the same JSON, with a kebab-case name, a <major>.<minor>.<patch> version, a description and a repository; plugin/package.json holds their name and version, pyproject.toml their version, and each marketplace lists the plugin by their name; pyproject.toml holds at most 16384 characters and nests its arrays and inline tables at most 200 levels deep, counting brackets, braces, indent and block indicators, while Bun parses its dotted keys and table headers without deep recursion, so Bun's parser cannot crash on it",
  workflows:
    "the release workflow sets jobs.ci.needs: tag and jobs.publish.needs: ci, and the CI workflow sets jobs.release-zip.needs: make-check, each workflow holding at most 16384 characters and nesting at most 200 levels deep, counting brackets, braces, indent and block indicators, so Bun's parser cannot crash on it",
  layout:
    "plugin/ holds only the host manifests, each skill's SKILL.md, the mode's playbooks, the OpenCode loader with its package.json, the vendored copies and a LICENSE equal to the repository's, which exists, and no symlink",
  skills: `each skill folder is named in kebab case and holds a SKILL.md whose name is the folder's and whose description is filled in, with a name of at most ${NAME_CAP} characters and a description of at most ${DESCRIPTION_CAP}; an authored one holds in its frontmatter only lines that each are a field, <key>: <value>, or a list entry under a field with no value, <spaces>- <value>, with no field repeated and no --- in a value, holds no field but ${AUTHORED_KEYS.join(", ")}, sets disable-model-invocation: true and triggers: [user] in a principle- or language- skill and neither in the mode, and stays under ${MAX_LINES} lines`,
  mode: `plugin/skills/ holds exactly one mode, ${MODE}, whose body stays within ${MODE_CAP} characters, and links each playbook under ## ${INDEX.playbook}, each principle under ## ${INDEX.principle} and each language skill under ## ${INDEX.language}`,
  links:
    "each link, image, autolink or link definition GitHub renders in an authored Markdown file under plugin/, so none in code or frontmatter, is an https, http or mailto URL, an anchor, or a file under plugin/",
  vendored:
    "vendored/ holds only records named <copy>.json in kebab case, each of a record's shape, and each skill folder a record names holds exactly the files it lists, at the Git blobs it lists",
  copies:
    "each skill folder a record names has its line <folder>/** -text in .gitattributes, and only such lines follow the first of them, so no checkout or git archive rewrites its line endings",
  endings: ".gitattributes sets plugin/** text eol=lf",
} as const)

// The kinds of skill nustack writes besides its mode, each named by its prefix.
const SKILL_KINDS = Object.freeze(["principle", "language"] as const)
// The plugin's own files besides the host manifests, which MANIFESTS lists.
const PLUGIN_FILE = new RegExp(
  String.raw`^plugin/(?:LICENSE|opencode\.ts|package\.json|skills/[a-z0-9-]+/SKILL\.md|skills/(?!${SKILL_KINDS.map((kind) => `${kind}-`).join("|")})[a-z0-9-]+/playbooks/[a-z0-9-]+\.md)$`,
)
const READ = Object.freeze([
  "plugin",
  "vendored",
  ".agents",
  ".github/workflows",
  ".gitattributes",
  "LICENSE",
  PYPROJECT,
  ...MARKETPLACES,
])
// The loader's messages offer reinstalling the plugin as a second fix, which only a plugin user needs.
const LOADER_FIX = /, or reinstall the nustack plugin$/
// A frontmatter field, <key>: <value>, and a list entry under a field with no value, <spaces>- <value>.
const FIELD = /^([A-Za-z][\w-]*):(?: (.*))?$/
const ENTRY = /^ +- \S/

const CHECKS: Record<keyof typeof RULES, (tree: Tree) => Problem[]> = Object.freeze({
  metadata: metadataProblems,
  workflows: workflowProblems,
  layout: layoutProblems,
  skills: (tree) =>
    loader === undefined ? [] : skillFolders(tree).flatMap((folder) => skillProblems(tree, folder)),
  mode: modeProblems,
  links: linkProblems,
  vendored: (tree) => under(tree, "vendored/").flatMap((path) => recordProblems(tree, path)),
  copies: copyProblems,
  endings: endingProblems,
})

export async function check(tree: Tree): Promise<Problem[]> {
  loader = await load()
  // Two rules can find one break, such as a symlinked manifest, and the problem shows once.
  return [...new Set(Object.values(CHECKS).flatMap((rule) => rule(tree)))]
}

async function load(): Promise<Loader | undefined> {
  const path = join(import.meta.dirname, "../plugin/opencode.ts")
  return (await Bun.file(path).exists()) ? import(path) : undefined
}

function layoutProblems(tree: Tree): Problem[] {
  const problems = under(tree, "plugin/").flatMap((path) => {
    if (tree.get(path) === "symlink") return [symlinkProblem(path)]
    if (MANIFESTS.includes(path) || PLUGIN_FILE.test(path) || inCopy(tree, path)) return []
    return [problem(`${path}: is not a file the plugin installs; move it out of plugin/`)]
  })
  if (!tree.has("plugin/opencode.ts")) problems.push(MISSING_LOADER)
  const license = tree.get("LICENSE")
  if (license === "symlink") problems.push(symlinkProblem("LICENSE"))
  else if (license === undefined) problems.push(problem("LICENSE: is missing; restore it"))
  else if (!Bun.deepEquals(tree.get("plugin/LICENSE"), license))
    problems.push(problem("plugin/LICENSE: is not the repository's LICENSE; copy that one here"))
  return problems
}

function skillProblems(tree: Tree, folder: string): Problem[] {
  const name = folder.slice("plugin/skills/".length)
  if (!KEBAB.test(name)) return [problem(`${folder}: is not named in kebab case; rename it`)]
  const read = skillFile(tree, folder)
  if (typeof read === "string")
    return vendoredFolders(tree).includes(folder) ? [read] : [read, ...lineProblems(tree, folder)]
  const { file, frontmatter } = read
  const problems: Problem[] = []
  try {
    if (file.info(name).name !== name)
      problems.push(problem(`${file.path}: name is not its folder's; use one for both`))
  } catch (error) {
    problems.push(loaderProblem(error, file.path))
  }
  const description = frontmatter.get("description")
  if (name.length > NAME_CAP)
    problems.push(problem(`${file.path}: name has over ${NAME_CAP} characters; shorten it`))
  if (typeof description === "string" && description.length > DESCRIPTION_CAP)
    problems.push(
      problem(`${file.path}: description has over ${DESCRIPTION_CAP} characters; shorten it`),
    )
  if (vendoredFolders(tree).includes(folder)) return problems
  problems.push(...frontmatterProblems(file.path, file.text))
  for (const key of frontmatter.keys())
    if (!AUTHORED_KEYS.includes(key))
      problems.push(
        problem(`${file.path}: holds a field outside ${AUTHORED_KEYS.join(", ")}; drop it`),
      )
  const invocation = [frontmatter.get("disable-model-invocation"), frontmatter.get("triggers")]
  if (kindOf(folder) === "mode" && !Bun.deepEquals(invocation, [undefined, undefined]))
    problems.push(
      problem(
        `${file.path}: sets disable-model-invocation or triggers, which a mode leaves unset; drop both, or name the folder principle-<name> or language-<name> if it is one`,
      ),
    )
  if (kindOf(folder) !== "mode" && !Bun.deepEquals(invocation, [true, ["user"]]))
    problems.push(
      problem(`${file.path}: needs disable-model-invocation: true and triggers: [user]`),
    )
  return [...problems, ...lineProblems(tree, folder)]
}

// Counts the lines of a SKILL.md the loader refuses too, so a missing frontmatter hides no other problem.
function lineProblems(tree: Tree, folder: string): Problem[] {
  const path = `${folder}/SKILL.md`
  const read = decode(tree, path, (text) => text)
  if (!Array.isArray(read)) return []
  const [text] = read
  const lines = text.split("\n").length - (text.endsWith("\n") ? 1 : 0)
  if (lines < MAX_LINES) return []
  return [problem(`${path}: has ${lines} lines, where it needs under ${MAX_LINES}; shorten it`)]
}

function modeProblems(tree: Tree): Problem[] {
  const copied = vendoredFolders(tree)
  const authored = skillFolders(tree).filter((folder) => !copied.includes(folder))
  const modes = authored.filter(
    (folder) => kindOf(folder) === "mode" && KEBAB.test(basename(folder)),
  )
  const [mode] = modes
  if (mode === undefined || modes.length > 1)
    return [
      problem(
        `plugin/skills: holds ${modes.length} modes, where it needs exactly 1; keep one mode, and name each other skill principle-<name> or language-<name>`,
      ),
    ]
  if (basename(mode) !== MODE)
    return [problem(`plugin/skills: holds a mode not named ${MODE}; name its folder ${MODE}`)]
  const file = `${mode}/SKILL.md`
  if (typeof skillFile(tree, mode) === "string") return []
  const read = decode(tree, file, markdown)
  if (!Array.isArray(read)) return []
  const text = read[0]
  const body = text.text.slice(text.blocks.find(({ type }) => type === "yaml")?.end ?? 0).trim()
  const problems: Problem[] = []
  if (body.length > MODE_CAP)
    problems.push(problem(`${file}: body has ${body.length} characters, over ${MODE_CAP}; cut it`))
  const indexed = written(text).map(
    (link) => `${sectionOf(text, link)} ${normalize(join(mode, link.destination))}`,
  )
  const expected = [
    ...under(tree, `${mode}/playbooks/`).map((path) => [INDEX.playbook, path] as const),
    ...authored.flatMap((folder) => {
      const kind = kindOf(folder)
      return kind === "mode" ? [] : [[INDEX[kind], `${folder}/SKILL.md`] as const]
    }),
  ]
  for (const [section, path] of expected)
    if (!indexed.includes(`${section} ${path}`))
      problems.push(problem(`${file}: ## ${section} does not link ${path}; link it there`))
  return problems
}

function linkProblems(tree: Tree): Problem[] {
  return under(tree, "plugin/")
    .filter((path) => path.endsWith(".md") && !inCopy(tree, path))
    .flatMap((path) => {
      const read = decode(tree, path, markdown)
      if (!Array.isArray(read)) return [read.problem]
      return written(read[0])
        .map(({ destination }) => destination)
        .filter((target) => !/^(?:https?:|mailto:|#)/i.test(target))
        .filter((target) => {
          if (target.startsWith("/")) return true
          const resolved = normalize(join(dirname(path), target.split("#")[0] ?? ""))
          return climbsOut(path, target) || !(tree.get(resolved) instanceof Uint8Array)
        })
        .map((target) =>
          problem(
            target.startsWith("/")
              ? `${path}: links the absolute path ${target}, which breaks once the plugin moves; link it by its path from this file`
              : `${path}: links ${target}, no file under plugin/; link one, or a full URL`,
          ),
        )
    })
}

// The release zip holds plugin/'s contents at its root, so a target that climbs above plugin/ leaves the installed
// plugin, even where it climbs back in.
function climbsOut(path: string, target: string): boolean {
  let depth = dirname(path).split("/").length - 1
  for (const segment of (target.split("#")[0] ?? "").split("/")) {
    if (segment === "..") depth -= 1
    else if (segment !== "." && segment !== "") depth += 1
    if (depth < 0) return true
  }
  return false
}

function recordProblems(tree: Tree, path: string): Problem[] {
  const record = parseRecord(path, tree.get(path))
  if (Array.isArray(record)) return record
  const listed = Object.keys(record.files).map((file) => `${record.folder}/${file}`)
  return [
    ...record.skills
      .flatMap((skill) => under(tree, `${record.folder}/${skill}/`))
      .filter((file) => !listed.includes(file))
      .map((file) => problem(`${file}: is not in ${path}; remove it, or rerun the sync`)),
    ...listed.flatMap((file) => {
      const bytes = tree.get(file)
      const blob = record.files[file.slice(record.folder.length + 1)]
      if (bytes instanceof Uint8Array && blobOf(bytes) === blob) return []
      return [
        problem(`${file}: is missing or not the blob ${path} lists; restore it, or rerun the sync`),
      ]
    }),
  ]
}

// A copy's files keep their bytes in a checkout and in git archive's zip only where .gitattributes unsets text, since a
// core.autocrlf or eol setting rewrites a text file's line endings there, and the blobs the vendored rule reads stay as
// they were. A problem repeats a folder only from a record the schema accepts, as AGENTS.md › Harness code says.
function copyProblems(tree: Tree): Problem[] {
  const attributes = decode(tree, ".gitattributes", (text) => text)
  if (!Array.isArray(attributes)) return [attributes.problem]
  const lines = attributeLines(attributes[0])
  // A later line wins, so a line after the first -text one that sets text again would undo it for the copies.
  const first = lines.findIndex((line) => line.endsWith(" -text"))
  const order =
    first >= 0 && lines.slice(first).some((line) => !line.endsWith(" -text"))
      ? [
          problem(
            ".gitattributes: holds a line after the first that unsets text; move it above those lines",
          ),
        ]
      : []
  return order.concat(
    under(tree, "vendored/").flatMap((path) => {
      const record = parseRecord(path, tree.get(path))
      if (Array.isArray(record)) return []
      return record.skills
        .map((skill) => `${record.folder}/${skill}`)
        .filter((folder) => !lines.includes(`${folder}/** -text`))
        .map((folder) =>
          problem(
            `.gitattributes: does not unset text for ${folder}; add the line ${folder}/** -text`,
          ),
        )
    }),
  )
}

// .gitattributes holds the line plugin/** text eol=lf, whose own comment says what it guards.
function endingProblems(tree: Tree): Problem[] {
  const attributes = decode(tree, ".gitattributes", (text) => text)
  if (!Array.isArray(attributes) || attributeLines(attributes[0]).includes("plugin/** text eol=lf"))
    return []
  return [problem(".gitattributes: does not set plugin/** text eol=lf; add that line")]
}

function attributeLines(text: string): string[] {
  return text
    .split(/\r?\n/)
    .filter((line) => line.trim() !== "" && !line.trimStart().startsWith("#"))
}

// Reads only a record's folder and skills, so a record broken elsewhere keeps its copy's files from reading as stray.
function vendoredFolders(tree: Tree): string[] {
  return once(tree, vendoredFolders, () =>
    under(tree, "vendored/").flatMap((path) => {
      const record = decode(tree, path)
      const read = Array.isArray(record) && isObject(record[0]) ? record[0] : {}
      const { folder, skills } = read
      if (!RECORD_FOLDERS.some((known) => known === folder) || !Array.isArray(skills)) return []
      return skills.map((skill) => `${folder}/${skill}`)
    }),
  )
}

function inCopy(tree: Tree, path: string): boolean {
  return vendoredFolders(tree).some((folder) => path.startsWith(`${folder}/`))
}

function skillFolders(tree: Tree): string[] {
  const nested = under(tree, "plugin/skills/").filter((path) => path.split("/").length > 3)
  return [...new Set(nested.map((path) => path.split("/").slice(0, 3).join("/")))]
}

function skillFile(tree: Tree, folder: string) {
  return once(tree, folder, () => {
    const path = `${folder}/SKILL.md`
    const bytes = tree.get(path)
    if (!(bytes instanceof Uint8Array))
      return problem(`${folder}: has no SKILL.md; add one or remove it`)
    if (loader === undefined) return MISSING_LOADER
    try {
      const file = loader.SkillFile.decode(path, bytes)
      const [frontmatter] = file.split()
      return { file, frontmatter }
    } catch (error) {
      return loaderProblem(error, path)
    }
  })
}

function loaderProblem(error: unknown, path: string): Problem {
  if (loader === undefined || !(error instanceof loader.SkillError)) throw error
  const message = error.message.replace(LOADER_FIX, "")
  return problem(
    message.startsWith(`${path} `) ? `${path}: ${message.slice(path.length + 1)}` : message,
  )
}

function kindOf(folder: string): "mode" | (typeof SKILL_KINDS)[number] {
  return SKILL_KINDS.find((kind) => folder.startsWith(`plugin/skills/${kind}-`)) ?? "mode"
}

// The destinations a text writes: each inline link, image and autolink, and each definition, whose destination each
// link or image that names its label shares.
function written(read: Markdown): readonly Pick<Link, "start" | "end" | "destination">[] {
  return [...read.links.filter(({ label }) => label === undefined), ...read.definitions]
}

// The text of the ## heading a value sits under, or "" above the first.
function sectionOf(read: Markdown, at: Span): string {
  return read.headings.findLast(({ depth, start }) => depth === 2 && start < at.start)?.text ?? ""
}

function under(tree: Tree, prefix: string): string[] {
  return [...tree.keys()].filter((path) => path.startsWith(prefix)).sort()
}

// Some hosts drop every field once one spans lines or holds ---, as AGENTS.md › Writing skill text says, and a host
// that reads frontmatter line by line, not as YAML, reads a line only as a field or a list entry.
function frontmatterProblems(path: string, text: string): Problem[] {
  const lines = (loader?.SkillFile.FRONTMATTER.exec(text)?.[1] ?? "").split(/\r?\n/).slice(0, -1)
  const keys: string[] = []
  const reasons = new Set<string>()
  let listing = false
  for (const line of lines) {
    const field = FIELD.exec(line)
    if (field !== null) {
      keys.push(field[1] ?? "")
      listing = field[2] === undefined
    } else if (!(listing && ENTRY.test(line)))
      reasons.add(
        "holds a line that is neither a field, <key>: <value>, nor a list entry under a field with no value, <spaces>- <value>; keep each field and entry to one line",
      )
  }
  if (lines.some((line) => line.includes("---"))) reasons.add("a value holds ---; reword it")
  if (new Set(keys).size < keys.length) reasons.add("repeats a field; keep one")
  return [...reasons].map((reason) => problem(`${path}: ${reason}`))
}

export async function readTree(root: string): Promise<Tree> {
  const bytes = await gitBytes(["ls-files", "-z", "-co", "--exclude-standard", "--", ...READ], root)
  // A name that is not UTF-8 decodes to a path naming no file, which would leave its file unchecked yet shipped.
  if (!isUtf8(bytes))
    throw new Error(
      "git ls-files lists a path that is not valid UTF-8; rename it in UTF-8, then rerun",
    )
  const listed = new TextDecoder().decode(bytes)
  const tree = new Map<string, Uint8Array | "symlink">()
  for (const path of new Set(listed.split("\0").filter(Boolean))) {
    const entry = await readEntry(root, path)
    if (entry !== undefined) tree.set(path, entry)
  }
  return tree
}

if (import.meta.main) {
  const args = process.argv.slice(2)
  if (args.length > 1 || (args.length === 1 && args[0] !== "--help")) {
    console.error(usage("check", "[--help]"))
    process.exitCode = 1
  } else if (args[0] === "--help") {
    const rules = Object.entries(RULES).map(([name, rule]) => `- ${name}: ${rule}`)
    console.log(
      [
        "bun scripts/check.ts holds the repository to these rules, skipping the files Git ignores:",
        ...rules,
      ].join("\n"),
    )
  } else {
    const problems = await check(await readTree(join(import.meta.dirname, "..")))
    for (const problem of problems) console.error(problem)
    process.exitCode = problems.length > 0 ? 1 : 0
  }
}
