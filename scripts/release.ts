/**
 * The release steps the tools leave, which the release skill (.agents/skills/release/SKILL.md) and the release workflow
 * run:
 * - `bump [<version>]`, from a working tree with no changes, sets the version, the next patch by default, through
 *   cz bump, and titles CHANGELOG.md's [Unreleased] with it and today's date in UTC;
 * - `notes [<version>]` prints the release page, of the plugin's version by default;
 * - `bundle` builds dist/nustack-<version>.zip from plugin/ as HEAD holds it;
 * - `tag` checks out the commit on main that set main's version, runs make check and make smoke on it, and pushes
 *   v<version> on it, reaching the plugin's repository over HTTPS;
 * - `verify-tag <tag>` checks that a tag names the plugin's version, on main;
 * - `publish <tag> <commit>` publishes the GitHub release from the zip and page in dist/, only while the tag names the
 *   commit CI passed on.
 */
import { mkdir, readdir, readFile, rename, rm, writeFile } from "node:fs/promises"
import { basename, dirname, join } from "node:path"
import { asksForUsage, runMain, usage } from "./command.ts"
import { type Gh, ghOutput, runGh } from "./gh.ts"
import { GitError, type GitOptions, git, gitBytes } from "./git.ts"
import { type Markdown, markdown, type Section, section, within } from "./markdown.ts"
import { CLAUDE_MANIFEST, PACKAGE, type Plugin, parseManifest, parsePackage } from "./metadata.ts"
import { PAGE_STEPS, VERSION } from "./plugin.ts"
import { SHA } from "./record.ts"
import { decode, readEntry, type Tree } from "./tree.ts"

// Each command, with the fewest and the most arguments it takes.
const COMMANDS = Object.freeze({
  bump: [0, 1],
  notes: [0, 1],
  bundle: [0, 0],
  tag: [0, 0],
  "verify-tag": [1, 1],
  publish: [2, 2],
} as const)
type Command = keyof typeof COMMANDS
const USAGE = usage(
  "release",
  "bump [version] | notes [version] | bundle | tag | verify-tag <tag> | publish <tag> <commit>",
)
const UNRELEASED = "## [Unreleased]"
export const tagOf = (version: string) => `v${version}`
// gh reports a missing release as exactly this: https://github.com/cli/cli/blob/v2.103.3/pkg/cmd/release/shared/fetch.go
const NO_RELEASE = "release not found"
// GitHub answers a ref it cannot find with this, which gh prints as the reply's body, as
// tests/fixtures/github/tag-commit/missing.json records.
const NO_COMMIT = "No commit found for SHA"
// A tree, unlike a commit, gives git archive no date and no comment, so the same plugin/ files give the same zip
// bytes whichever commit holds them; each entry takes the earliest MS-DOS time instead. git writes that time in its
// own time zone, so it runs in UTC. git reads its environment when it starts, which is before archive's first
// await, so the zone it sets reaches only that run.
const ZIP_TIME = "1980-01-01T00:00:00Z"
// tag fetches main into this ref, which only tag writes, and reads main at the one commit it names, since another fetch
// in the clone, such as an editor's, can rewrite FETCH_HEAD between any two reads of it.
const FETCHED_MAIN = "refs/nustack/fetched-main"

export async function run(root: string, args: readonly string[]): Promise<string> {
  const [given, ...rest] = args
  if (asksForUsage(args, Object.keys(COMMANDS))) return USAGE
  if (given === undefined || !Object.hasOwn(COMMANDS, given)) throw new Error(USAGE)
  const command = given as Command
  const [fewest, most] = COMMANDS[command]
  if (rest.length < fewest || rest.length > most) throw new Error(USAGE)
  const [first] = rest
  switch (command) {
    case "bump":
      return bump(root, first)
    case "notes": {
      const plugin = await readPlugin(root)
      const [changelog, readme] = await Promise.all([
        text(root, "CHANGELOG.md"),
        text(root, "README.md"),
      ])
      return notes(changelog, readme, first ?? plugin.version, plugin)
    }
    case "bundle":
      return bundle(root)
    case "tag":
      return tag(root)
    // The count check above leaves each argument these commands require defined.
    case "verify-tag":
      return verifyTag(root, rest[0] as string)
    case "publish":
      return publish(root, rest[0] as string, rest[1] as string)
  }
}

export async function bump(root: string, given?: string, setVersion = czBump): Promise<string> {
  await refuseChanges(root, "would ride into the release's commit")
  const plugin = await readPlugin(root)
  const version = given ?? plugin.version.replace(/\d+$/, (patch) => `${Number(patch) + 1}`)
  if (!VERSION.test(version)) throw new Error("pass the version as <major>.<minor>.<patch>")
  if (Bun.semver.order(version, plugin.version) !== 1)
    throw new Error(`pass a version above ${plugin.version}, the plugin's version`)
  // A release is dated by its day in UTC, so every machine that cuts it agrees.
  const date = new Date().toISOString().slice(0, 10)
  // The changelog is titled before cz bump runs, so a changelog it cannot title stops the bump before any change.
  const titled = title(await text(root, "CHANGELOG.md"), date, { ...plugin, version })
  // The tree started clean, so a bump that fails part-way goes back to HEAD and changes nothing.
  try {
    await setVersion(root, version)
    await writeFile(join(root, "CHANGELOG.md"), titled)
  } catch (error) {
    await git(["restore", "--source=HEAD", "--staged", "--worktree", ":/"], root)
    await git(["clean", "-fdq", ":/"], root)
    throw error
  }
  return `Set version ${version} and titled [Unreleased] as [${version}] - ${date}`
}

export function title(changelog: string, date: string, plugin: Plugin): string {
  const { version, repository } = plugin
  const read = markdown(changelog)
  const unreleased = section(read, UNRELEASED)
  if (unreleased === undefined) throw new Error("CHANGELOG.md has no ## [Unreleased]; add one")
  if (!read.blocks.some((block) => block.type === "list" && within(block, unreleased)))
    throw new Error(
      "CHANGELOG.md's [Unreleased] lists no change; merge the changes to release first",
    )
  const link = read.definitions.find(({ label }) => label.toLowerCase() === "unreleased")
  if (link === undefined) throw new Error("CHANGELOG.md has no [Unreleased] link; add one")
  if (section(read, `## [${version}]`) !== undefined)
    throw new Error(`CHANGELOG.md already holds [${version}]; bump to the next version`)
  // What title inserts takes the changelog's own line ending, so a CRLF changelog stays CRLF throughout.
  const eol = changelog.includes("\r\n") ? "\r\n" : "\n"
  const links = `[Unreleased]: ${repository}/compare/${tagOf(version)}...HEAD${eol}[${version}]: ${repository}/releases/tag/${tagOf(version)}`
  const edits = [
    {
      at: unreleased.heading.end,
      end: unreleased.heading.end,
      text: `${eol}${eol}## [${version}] - ${date}`,
    },
    { at: link.start, end: link.end, text: links },
  ].sort((one, other) => other.at - one.at)
  return edits.reduce(
    (text, { at, end, text: edit }) => text.slice(0, at) + edit + text.slice(end),
    changelog,
  )
}

export function notes(changelog: string, readme: string, version: string, plugin: Plugin): string {
  if (!VERSION.test(version)) throw new Error("pass the version as <major>.<minor>.<patch>")
  const log = markdown(changelog)
  const entry = sectionOf(log, `## [${version}]`, "CHANGELOG.md")
  const [kind] = log.headings.filter((heading) => within(heading, entry))
  const lead = log.text.slice(entry.start, kind?.lines.start ?? entry.end).trim()
  const changes = log.text.slice(kind?.lines.start ?? entry.end, entry.end).trim()
  // Each version's heading links its release by its label, as title writes it, so the next heading's label is the
  // version before.
  const previous = entry.next?.reference
  if (entry.next !== undefined && previous === undefined)
    throw new Error(
      `CHANGELOG.md: the heading after [${version}] links no version; define its label`,
    )
  const span = previous && `${tagOf(previous)}...${tagOf(version)}`
  const page = markdown(readme)
  return [
    `> **[${plugin.name}](${plugin.repository})** · ${plugin.description}`,
    lead,
    "## 🆕 What's new",
    changes,
    "## 🚀 Quick start",
    ...PAGE_STEPS.map(
      (heading) => `${heading}\n\n${sectionOf(page, heading, "README.md").body.trim()}`,
    ),
    span && `**Full changelog:** [\`${span}\`](${plugin.repository}/compare/${span})`,
  ]
    .filter(Boolean)
    .join("\n\n")
    .replace(/\r\n?/g, "\n")
}

function sectionOf(read: Markdown, heading: string, file: string): Section {
  const found = section(read, heading)
  if (found === undefined) throw new Error(`${file} has no ${heading} heading; add it`)
  return found
}

function zipOf(root: string, version: string): string {
  return join(root, "dist", `nustack-${version}.zip`)
}

// git archive zips plugin/'s tree as HEAD holds it, so the zip's paths leave the folder's name out
// (https://git-scm.com/docs/git-archive). The zip takes its name only once whole, and only then do older zips go,
// since make smoke unpacks the only one.
export async function bundle(root: string): Promise<string> {
  const version = versionOf(await gitBytes(["show", `HEAD:${PACKAGE}`], root), "HEAD")
  const zip = zipOf(root, version)
  const folder = dirname(zip)
  const name = basename(zip)
  const partial = `${zip}.partial`
  await mkdir(folder, { recursive: true })
  try {
    await archive(partial, root)
    await rename(partial, zip)
  } catch (error) {
    await rm(partial, { force: true })
    throw error
  }
  const older = (await readdir(folder)).filter((file) => file.endsWith(".zip") && file !== name)
  await Promise.all(older.map((file) => rm(join(folder, file))))
  return `Built dist/${name}`
}

// The tag goes to the plugin's repository by its https URL, whatever transport the checkout's own remotes use.
// Tests pass "file", since their repositories are local; a release reaches its repository over HTTPS only.
export async function tag(
  root: string,
  verify = makeChecks,
  transport: GitOptions["transport"] = "https",
): Promise<string> {
  const { repository } = await readPlugin(root)
  const remote = `${repository}.git`
  // A checkout carries changes along, so the checks would read them in place of the commit they tag.
  await refuseChanges(root, "the checks would read in place of the commit they tag")
  // A shallow clone's history stops at its boundary, whose commit would read as the one that set the version.
  if ((await git(["rev-parse", "--is-shallow-repository"], root)).trim() === "true")
    throw new Error("the clone is shallow; run git fetch --unshallow origin, then rerun")
  const held = versionOf(await gitBytes(["show", `HEAD:${PACKAGE}`], root), "HEAD")
  await git(["fetch", "--no-tags", remote, `+main:${FETCHED_MAIN}`], root, { transport })
  const main = await revision(root, FETCHED_MAIN).finally(() =>
    git(["update-ref", "-d", FETCHED_MAIN], root),
  )
  const where = `main at ${repository}`
  const version = versionOf(await gitBytes(["show", `${main}:${PACKAGE}`], root), where)
  // A checkout above main's version holds a release that has not merged, whose tag would name main's older one.
  if (Bun.semver.order(held, version) === 1)
    throw new Error(
      `${where} holds ${version}, below HEAD's ${held}; merge the release pull request, then rerun`,
    )
  const commit = await releaseCommit(root, main, version)
  const name = tagOf(version)
  // The tag goes from the commit straight to the repository, so a rerun after a failed push checks only there.
  // An annotated tag names its tag object, and ls-remote gives the commit it names on the line for <tag>^{}.
  const listed = await git(
    ["ls-remote", remote, `refs/tags/${name}`, `refs/tags/${name}^{}`],
    root,
    {
      transport,
    },
  )
  const named = new Map(
    listed
      .split("\n")
      .filter(Boolean)
      .map((line) => line.split("\t").reverse() as [string, string]),
  )
  const tagged = named.get(`refs/tags/${name}^{}`) ?? named.get(`refs/tags/${name}`)
  if (tagged === commit)
    return `${repository} already holds ${name} on ${commit}; the release workflow publishes from it`
  if (tagged)
    throw new Error(
      `${repository} holds ${name} on another commit; bump to the next version, then rerun`,
    )
  // The checks run in the clone's own working tree, which tag leaves at the commit, detached.
  await git(["checkout", "--quiet", "--detach", commit], root)
  await verify(root)
  try {
    await git(["push", remote, `${commit}:refs/tags/${name}`], root, { transport })
  } catch (error) {
    if (!(error instanceof GitError)) throw error
    throw new Error(
      `${name} was not pushed to ${repository} (${error.message}); fix that, then rerun`,
    )
  }
  return `Pushed ${name}, on ${commit}, which the clone has checked out detached`
}

async function archive(zip: string, root: string): Promise<string> {
  const zone = process.env.TZ
  process.env.TZ = "UTC"
  try {
    // HEAD:plugin's paths leave out plugin/, so no .gitattributes line for plugin/ matches them, and core.autocrlf
    // would rewrite each text file's line endings by the machine's config; with it off, the zip holds the blobs' bytes.
    return git(
      [
        "-c",
        "core.autocrlf=false",
        "archive",
        "--format=zip",
        `--mtime=${ZIP_TIME}`,
        "-o",
        zip,
        "HEAD:plugin",
      ],
      root,
    )
  } finally {
    if (zone === undefined) delete process.env.TZ
    else process.env.TZ = zone
  }
}

// The commit on fetched main's first-parent line that set the version: the oldest of the newest commits to touch
// plugin/package.json that hold it, so the release's merge commit is found however far main has moved on. Each commit
// above the newest listed one keeps its plugin/package.json, so that one holds main's version, as main does.
async function releaseCommit(root: string, main: string, version: string): Promise<string> {
  let setter = main
  const listed = await git(["rev-list", "--first-parent", main, "--", PACKAGE], root)
  for (const commit of listed.split("\n").filter(Boolean)) {
    // A commit with no plugin/package.json holds another version; any other failure to read one stops the run.
    const listedPackage = await git(["ls-tree", "--name-only", commit, "--", PACKAGE], root)
    const held = listedPackage.trim()
      ? parsedVersion(await gitBytes(["show", `${commit}:${PACKAGE}`], root))
      : undefined
    if (held !== version) break
    setter = commit
  }
  return setter
}

export async function verifyTag(root: string, name: string): Promise<string> {
  versionOfTag(name)
  const expected = tagOf((await readPlugin(root)).version)
  if (name !== expected) throw new Error(`${name} is not the plugin's version; push ${expected}`)
  const commit = await revision(root, `refs/tags/${name}`).catch((error) => {
    if (error instanceof GitError && error.code === 128)
      throw new Error(`${name} is not in this clone; fetch the tags from origin, then rerun`)
    throw error
  })
  // merge-base --is-ancestor exits 1 when the commit is not an ancestor: https://git-scm.com/docs/git-merge-base
  await git(["merge-base", "--is-ancestor", commit, "origin/main"], root).catch((error) => {
    if (error instanceof GitError && error.code === 1)
      throw new Error(`${name} is not on origin/main; tag a commit on main`)
    throw error
  })
  return `${name} names the plugin's version, on main at ${commit}`
}

// The release stays a draft until the zip is up and the tag still names the commit CI passed on, which leaves only the
// moment between that last check and the edit for a tag pushed again to slip in. A rerun finishes a draft and leaves a
// published release as it is, whichever commit its zip came from.
export async function publish(
  root: string,
  name: string,
  commit: string,
  gh = runGh,
): Promise<string> {
  const version = versionOfTag(name)
  if (!SHA.test(commit)) throw new Error("pass the commit CI passed on as its full SHA")
  const zip = zipOf(root, version)
  const notesFile = join(root, "dist", "notes.md")
  for (const file of [zip, notesFile])
    if (!(await Bun.file(file).exists()))
      throw new Error(
        `dist/ holds no ${basename(file)}; download the release artifact CI built, then rerun`,
      )
  const refuseMoved = async () => {
    const args = ["api", `repos/{owner}/{repo}/commits/tags/${name}`, "--jq", ".sha"]
    const ran = await gh(args)
    if (ran.stdout.includes(NO_COMMIT))
      throw new Error(
        `${name} names no commit GitHub can find; push it again if it was deleted, then rerun`,
      )
    const named = await ghOutput(gh, args, ran)
    if (named.trim() !== commit)
      throw new Error(
        `${name} names a commit other than ${commit}, which CI passed on; the tag's own run publishes from its commit`,
      )
  }
  await refuseMoved()
  switch (await releaseState(gh, name)) {
    case "published":
      return `${name} is already published, so it stays as it is, with the zip it was published with`
    case "missing":
      await ghOutput(gh, ["release", "create", name, "--draft", "--verify-tag", "--notes", ""])
      break
    case "draft":
      break
  }
  await ghOutput(gh, ["release", "upload", name, zip, "--clobber"])
  await refuseMoved()
  // A release before v0.1.0, the first version held to a stable interface, is a pre-release.
  const prerelease = version.startsWith("0.0.")
  const page = [
    "--title",
    `nustack ${version}`,
    "--notes-file",
    notesFile,
    `--prerelease=${prerelease}`,
  ]
  await ghOutput(gh, ["release", "edit", name, "--draft=false", ...page])
  return `Published ${name}`
}

async function releaseState(gh: Gh, name: string): Promise<"missing" | "draft" | "published"> {
  const args = ["release", "view", name, "--json", "isDraft", "--jq", ".isDraft"]
  const viewed = await gh(args)
  if (viewed.code !== 0 && viewed.stderr.trim() === NO_RELEASE) return "missing"
  switch ((await ghOutput(gh, args, viewed)).trim()) {
    case "true":
      return "draft"
    case "false":
      return "published"
    default:
      throw new Error(
        `gh ${args.join(" ")} printed neither true nor false; rerun once GitHub answers`,
      )
  }
}

async function revision(root: string, ref: string): Promise<string> {
  return (await git(["rev-parse", "--verify", `${ref}^{commit}`], root)).trim()
}

async function refuseChanges(root: string, consequence: string): Promise<void> {
  // A status.showUntrackedFiles of no would hide an untracked file, which bump's failure path then cleans away.
  if ((await git(["status", "--porcelain", "--untracked-files=normal"], root)) !== "")
    throw new Error(
      `the working tree has changes, which ${consequence}; commit or stash them, then rerun`,
    )
}

// make and cz run while the releaser watches the run they started, which bounds the wait.
export async function makeChecks(root: string): Promise<void> {
  const make = Bun.spawn(["make", "check", "smoke"], { cwd: root, stdout: "inherit" })
  if ((await make.exited) !== 0) throw new Error("make check or smoke failed; fix it, then rerun")
}

// cz bump sets the version in each file [tool.commitizen] names, and the script titles the changelog itself.
export async function czBump(root: string, version: string): Promise<void> {
  const cz = Bun.spawn(["uv", "run", "cz", "bump", "--version-files-only", "--yes", version], {
    cwd: root,
    stdout: "inherit",
  })
  if ((await cz.exited) !== 0)
    throw new Error("cz bump failed; fix the cause it printed, then rerun")
}

// The version of plugin/package.json at a commit, such as HEAD's, so a zip or a tag never names an unset version.
function versionOf(packageJson: Uint8Array, at: string): string {
  const version = parsedVersion(packageJson)
  if (version === undefined)
    throw new Error(
      `${PACKAGE} at ${at} holds no <major>.<minor>.<patch> version; commit one, then rerun`,
    )
  return version
}

export async function readPlugin(root: string): Promise<Plugin> {
  const paths = [CLAUDE_MANIFEST, PACKAGE]
  const read = await Promise.all(
    paths.map(async (path) => [path, await readEntry(root, path)] as const),
  )
  const tree: Tree = new Map(
    read.filter((entry): entry is [string, Uint8Array | "symlink"] => entry[1] !== undefined),
  )
  const [manifest, pkg] = [parseManifest(tree, CLAUDE_MANIFEST), parsePackage(tree)]
  const problems = [manifest, pkg].flatMap((parsed) => (Array.isArray(parsed) ? parsed : []))
  if (Array.isArray(manifest) || Array.isArray(pkg)) throw new Error(problems.join("\n"))
  const { name, description, repository } = manifest
  return Object.freeze({ name, version: pkg.version, description, repository })
}

// plugin/package.json as a commit holds it, read as make check reads it.
function parsedVersion(packageJson: Uint8Array): string | undefined {
  const parsed = parsePackage(new Map([[PACKAGE, packageJson]]))
  return Array.isArray(parsed) ? undefined : parsed.version
}

function versionOfTag(name: string): string {
  const version = name.slice(1)
  if (tagOf(version) !== name || !VERSION.test(version))
    throw new Error("pass the tag as v<major>.<minor>.<patch>")
  return version
}

async function text(root: string, path: string): Promise<string> {
  const decoded = decode(new Map([[path, await readFile(join(root, path))]]), path, (text) => text)
  if (!Array.isArray(decoded)) throw new Error(`${decoded.problem}, then rerun`)
  return decoded[0]
}

if (import.meta.main) await runMain(run, join(import.meta.dirname, ".."))
