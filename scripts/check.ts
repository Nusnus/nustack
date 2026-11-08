/**
 * nustack's commit-time check. It reads the files Git tracks, or would track, in the folders the rules cover, prints
 * each break of the rules --help lists with the file, the field and the fix, and exits 1 on any. A problem repeats no
 * value read from a file, apart from a link's target, a path or skill name a record lists, and a workflow's job id.
 */
import { lstat, readdir } from "node:fs/promises"
import { basename, dirname, join, normalize } from "node:path"
import { isMap, isScalar, isSeq, parseDocument, visit } from "yaml"
import { usage } from "./command.ts"
import { gitBytes } from "./git.ts"
import { type Link, type Markdown, markdown, type Span, section, within } from "./markdown.ts"
import {
  CHANGELOG,
  type Found,
  MANIFEST_KEYS,
  MANIFESTS,
  MARKETPLACES,
  type Manifest,
  PACKAGE,
  PYPROJECT,
  readMetadata,
} from "./metadata.ts"
import { PAGE_STEPS } from "./plugin.ts"
import { blobOf, KEBAB, parseRecord, RECORD_FOLDERS } from "./record.ts"
import {
  cannotOpen,
  decode,
  FileFault,
  folderInPlace,
  isObject,
  neither,
  neitherInFolderPlace,
  once,
  type Problem,
  parseYaml,
  problem,
  readEntry,
  rethrowUnlessMissing,
  symlinkProblem,
  TOO_DEEP,
  type Tree,
  UnreadableEntry,
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

// The hooks that rewrite the files they check, each of which must leave a vendored copy byte for byte.
const REWRITING_HOOKS = Object.freeze([
  "end-of-file-fixer",
  "fix-byte-order-marker",
  "mixed-line-ending",
  "trailing-whitespace",
  "markdownlint-cli2",
])
const RULES = Object.freeze({
  metadata:
    "the host manifests agree and each holds only a kebab-case name, a <major>.<minor>.<patch> version, a description, an author with only a name, an https homepage of at most 2083 characters, an https://<host>/<owner>/<name> repository and a license; pyproject.toml holds their version; plugin/package.json holds only their name and version, type module and exports naming the loader; each marketplace holds only a kebab-case name, the owner, the plugin and a filled-in description, lists only the plugin, with the manifests' name and description and its host's source, names the manifests' author as owner, and shares one name and description with the other; commitizen's version_files lists each file holding their version, and its tag_format is v$version; CHANGELOG.md's latest release, the first ## heading that links a version by its label, is their version, each ## heading that names a version in brackets defines its label, the releases titled with a version and a day run newest first, by version and by date, and the latest release's entry, which the release page copies, links by full URLs, defines each reference it uses and shows something in each ### group; the release workflow runs on the v* tags that tag_format gives",
  workflows:
    "the release workflow sets jobs.ci.needs: tag and jobs.publish.needs: ci, the CI workflow sets jobs.release-zip.needs: make-check, and each job of each workflow in .github/workflows installs bun.lock before it runs a script",
  layout:
    "plugin/ holds opencode.ts, and only the host manifests, each skill's SKILL.md, the mode's playbooks, the OpenCode loader with its package.json, the vendored copies and a LICENSE equal to the repository's, which exists, and no symlink; tests/unit/ and tests/integration/ hold only *.test.ts files",
  skills: `each skill folder is named in kebab case and holds a SKILL.md whose name is the folder's and whose description is filled in, with a name of at most ${NAME_CAP} characters and a description of at most ${DESCRIPTION_CAP}; an authored one keeps each field and list entry to one line, with no --- in a value and no field repeated, and holds in its frontmatter only field and list entry lines, no control character YAML cannot read, no NEL or Unicode line or paragraph separator, no | or > block value, no tab outside quotes, no tag outside YAML's core schema or on a value it cannot build, no alias, no reused anchor and no key that is not text, holds no field but ${AUTHORED_KEYS.join(", ")}, sets disable-model-invocation: true and triggers: [user] in a principle- or language- skill and neither in the mode, and stays under ${MAX_LINES} lines`,
  mode: `plugin/skills/ holds exactly one mode, ${MODE}, whose body stays within ${MODE_CAP} characters, and links each playbook under ## ${INDEX.playbook}, each principle under ## ${INDEX.principle} and each language skill under ## ${INDEX.language}`,
  links:
    "each link, image, autolink or link definition GitHub renders in an authored file under plugin/, so none in code, frontmatter or HTML, whether a tag such as <a href> or a comment, is an https, http or mailto URL, an anchor, or a file under plugin/",
  readme: `each step of README.md the release page copies, ${PAGE_STEPS.join(" and ")}, links only by https URL and defines each reference label it uses within itself, and its skills tables give each skill folder under plugin/skills/ one row, which links that skill alone`,
  vendored:
    "vendored/ holds only records named <copy>.json in kebab case, each copying from a repository other than the manifests', each of a record's shape, giving each skill its SKILL.md and LICENSE once it lists files, and each skill folder a record names holds exactly the files it lists, at the Git blobs it lists",
  copies: `each skill folder a record names is named by no other record, and has its own line unsetting text in .gitattributes, where those lines, sorted, end the file and no other line unsets text, and its place in the hooks' &copy exclude, which names no other folder and which ${REWRITING_HOOKS.join(", ")}, each present and each rewriting files, take as their exclude, an exclude needed once a record exists; each skill folder under .agents/skills/ holding a LICENSE is a record's`,
  endings: ".gitattributes sets plugin/** text eol=lf",
} as const)

// The kinds of skill nustack writes besides its mode, each named by its prefix.
const SKILL_KINDS = Object.freeze(["principle", "language"] as const)
// The plugin's own files besides the host manifests, which MANIFESTS lists.
const PLUGIN_FILE = new RegExp(
  String.raw`^plugin/(?:LICENSE|opencode\.ts|package\.json|skills/[a-z0-9-]+/SKILL\.md|skills/(?!${SKILL_KINDS.map((kind) => `${kind}-`).join("|")})[a-z0-9-]+/playbooks/[a-z0-9-]+\.md)$`,
)
const READ_FOLDERS = Object.freeze([
  "plugin",
  "vendored",
  ".agents",
  ".github/workflows",
  "tests/unit",
  "tests/integration",
])
const READ = Object.freeze([
  ...READ_FOLDERS,
  ".gitattributes",
  ".pre-commit-config.yaml",
  "LICENSE",
  PYPROJECT,
  "README.md",
  CHANGELOG,
  ...MARKETPLACES.map(({ path }) => path),
])
// An https URL, its scheme in any case, as URLs take it: https://url.spec.whatwg.org/#scheme-state
const HTTPS = /^https:\/\//i
// A skills-table row's link to a skill, whose folder it captures.
const SKILL_LINK = /^(plugin\/skills\/[^/]+)\/SKILL\.md$/
// The loader's messages offer reinstalling the plugin as a second fix, which only a plugin user needs.
const LOADER_FIX = /, or reinstall the nustack plugin$/
// [^\r] in place of ., which stops at U+2028 and U+2029, so the separators get their own problem.
const FIELD = /^([A-Za-z][\w-]*):(?: ([^\r]*))?$/
const BLOCK = "opens a | or > block value; write the value on its own line"
// Quoted text, whose characters are text, not YAML's syntax.
const QUOTED = /"(?:[^"\\]|\\.)*"|'(?:[^']|'')*'/g
// What each tag of YAML's core schema builds: https://yaml.org/spec/1.2.2/#103-core-schema
const CORE_TAGS: Readonly<Record<string, (node: unknown) => boolean>> = Object.freeze({
  "tag:yaml.org,2002:str": (node) => isScalar(node) && typeof node.value === "string",
  "tag:yaml.org,2002:null": (node) => isScalar(node) && node.value === null,
  "tag:yaml.org,2002:bool": (node) => isScalar(node) && typeof node.value === "boolean",
  "tag:yaml.org,2002:int": (node) => isScalar(node) && Number.isInteger(node.value),
  // yaml leaves a float written as an integer, such as 1, a string, so its text is read by the core schema's pattern.
  "tag:yaml.org,2002:float": (node) =>
    isScalar(node) &&
    (typeof node.value === "number" ||
      /^(?:[-+]?(?:\.\d+|\d+(?:\.\d*)?)(?:[eE][-+]?\d+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$/.test(
        String(node.value),
      )),
  "tag:yaml.org,2002:seq": isSeq,
  "tag:yaml.org,2002:map": isMap,
})

const CHECKS: Record<keyof typeof RULES, (tree: Tree) => Problem[]> = Object.freeze({
  metadata: metadataProblems,
  workflows: workflowProblems,
  layout: layoutProblems,
  skills: (tree) =>
    loader === undefined ? [] : skillFolders(tree).flatMap((folder) => skillProblems(tree, folder)),
  mode: modeProblems,
  links: linkProblems,
  readme: readmeProblems,
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

function metadataProblems(tree: Tree): Problem[] {
  const {
    manifests,
    marketplaces,
    pkg,
    pyproject,
    changelog,
    problems: parsed,
  } = readMetadata(tree)
  const problems = [...parsed]
  // Each field's reference is the first manifest whose field parsed, so a broken field leaves the others compared.
  const manifest: { -readonly [K in keyof Manifest]?: Found<Manifest>[K] } = {}
  const reference: { [K in keyof Manifest]?: string } = {}
  for (const { path, found } of manifests) {
    const differing = new Map<string, string[]>()
    const compare = <K extends keyof Manifest>(field: K) => {
      const value = found[field]
      const from = reference[field]
      if (value === undefined) return
      if (from === undefined) {
        manifest[field] = value
        reference[field] = path
      } else if (!Bun.deepEquals(value, manifest[field]))
        differing.set(from, [...(differing.get(from) ?? []), field])
    }
    for (const field of MANIFEST_KEYS) compare(field)
    for (const [from, fields] of differing)
      problems.push(
        problem(`${path}: ${fields.join(", ")} differs from ${from}; make every manifest the same`),
      )
  }
  const { name, version, description, author } = manifest
  if (clash(pyproject.version, version))
    problems.push(
      problem(`${PYPROJECT}: [project] version is not the manifests'; set it to theirs`),
    )
  if (clash(pkg.name, name) || clash(pkg.version, version))
    problems.push(problem(`${PACKAGE}: name or version is not the manifests'; set both`))
  if (changelog !== undefined && version !== undefined && changelog.latest !== version)
    problems.push(
      problem(
        `${CHANGELOG}: its latest release is not the manifests' version; title that release, or set the version to it`,
      ),
    )
  for (const { path, found } of marketplaces) {
    if (clash(found.plugin?.name, name) || clash(found.plugin?.description, description))
      problems.push(
        problem(
          `${path}: the plugin's name or description is not the manifests'; set both to theirs`,
        ),
      )
    if (clash(found.owner?.name, author?.name))
      problems.push(problem(`${path}: owner differs from the manifests' author; set it to theirs`))
  }
  const [claude, cursor] = marketplaces.map(({ found }) => found)
  if (clash(claude?.name, cursor?.name) || clash(claude?.description, cursor?.description))
    problems.push(
      problem(`${MARKETPLACES[1].path}: name or description differs from the other's; match it`),
    )
  return problems
}

// Two parsed fields clash when both parsed and differ; a field that did not parse has its own problem.
function clash(field: string | undefined, other: string | undefined): boolean {
  return field !== undefined && other !== undefined && field !== other
}

function layoutProblems(tree: Tree): Problem[] {
  const problems = under(tree, "plugin/").flatMap((path) => {
    if (tree.get(path) === "symlink") return [symlinkProblem(path)]
    if (MANIFESTS.includes(path) || PLUGIN_FILE.test(path) || inCopy(tree, path)) return []
    return [problem(`${path}: is not a file the plugin installs; move it out of plugin/`)]
  })
  if (!tree.has("plugin/opencode.ts")) problems.push(MISSING_LOADER)
  for (const path of [...under(tree, "tests/unit/"), ...under(tree, "tests/integration/")])
    if (!path.endsWith(".test.ts"))
      problems.push(
        problem(
          `${path}: is no test, so it does not belong in a tier folder; move it to tests/fixtures/`,
        ),
      )
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

// The release page copies README's PAGE_STEPS, where a relative link, or a label README defines outside its step, breaks.
function readmeProblems(tree: Tree): Problem[] {
  const read = decode(tree, "README.md", markdown)
  if (!Array.isArray(read)) return [read.problem]
  const readme = read[0]
  return [...pageStepProblems(readme), ...skillRowProblems(tree, readme)]
}

// Each step is the section the release page copies. A label resolves on that page only where the step defines it, so
// each link or image the step renders by a label, and each footnote it calls, has a definition of its label inside the
// step.
function pageStepProblems(readme: Markdown): Problem[] {
  return PAGE_STEPS.flatMap((heading) => {
    const step = section(readme, heading)
    if (step === undefined) return [problem(`README.md: has no ${heading} heading; add it`)]
    const problems = written(readme)
      .filter((link) => within(link, step) && !HTTPS.test(link.destination))
      .map(({ destination }) =>
        problem(
          `README.md: ${heading} links ${destination}; link it by https URL, since the release page copies it`,
        ),
      )
    // README renders a label from its first definition, the release page from the first inside the step.
    const outside = [
      ...readme.links.flatMap(({ definition, ...link }) =>
        definition && within(link, step) ? [{ definition, key: definition.identifier }] : [],
      ),
      ...readme.footnotes.flatMap(({ definition, ...note }) =>
        within(note, step) ? [{ definition, key: `^${definition.identifier}` }] : [],
      ),
    ].filter(({ definition }) => !within(definition, step))
    const inside = new Set([
      ...readme.definitions.flatMap((definition) =>
        within(definition, step) ? [definition.identifier] : [],
      ),
      ...readme.notes.flatMap((note) => (within(note, step) ? [`^${note.identifier}`] : [])),
    ])
    if (outside.some(({ key }) => !inside.has(key)))
      problems.push(
        problem(
          `README.md: ${heading} uses a reference label it does not define; define it in that step`,
        ),
      )
    if (outside.some(({ key }) => inside.has(key)))
      problems.push(
        problem(
          `README.md: ${heading} uses a reference label defined outside that step too, so README and the release page link different targets; define it only inside the step`,
        ),
      )
    return problems
  })
}

// A skills-table row opens with the link to its skill's SKILL.md.
function skillRowProblems(tree: Tree, readme: Markdown): Problem[] {
  const rows = readme.rows.filter(([first]) => first?.[0]?.destination.startsWith("plugin/skills/"))
  const linked = rows.map((row) =>
    row.flat().flatMap(({ destination }) => SKILL_LINK.exec(destination)?.[1] ?? []),
  )
  const folders = skillFolders(tree)
  const problems: Problem[] = []
  if (linked.some((row) => row.length !== 1))
    problems.push(
      problem(
        "README.md: a skills-table row links other than one SKILL.md; link its skill's alone",
      ),
    )
  if (linked.flat().some((folder) => !folders.includes(folder ?? "")))
    problems.push(
      problem(
        "README.md: a skills-table row links a skill plugin/skills/ does not hold; drop that row",
      ),
    )
  for (const folder of folders) {
    const count = linked.filter((row) => row.includes(folder)).length
    if (count === 0)
      problems.push(problem(`README.md: no skills-table row links ${folder}; add one`))
    if (count > 1)
      problems.push(problem(`README.md: more than one skills-table row links ${folder}; keep one`))
  }
  return problems
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
  // GitHub matches a repository's owner and name in any case, and serves its www. host as the bare one.
  const repositoryKey = (url: string) => url.toLowerCase().replace("https://www.", "https://")
  const fromHere = readMetadata(tree).manifests.some(
    ({ found }) =>
      found.repository !== undefined &&
      repositoryKey(found.repository) === repositoryKey(record.upstream),
  )
  const authored = record.skills.filter(
    (skill) => skill === MODE || SKILL_KINDS.some((kind) => skill.startsWith(`${kind}-`)),
  )
  return [
    ...authored.map((skill) =>
      problem(
        `${path}: lists ${skill}, a name only nustack's own skills hold; drop it from skills`,
      ),
    ),
    ...(fromHere
      ? [
          problem(
            `${path}: upstream is this repository, whose skills are authored here; copy from another`,
          ),
        ]
      : []),
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

// Each folder and skill a copy's three guards name: its record, its .gitattributes line and its place in the hooks'
// &copy exclude. A problem repeats a folder only from a record the schema accepts, as AGENTS.md › Harness code says.
function copyProblems(tree: Tree): Problem[] {
  const listed = under(tree, "vendored/").flatMap((path) => {
    const record = parseRecord(path, tree.get(path))
    return Array.isArray(record) ? [] : record.skills.map((skill) => `${record.folder}/${skill}`)
  })
  const known = vendoredFolders(tree)
  const problems = listed
    .filter((folder, index) => listed.indexOf(folder) !== index)
    .map((folder) =>
      problem(`${folder}: is named by more than one record in vendored/; keep it in one`),
    )
  const attributes = decode(tree, ".gitattributes", (text) => text)
  if (Array.isArray(attributes)) {
    const unset = [...String(attributes[0]).matchAll(/^(\S+)\/\*\* -text$/gm)].map(
      ([, folder]) => folder,
    )
    for (const folder of listed.filter((folder) => !unset.includes(folder)))
      problems.push(
        problem(
          `.gitattributes: does not unset text for ${folder}; add the line ${folder}/** -text`,
        ),
      )
    if (unset.some((folder) => !known.includes(folder ?? "")))
      problems.push(
        problem(
          ".gitattributes: unsets text for a folder no record in vendored/ names; drop that line",
        ),
      )
    const UNSET = /^\S+\/\*\* -text$/
    const lines = attributeLines(String(attributes[0]))
    const first = lines.findIndex((line) => UNSET.test(line))
    if (first !== -1 && lines.slice(first).some((line) => !UNSET.test(line)))
      problems.push(
        problem(
          ".gitattributes: sets attributes after a line unsetting text, which can set text on a copy again; end the file with the lines unsetting text",
        ),
      )
    if (lines.some((line) => /\s-text(?:\s|$)/.test(line) && !UNSET.test(line)))
      problems.push(
        problem(
          ".gitattributes: unsets text on a path that is no copy's folder; drop -text from that line",
        ),
      )
    const copies = lines.filter((line) => UNSET.test(line))
    if (copies.some((line, index) => index > 0 && line < (copies[index - 1] ?? "")))
      problems.push(problem(".gitattributes: its lines unsetting text are out of order; sort them"))
  } else problems.push(attributes.problem)
  const hooks = decode(tree, ".pre-commit-config.yaml", (text) => text)
  if (Array.isArray(hooks)) {
    const alternatives = /^ *exclude: &copy \^\(\?:(.*)\)\/$/m.exec(String(hooks[0]))?.[1]
    const excluded = alternatives?.split("|").map((folder) => folder.replaceAll("\\", "")) ?? []
    if (alternatives === undefined && listed.length > 0)
      problems.push(
        problem(
          ".pre-commit-config.yaml: has no exclude: &copy ^(?:<folder>|...)/ naming the copies; add it",
        ),
      )
    for (const folder of listed.filter((folder) => !excluded.includes(folder)))
      problems.push(
        problem(`.pre-commit-config.yaml: its &copy exclude does not name ${folder}; add it`),
      )
    if (excluded.some((folder) => !known.includes(folder)))
      problems.push(
        problem(
          ".pre-commit-config.yaml: its &copy exclude names a folder no record in vendored/ names; drop it",
        ),
      )
    const config = decode(tree, ".pre-commit-config.yaml", parseYaml)
    if (!Array.isArray(config)) problems.push(config.problem)
    else if (alternatives !== undefined) {
      const repos = [isObject(config[0]) ? (config[0].repos ?? []) : []].flat()
      const declared = repos
        .flatMap((repo) => (isObject(repo) ? [repo.hooks ?? []].flat() : []))
        .filter(isObject)
      for (const id of REWRITING_HOOKS)
        if (!declared.some((hook) => hook.id === id))
          problems.push(problem(`.pre-commit-config.yaml: has no ${id} hook; restore it`))
        else if (
          declared.some((hook) => hook.id === id && hook.exclude !== `^(?:${alternatives})/`)
        )
          problems.push(
            problem(
              `.pre-commit-config.yaml: ${id} does not exclude the copies; give it exclude: *copy`,
            ),
          )
    }
  } else problems.push(hooks.problem)
  for (const path of under(tree, ".agents/skills/"))
    if (/^\.agents\/skills\/[^/]+\/LICENSE$/.test(path) && !known.includes(dirname(path)))
      problems.push(
        problem(
          `${path}: sits in a skill folder no record in vendored/ names; write its record, or remove the copy`,
        ),
      )
  return problems
}

// .gitattributes holds the line plugin/** text eol=lf, whose own comment says what it guards. The copies rule keeps
// it above the lines unsetting text.
function endingProblems(tree: Tree): Problem[] {
  const attributes = decode(tree, ".gitattributes", (text) => text)
  if (
    !Array.isArray(attributes) ||
    attributeLines(String(attributes[0])).includes("plugin/** text eol=lf")
  )
    return []
  return [
    problem(
      ".gitattributes: does not set plugin/** text eol=lf; add that line above the lines that unset text",
    ),
  ]
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

// Some hosts drop every field once one spans lines or holds ---, as AGENTS.md › Writing skill text says, and a YAML
// mapping holds each key once: https://yaml.org/spec/1.2.2/#mapping. A host that reads frontmatter line by line, not as
// YAML, reads a line only as a field or a list entry, so every other line, a blank one included, reads differently there.
function frontmatterProblems(path: string, text: string): Problem[] {
  const block = loader?.SkillFile.FRONTMATTER.exec(text)?.[1] ?? ""
  const lines = block.split(/\r?\n/).slice(0, -1)
  const keys = lines.flatMap((line) => FIELD.exec(line)?.[1] ?? [])
  const reasons = new Set<string>()
  // Of the control characters, YAML reads only a tab, LF, CR and NEL: https://yaml.org/spec/1.2.2/#51-character-set
  if (/(?![\t\n\r\x85])\p{Cc}/u.test(block))
    reasons.add("holds a control character YAML cannot read; delete it")
  // YAML 1.1 reads NEL, U+2028 and U+2029 as line breaks, YAML 1.2 as text, and most editors hide them.
  if (/[\x85\u2028\u2029]/.test(block))
    reasons.add(
      "holds a NEL, a Unicode line separator or a paragraph separator, which hosts read differently and most editors hide; delete it",
    )
  const nodes = nodeProblems(block)
  let open = false
  for (const [at, line] of lines.entries()) {
    const field = FIELD.exec(line)
    const entry = /^ *- ([^\r]*\S[^\r]*)$/.exec(line)
    if (/^\s*$/.test(line)) reasons.add("holds a blank line; delete it")
    else if (entry !== null && open)
      reasons.add("a field or list entry spans lines; keep each to one line")
    else if (field === null && entry === null)
      reasons.add(
        /^\s/.test(line)
          ? "a field or list entry spans lines; keep each to one line"
          : "has a line that is neither a field, a key that starts with a letter, a colon and a space before any value, nor a list entry, a dash and a space before its value; rewrite or delete it",
      )
    const value = field?.[2] ?? entry?.[1]
    // A value of only a tag or an anchor opens a node on the lines under it.
    open = field !== null && value !== undefined && !/^(?:[!&]\S*\s*)+$/.test(value)
    const found = nodes.get(at) ?? []
    // A | or > block takes the lines under it, so its line gives that problem alone.
    if (found.includes(BLOCK)) reasons.add(BLOCK)
    else {
      if (value?.replace(QUOTED, '""').includes("\t"))
        reasons.add("holds a tab outside quotes; replace it with a space, or quote the value")
      for (const reason of found) reasons.add(reason)
    }
  }
  if (lines.some((line) => line.includes("---"))) reasons.add("a value holds ---; reword it")
  if (new Set(keys).size < keys.length) reasons.add("repeats a field; keep one")
  return [...reasons].map((reason) => problem(`${path}: ${reason}`))
}

// The problems of each node a host may read differently, by the line it opens on: a | or > block, an alias, an anchor's
// name used twice, a tag outside YAML's core schema or one its value cannot build, and a key that is not text.
function nodeProblems(block: string): Map<number, string[]> {
  const found = new Map<number, string[]>()
  const add = (range: readonly number[] | null | undefined, reason: string) => {
    const line = block.slice(0, range?.[0]).split("\n").length - 1
    found.set(line, [...(found.get(line) ?? []), reason])
  }
  const anchors = new Set<string>()
  visit(parseDocument(block), {
    Alias: (_, alias) =>
      add(
        alias.range,
        "uses an alias, which a host that reads frontmatter line by line takes as text; write the value out",
      ),
    Pair: (_, pair) => {
      if (isMap(pair.key) || isSeq(pair.key))
        add(pair.key.range, "has a key that is not text; write the key as text")
    },
    Node: (_, node) => {
      if (isScalar(node) && (node.type === "BLOCK_LITERAL" || node.type === "BLOCK_FOLDED"))
        add(node.range, BLOCK)
      if (node.anchor !== undefined) {
        if (anchors.has(node.anchor))
          add(node.range, "reuses an anchor's name; give each anchor its own")
        anchors.add(node.anchor)
      }
      if (node.tag === undefined) return
      const builds = CORE_TAGS[node.tag]
      if (builds === undefined) add(node.range, "uses a tag outside YAML's core schema; drop it")
      else if (!builds(node))
        add(node.range, "tags a value its tag cannot build; fix the value, or drop the tag")
    },
  })
  return found
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
      // The loader refuses frontmatter too long to parse safely before it counts levels, and yaml parses any length
      // without crashing, so the check names frontmatter nested too deep however long it is.
      if (frontmatterTooDeep(file.text)) return problem(`${path}: has frontmatter that ${TOO_DEEP}`)
      const [frontmatter] = file.split()
      return { file, frontmatter }
    } catch (error) {
      return loaderProblem(error, path)
    }
  })
}

function frontmatterTooDeep(text: string): boolean {
  try {
    parseYaml(loader?.SkillFile.FRONTMATTER.exec(text)?.[1] ?? "")
  } catch (error) {
    return error instanceof FileFault && error.message === TOO_DEEP
  }
  return false
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

export async function readTree(root: string): Promise<Tree> {
  const plugin = await lstat(join(root, "plugin")).catch(rethrowUnlessMissing)
  if (plugin !== undefined && !plugin.isDirectory())
    throw new UnreadableEntry(
      "plugin: is not a folder, so the check stops here; replace it with the plugin folder",
    )
  const bytes = Buffer.from(
    await gitBytes(["ls-files", "-z", "-co", "--exclude-standard", "--", ...READ], root),
  )
  const listed = bytes.toString("utf8")
  // A name that is not UTF-8 decodes to one that names no file, so it would drop out of the tree unread.
  if (!Buffer.from(listed, "utf8").equals(bytes)) {
    const unreadable = listed.split("\0").filter((path) => path.includes("\uFFFD"))
    throw new UnreadableEntry(`${unreadable.join(", ")}: its name is not UTF-8; rename it`)
  }
  const ignored = Buffer.from(
    await gitBytes(
      ["ls-files", "-z", "-oi", "--exclude-standard", "--directory", "--", ...READ],
      root,
    ),
  )
  const paths = listed.split("\0").filter(Boolean)
  for (const folder of READ_FOLDERS)
    await refuseSpecial(root, folder, new Set(ignored.toString("utf8").split("\0")), paths)
  const tree = new Map<string, Uint8Array | "symlink">()
  for (const path of new Set(paths)) {
    const entry = await readEntry(root, path)
    if (entry !== undefined) tree.set(path, entry)
  }
  return tree
}

// Git lists no fifo, socket or device, so the walk finds one where Git would track it, skipping the folders Git ignores.
async function refuseSpecial(
  root: string,
  path: string,
  ignored: ReadonlySet<string>,
  listed: readonly string[],
) {
  const entries = await readdir(join(root, path), { withFileTypes: true }).catch(
    async (error: unknown) => {
      const code = isObject(error) ? error.code : undefined
      if (code === "EACCES") throw new UnreadableEntry(cannotOpen(path))
      if (code === "ENOTDIR") throw new UnreadableEntry(await folderInPlace(root, `${path}/`))
      if (code === "ENOENT") return []
      throw error
    },
  )
  for (const entry of entries) {
    const inner = `${path}/${entry.name}`
    if (ignored.has(`${inner}/`)) continue
    if (entry.isDirectory()) await refuseSpecial(root, inner, ignored, listed)
    else if (entry.isFile() || entry.isSymbolicLink()) continue
    else if (listed.some((listedPath) => listedPath.startsWith(`${inner}/`)))
      throw new UnreadableEntry(neitherInFolderPlace(inner))
    else throw new UnreadableEntry(neither(inner))
  }
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
    const tree = await readTree(join(import.meta.dirname, "..")).catch((error: unknown) => {
      if (!(error instanceof UnreadableEntry)) throw error
      console.error(error.message)
    })
    const problems = tree === undefined ? [] : await check(tree)
    for (const problem of problems) console.error(problem)
    process.exitCode = tree === undefined || problems.length > 0 ? 1 : 0
  }
}
