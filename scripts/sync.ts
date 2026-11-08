/**
 * The vendored copies' sync. `list` prints each record in vendored/ with its pull request's branch, for the sync
 * workflow's matrix; `sync <record> <body-file>` copies the record's skills from upstream's default branch, rewrites
 * the record's commit and files, and writes the pull request's body from the PR template's layout, listing each file
 * the copy changes, adds or drops and each skill upstream holds that the record does not list. It compares upstream with
 * the copy the checkout holds, so it also restores a copy edited by hand since the last sync. `proposed <record> <branch>
 * <base> <body-file>` writes proposed=true to $GITHUB_OUTPUT when an open pull request from the copy's branch into the base comes from
 * this repository and that branch already proposes the copy on the base's head, so the workflow leaves that pull request,
 * with the commits a reviewer added, as it is; it gives the pull request the body the sync wrote only where the two
 * differ beyond the run that wrote them, so a reviewer sees an edit only when the copy's description changes.
 */
import { appendFile, mkdir, mkdtemp, readFile, rename, rm, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { basename, dirname, join } from "node:path"
import { asksForUsage, runMain, usage } from "./command.ts"
import { type Gh, ghOutput, runGh } from "./gh.ts"
import { GitError, type GitOptions, git, gitBytes } from "./git.ts"
import { type Markdown, markdown, within } from "./markdown.ts"
import {
  type CopyRecord,
  FILE_PATH,
  KEBAB,
  OBJECT_ID,
  parseRecord,
  recordText,
  SHA,
} from "./record.ts"
import { readEntry, rethrowUnlessMissing } from "./tree.ts"

// The most characters GitHub takes in a pull request's body.
const BODY_LIMIT = 65_536
// Upstream's default branch over HTTPS, with no checkout, since the sync reads only Git's objects, and no blob until
// the sync reads it. The history stays, since the record's commit is the newest commit on upstream's first-parent
// line to touch the copied files, so a branch merged into it records the merge, not the branch's own commit.
const CLONE = Object.freeze(["clone", "--filter=blob:none", "--no-checkout"])
const COMMANDS = Object.freeze(["list", "sync", "proposed"] as const)
const USAGE = usage(
  "sync",
  "list | sync <record> <body-file> | proposed <record> <branch> <base> <body-file>",
)

export type Change = Readonly<Record<"changed" | "added" | "removed", readonly string[]>>

/** The pages a reviewer checks the sync against: the run that wrote it, and upstream's commits since the last sync. */
export type Links = Readonly<{ run?: string; compare?: string }>

/** What a sync proposes, for its pull request's body; `recordChanges` says whether the record changes too. */
export type Proposal = Readonly<{
  path: string
  copy: CopyRecord
  changes: Change
  unlisted: readonly string[]
  recordChanges: boolean
  links: Links
}>

/** The pull request's body, or the notice of a run that proposes nothing. */
export type Outcome = Readonly<{ body: string; proposes: boolean }>

export const TEMPLATE = ".github/pull_request_template.md"
// A placeholder in the template is an HTML comment naming what fills it, such as <!-- Changes -->.
const PLACEHOLDER = /<!-- (.+?) -->/
// The Checks bullet that links the sync run that wrote a body, which each run changes.
const RUN = "- The sync run that wrote it: "
const RUN_LINK = new RegExp(`^(${RUN})\\S*`, "m")

// The parts of the PR template, in its order; body() fills each that a sync has.
const PARTS = Object.freeze([
  "What changed",
  "Risk",
  "Review first",
  "After merge",
  "Checks",
  "Files",
  "Decisions",
] as const)

// Each placeholder of the PR template that body() fills.
const PLACEHOLDERS = Object.freeze([
  "Headline",
  "What the change does for its reader",
  "Badges",
  "issue",
  "Changes",
  "Risk",
  "Review",
  "step",
  "Fold summary",
  "Checks",
  "Files",
  "Decisions",
] as const)
type Placeholder = (typeof PLACEHOLDERS)[number]

// A copy in plugin/ changes what users install, so its sync is a feature; any other copy only documents nustack.
const TYPES: Readonly<Record<CopyRecord["folder"], "feat" | "docs">> = Object.freeze({
  ".agents/skills": "docs",
  "plugin/skills": "feat",
})

type Entry = Readonly<{ mode: string; blob: string; file: string }>
// An entry of `git ls-tree -z` and of `git ls-files --stage -z`, which gives the blob's merge stage after it.
const TREE_ENTRY = new RegExp(`^(?<mode>\\d{6}) blob (?<blob>${OBJECT_ID})\t(?<file>.+)$`, "s")
const INDEX_ENTRY = new RegExp(`^(?<mode>\\d{6}) (?<blob>${OBJECT_ID}) \\d\t(?<file>.+)$`, "s")

function isPlaceholder(name: string): name is Placeholder {
  return (PLACEHOLDERS as readonly string[]).includes(name)
}

export async function run(
  root: string,
  args: readonly string[],
  clone = cloneUpstream,
  gh: Gh = runGh,
): Promise<string> {
  if (asksForUsage(args, COMMANDS)) return USAGE
  const [given, path, out, ...rest] = args
  const command = COMMANDS.find((name) => name === given)
  if (!command) throw new Error(USAGE)
  switch (command) {
    case "list":
      if (path !== undefined) throw new Error(USAGE)
      return list(root)
    case "sync":
      if (path === undefined || out === undefined || rest.length > 0) throw new Error(USAGE)
      {
        const { body, proposes } = await sync(root, path, clone)
        await writeFile(out, body)
        // A run that proposes nothing opens no pull request, so its notice goes to the log.
        return proposes ? `Wrote ${out}` : `Wrote ${out}\n${body.trimEnd()}`
      }
    case "proposed": {
      const [base, bodyFile, ...extra] = rest
      if (
        path === undefined ||
        out === undefined ||
        base === undefined ||
        bodyFile === undefined ||
        extra.length > 0
      )
        throw new Error(USAGE)
      const output = process.env.GITHUB_OUTPUT
      if (!output) throw new Error("GITHUB_OUTPUT is unset; run proposed in a GitHub Actions step")
      const kept = await proposed(root, path, out, base, gh)
      if (kept.length === 0)
        return `no open pull request from origin/${out} proposes this copy on the base's head; the workflow proposes it`
      const refreshed = []
      for (const number of kept)
        if (await refresh(gh, number, bodyFile)) refreshed.push(`#${number}`)
      await appendFile(output, "proposed=true\n")
      const edited =
        refreshed.length === 0
          ? "its description already says what the sync wrote"
          : `the sync's description replaces ${refreshed.join(", ")}'s`
      return `the open pull request from origin/${out} already proposes this copy on the base's head; it keeps its commits, and ${edited}`
    }
  }
}

export async function list(root: string): Promise<string> {
  const listed = await git(["ls-files", "-z", "--", "vendored/*.json"], root)
  const copies = []
  for (const record of listed.split("\0").filter(Boolean)) {
    const copy = await readRecord(root, record)
    const title = `${TYPES[copy.folder]}: sync ${record} from ${copy.upstream}`
    copies.push({ record, branch: `sync/${basename(record, ".json")}`, title })
  }
  if (copies.length === 0)
    throw new Error(
      "vendored/: holds no record to sync; add one, as AGENTS.md › Where things live says",
    )
  return JSON.stringify(copies)
}

async function ghPulls(
  gh: Gh,
  args: readonly string[],
): Promise<readonly { isCrossRepository: boolean; number: number }[]> {
  const noList = new Error(
    `gh ${args.join(" ")} printed no list of pull requests; update gh, then rerun`,
  )
  const output = await ghOutput(gh, args)
  let pulls: unknown
  try {
    pulls = JSON.parse(output)
  } catch {
    throw noList
  }
  if (
    !Array.isArray(pulls) ||
    !pulls.every(
      (pull) => typeof pull?.isCrossRepository === "boolean" && Number.isInteger(pull?.number),
    )
  )
    throw noList
  return pulls
}

// create-pull-request resets the branch to its own commit whenever the two differ, which drops a reviewer's commits, such
// as the changelog entry, so the branch stays while upstream and the base hold where it proposed them: the base's head is
// in its history and it holds the copy and record the sync just wrote. It gives the number of each open pull request
// from this repository's branch that it keeps, or none when the workflow proposes the copy afresh.
export async function proposed(
  root: string,
  path: string,
  branch: string,
  base: string,
  gh: Gh = runGh,
): Promise<readonly number[]> {
  const copy = await readRecord(root, path)
  const proposing = `refs/remotes/origin/${branch}`
  const holds = (args: string[]) =>
    git(args, root).then(
      () => true,
      (error) => {
        if (error instanceof GitError && error.code === 1) return false
        throw error
      },
    )
  if (!(await holds(["rev-parse", "--verify", "--quiet", proposing]))) return []
  // A pull request the owner closed unmerged leaves its branch behind, and only a new pull request proposes the copy then.
  // gh's --head takes a branch name alone, so it also lists a fork's pull request from a branch of that name.
  const open = [
    "pr",
    "list",
    "--head",
    branch,
    "--base",
    base,
    "--state",
    "open",
    "--json",
    "isCrossRepository,number",
  ]
  const kept = (await ghPulls(gh, open))
    .filter((pull) => !pull.isCrossRepository)
    .map((pull) => pull.number)
  if (kept.length === 0) return []
  if (!(await holds(["merge-base", "--is-ancestor", "HEAD", proposing]))) return []
  const folders = copy.skills.map((skill) => `${copy.folder}/${skill}`)
  // Staged, since git diff passes over a file the copy adds while it is untracked.
  await git(["add", "--all", "--", path, ...folders], root)
  return (await holds(["diff", "--quiet", proposing, "--", path, ...folders])) ? kept : []
}

// A kept pull request takes the body the sync wrote only where the two differ beyond the run that wrote them, as main's
// sync did, so each run's new run link alone edits no description. It says whether it edited the body.
export async function refresh(gh: Gh, number: number, bodyFile: string): Promise<boolean> {
  const view = ["pr", "view", String(number), "--json", "body"]
  const output = await ghOutput(gh, view)
  let current: unknown
  try {
    current = JSON.parse(output)?.body
  } catch {}
  if (typeof current !== "string")
    throw new Error(`gh ${view.join(" ")} printed no pull request body; update gh, then rerun`)
  if (beyondTheRun(current) === beyondTheRun(await readFile(bodyFile, "utf8"))) return false
  await ghOutput(gh, ["pr", "edit", String(number), "--body-file", bodyFile])
  return true
}

// A body with its run link dropped, and the newlines it ends on, which GitHub may trim from a stored body.
function beyondTheRun(body: string): string {
  return body.replace(RUN_LINK, "$1").replace(/\n+$/, "")
}

async function readRecord(root: string, path: string): Promise<CopyRecord> {
  const copy = parseRecord(path, await readEntry(root, path))
  if (Array.isArray(copy)) throw new Error(copy.join("\n"))
  return copy
}

export async function sync(root: string, path: string, clone = cloneUpstream): Promise<Outcome> {
  const old = await readRecord(root, path)
  const text = await readFile(join(root, TEMPLATE), "utf8").catch(rethrowUnlessMissing)
  if (text === undefined) throw new Error(`${TEMPLATE}: is missing; restore it`)
  const template = checkTemplate(text)
  const upstream = await mkdtemp(join(tmpdir(), "nustack-sync-"))
  try {
    await clone(old.upstream, upstream).catch((error) => {
      throw new Error(
        `${path}: its upstream did not clone; check that it exists and is public, then rerun. ${error.message}`,
      )
    })
    // TREE_ENTRY reads 40-hex blob names, so a SHA-256 repository would fail later on every entry, naming no fix.
    if (!SHA.test((await git(["rev-parse", "HEAD"], upstream)).trim()))
      throw new Error(
        `${path}: its upstream names its commits by other than SHA-1; nustack syncs SHA-1 repositories only, so point the record at one`,
      )
    const unlisted = await unlistedSkills(upstream, old)
    const files: Record<string, string> = {}
    const executables = new Set<string>()
    const borrowed = new Set<string>()
    for (const skill of old.skills) {
      const from = `${old.source}/${skill}`
      const unlistable = `${from} upstream holds an entry no record can list; review it there`
      const tree = await git(["ls-tree", "-r", "-z", "HEAD", "--", `${from}/`, "LICENSE"], upstream)
      for (const line of tree.split("\0").filter(Boolean)) {
        const entry = entryOf(line, TREE_ENTRY)
        if (entry === undefined || !/^100(644|755)$/.test(entry.mode)) throw new Error(unlistable)
        const isRootLicense = entry.file === "LICENSE"
        if (!isRootLicense && !entry.file.startsWith(`${from}/`)) throw new Error(unlistable)
        const name = `${skill}/${isRootLicense ? "LICENSE" : entry.file.slice(from.length + 1)}`
        if (!FILE_PATH.test(name)) throw new Error(unlistable)
        // A skill with no LICENSE of its own is copied under upstream's root one.
        if (isRootLicense && name in files) continue
        // The entry that wins decides the mode, so a skill's own LICENSE drops the root one's.
        files[name] = entry.blob
        if (isRootLicense) borrowed.add(skill)
        else if (name === `${skill}/LICENSE`) borrowed.delete(skill)
        if (entry.mode === "100755") executables.add(name)
        else executables.delete(name)
      }
      if (!(`${skill}/SKILL.md` in files && `${skill}/LICENSE` in files)) {
        // A skill upstream renamed shows up as one the record does not list.
        const renamed =
          unlisted.length === 0
            ? ""
            : ` Upstream holds ${unlisted.join(", ")}, which the record does not list; it may have renamed ${skill} to one.`
        throw new Error(
          `${old.upstream} holds no ${from}/SKILL.md or no LICENSE; fix ${path}.${renamed}`,
        )
      }
    }
    // An upstream commit that touches none of the copied files leaves the record's commit as it was.
    const paths = [
      ...old.skills.map((skill) => `${old.source}/${skill}/`),
      ...(borrowed.size > 0 ? ["LICENSE"] : []),
    ]
    const log = ["log", "--first-parent", "-1", "--format=%H", "HEAD", "--", ...paths]
    const commit = (await git(log, upstream)).trim()
    const sorted = Object.fromEntries(Object.entries(files).sort(([a], [b]) => (a < b ? -1 : 1)))
    const modes = Object.fromEntries(
      Object.entries(sorted).map(([name, blob]) => [
        name,
        `${executables.has(name) ? "100755" : "100644"} ${blob}`,
      ]),
    )
    const changes = change(await checkedIn(root, old), modes)
    const unchanged = (each: Change) => Object.values(each).every((list) => list.length === 0)
    const sameFiles = unchanged(change(old.files, sorted))
    if (unchanged(changes) && sameFiles) {
      const also =
        unlisted.length === 0
          ? ""
          : ` Upstream also holds ${unlisted.join(", ")}, which the record does not list.`
      const body = `The copy matches upstream, so the sync proposes nothing.${also}\n`
      return { body, proposes: false }
    }
    const next: CopyRecord = Object.freeze({ ...old, commit, files: Object.freeze(sorted) })
    const recordChanges = !sameFiles || old.commit !== commit
    const links = linksOf(old, commit)
    const text = body(template, { path, copy: next, changes, unlisted, recordChanges, links })
    if (text.length > BODY_LIMIT)
      throw new Error(
        `${path}: its sync's pull request body for ${old.folder} runs past GitHub's ${BODY_LIMIT.toLocaleString("en")} characters; split its skills across records, then rerun`,
      )
    const copy = (name: string) => join(root, old.folder, name)
    for (const skill of old.skills) await rm(copy(skill), { recursive: true, force: true })
    // Each file is written from its blob, so no checkout filter or line-ending rule upstream changes its bytes, with
    // the mode Git gives it upstream.
    for (const [name, blob] of Object.entries(files)) {
      await mkdir(dirname(copy(name)), { recursive: true })
      const mode = executables.has(name) ? 0o755 : 0o644
      await writeFile(copy(name), await gitBytes(["cat-file", "blob", blob], upstream), { mode })
    }
    if (recordChanges) await writeWhole(join(root, path), recordText(next))
    return { body: text, proposes: true }
  } finally {
    await rm(upstream, { recursive: true, force: true })
  }
}

// A stop partway through leaves the old file as it was, since the rename replaces it in one step.
async function writeWhole(path: string, text: string): Promise<void> {
  const temporary = join(dirname(path), `.${basename(path)}.${process.pid}.tmp`)
  try {
    await writeFile(temporary, text)
    await rename(temporary, path)
  } finally {
    await rm(temporary, { force: true })
  }
}

export function change(before: CopyRecord["files"], after: CopyRecord["files"]): Change {
  return Object.freeze({
    changed: Object.keys(after).filter((file) => file in before && before[file] !== after[file]),
    added: Object.keys(after).filter((file) => !(file in before)),
    removed: Object.keys(before).filter((file) => !(file in after)),
  })
}

// Each file of the copy's skill folders as the checkout's index holds it, by its path in the record: its mode and blob.
async function checkedIn(root: string, copy: CopyRecord): Promise<Record<string, string>> {
  const folders = copy.skills.map((skill) => `${copy.folder}/${skill}/`)
  const listed = await git(["ls-files", "--stage", "-z", "--", ...folders], root)
  const entries = []
  for (const line of listed.split("\0").filter(Boolean)) {
    const entry = entryOf(line, INDEX_ENTRY)
    if (entry === undefined)
      throw new Error(
        `${copy.folder}: holds an index entry the sync cannot read; rerun git add on it`,
      )
    entries.push([entry.file.slice(copy.folder.length + 1), `${entry.mode} ${entry.blob}`])
  }
  return Object.fromEntries(entries)
}

function entryOf(line: string, pattern: RegExp): Entry | undefined {
  const groups = pattern.exec(line)?.groups
  if (groups === undefined) return undefined
  // A match sets each group, since none is optional.
  return Object.freeze({ mode: `${groups.mode}`, blob: `${groups.blob}`, file: `${groups.file}` })
}

// The run's page comes from the variables each Actions run sets:
// https://docs.github.com/en/actions/reference/workflows-and-actions/variables#default-environment-variables
// GitHub alone gives a compare page by this path, so other upstreams get none.
export function linksOf(old: CopyRecord, commit: string, env = process.env): Links {
  const { GITHUB_SERVER_URL: server, GITHUB_REPOSITORY: repository, GITHUB_RUN_ID: id } = env
  const run = server && repository && id ? `${server}/${repository}/actions/runs/${id}` : undefined
  const github = old.upstream.startsWith("https://github.com/")
  const moved = old.commit !== null && old.commit !== commit
  const compare = github && moved ? `${old.upstream}/compare/${old.commit}...${commit}` : undefined
  return Object.freeze({ ...(run && { run }), ...(compare && { compare }) })
}

// Each skill upstream holds beside the source's other skills, in kebab case, so the body can name it. A skill the
// recorded commit already held is one the record leaves out on purpose, so only a skill new since then is named; a
// recorded commit upstream's history no longer holds names every one.
async function unlistedSkills(upstream: string, copy: CopyRecord): Promise<string[]> {
  const history =
    copy.commit === null ? [] : (await git(["rev-list", "HEAD"], upstream)).split("\n")
  const known =
    copy.commit !== null && history.includes(copy.commit)
      ? await skillsAt(upstream, copy, copy.commit)
      : []
  return (await skillsAt(upstream, copy, "HEAD"))
    .filter((skill) => !copy.skills.includes(skill) && !known.includes(skill))
    .sort()
}

async function skillsAt(upstream: string, copy: CopyRecord, commit: string): Promise<string[]> {
  const tree = await git(
    ["ls-tree", "-r", "-z", "--name-only", commit, "--", `${copy.source}/`],
    upstream,
  )
  return tree
    .split("\0")
    .map((file) => file.slice(copy.source.length + 1).split("/"))
    .filter((parts) => parts.length === 2 && parts[1] === "SKILL.md")
    .map(([skill = ""]) => skill)
    .filter((skill) => KEBAB.test(skill))
}

// Refuses a template body() cannot fill, so a sync stops before it writes anything, and gives the template as parsed.
export function checkTemplate(template: string): Markdown {
  const read = markdown(template)
  const headings = read.headings.filter(({ depth }) => depth === 4).map(({ text }) => text)
  if (headings.join("\n") !== PARTS.join("\n"))
    throw new Error(
      `${TEMPLATE}: its #### parts are not ${PARTS.join(", ")}; update body() in scripts/sync.ts to match`,
    )
  const guidance = guidanceOf(read)
  const names = read.html
    .filter((html) => guidance === undefined || !within(html, guidance))
    .flatMap(({ value }) => {
      const [, name] = PLACEHOLDER.exec(value) ?? []
      return name === undefined ? [] : [name]
    })
  if (names.some((name) => !isPlaceholder(name)))
    throw new Error(
      `${TEMPLATE}: holds a placeholder body() in scripts/sync.ts cannot fill; fill it there`,
    )
  return read
}

// The PR template as checkTemplate parsed it, its guidance comment left out and each placeholder filled. A sync leaves
// out a risk part for a copy outside the plugin, since the template asks for one only above low risk, and the issue,
// the steps after the merge and the decisions, which it has none of; a part left empty goes with its heading.
export function body(template: Markdown, proposal: Proposal): string {
  const { path, copy, changes, unlisted, recordChanges, links } = proposal
  const { changed, added, removed } = changes
  const installed = copy.folder === "plugin/skills"
  const count = (n: number) => `${n} ${n === 1 ? "file" : "files"}`
  const files = (n: number, verb: string) => (n === 0 ? [] : [`- ${verb} ${count(n)} of the copy.`])
  const listed = (names: readonly string[], kind: string) =>
    names.map((name) => `- \`${name}\`, ${kind}`)
  const [risk, colour] = installed ? ["medium", "9a6700"] : ["low", "1f883d"]
  const size = changed.length + added.length + removed.length + (recordChanges ? 1 : 0)
  const updates = recordChanges ? `, and updates ${path} to match` : ""
  const fills: Readonly<Record<Placeholder, string | readonly string[] | null>> = {
    Headline: `Copy ${basename(path, ".json")} from upstream`,
    "What the change does for its reader": `Copies ${copy.skills.join(", ")} from ${copy.upstream} at ${copy.commit}${updates}.`,
    Badges: [
      badge("Risk", risk, colour),
      badge("Checks", "CI not run", "9a6700"),
      badge("Size", count(size), "6e7781"),
    ].join(" "),
    issue: null,
    Changes: [
      ...files(changed.length, "Changes"),
      ...files(added.length, "Adds"),
      ...files(removed.length, "Removes"),
      ...(recordChanges ? ["- Sets the record's commit and blobs to upstream's."] : []),
      ...(links.compare === undefined
        ? []
        : [`- Upstream's commits since the last sync: ${links.compare}`]),
    ],
    Risk: installed
      ? "Medium. The copy's text reaches every plugin user's agent and steers it. Close this pull request to keep the current copy."
      : null,
    Review: [
      "- Read the copy as untrusted text, as REVIEW.md says, starting from the files in the fold.",
      "- Before the merge, add the copy's CHANGELOG.md entry, as AGENTS.md › Pull requests says, and set the checks badge to the checks' state.",
      ...(unlisted.length === 0
        ? []
        : [
            `- Upstream also holds ${unlisted.join(", ")}, which the record does not list; add a skill to the record to copy it.`,
          ]),
    ],
    step: null,
    "Fold summary": "Checks and files",
    Checks: [
      "- CI had not run when the sync wrote this description.",
      ...(links.run === undefined ? [] : [`${RUN}${links.run}`]),
    ],
    Files: [
      ...listed(changed, "changed"),
      ...listed(added, "added"),
      ...listed(removed, "removed"),
      ...(recordChanges ? [`- \`${path}\`, the record`] : []),
    ],
    Decisions: null,
  }
  // Each top-level block, the guidance comment that opens the template left out, with each placeholder filled.
  const blocks = template.blocks
    .slice(guidanceOf(template) === undefined ? 0 : 1)
    .flatMap((block) => {
      let text = template.text.slice(block.start, block.end)
      let whole = false
      for (const { value, start } of template.html
        .filter((html) => within(html, block))
        .reverse()) {
        const [placeholder, name = ""] = PLACEHOLDER.exec(value) ?? []
        if (placeholder === undefined) continue
        const fill = isPlaceholder(name) ? fills[name] : null
        if (fill === null) return []
        const at = start - block.start + value.indexOf(placeholder)
        whole ||= text === placeholder
        text =
          typeof fill === "string"
            ? text.slice(0, at) + fill + text.slice(at + placeholder.length)
            : fill.join("\n")
      }
      if (text === "") return []
      return [
        {
          text,
          part: block.type === "heading" && block.depth === 4,
          content: whole || (block.type !== "html" && block.type !== "heading"),
        },
      ]
    })
  // A part left empty goes with its heading: one that the next heading, HTML or the end follows.
  const kept = blocks.filter((block, index) => !block.part || (blocks[index + 1]?.content ?? false))
  return `${kept.map(({ text }) => text).join("\n\n")}\n`
}

// The comment that opens the PR template to guide its author, which a sync's description leaves out.
function guidanceOf(read: Markdown): Markdown["blocks"][number] | undefined {
  const [first] = read.blocks
  return first?.type === "html" && read.text.startsWith("<!--", first.start) ? first : undefined
}

// A shields.io static badge: https://shields.io/badges/static-badge
function badge(label: string, message: string, colour: string): string {
  const escaped = encodeURIComponent(message)
  return `![${label}: ${message}](https://img.shields.io/badge/${label.toLowerCase()}-${escaped}-${colour}?style=flat-square)`
}

export async function cloneUpstream(
  url: string,
  into: string,
  options: GitOptions = {},
): Promise<void> {
  await git([...CLONE, "--", `${url}.git`, into], into, options)
}

if (import.meta.main) await runMain(run, join(import.meta.dirname, ".."))
