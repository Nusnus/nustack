/**
 * Cuts a release, as .agents/skills/release/SKILL.md says: `bump <version>` sets the version and titles the
 * changelog section, `notes` prints the section the release page shows, and `publish [--dry-run]` tags and
 * publishes the version the manifests hold, once.
 */
import { rename } from "node:fs/promises"
import { $ } from "bun"
import { MANIFESTS, VERSION_SOURCE } from "./manifests.ts"

const VERSIONED = [...MANIFESTS, "plugin/package.json"] as const
const CHANGELOG = "CHANGELOG.md"
const SEMVER = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/

const args = process.argv.slice(2)
const [command, argument] = args
if (command === "bump" && argument !== undefined && args.length === 2)
  await bump(argument, new Date().toISOString().slice(0, 10))
else if (args.join(" ") === "notes") console.log(await notes())
else if (args.join(" ") === "publish") await publish(false)
else if (args.join(" ") === "publish --dry-run") await publish(true)
else
  fail(
    `Run bump <version>, notes or publish [--dry-run]; got ${args.join(" ") || "no arguments"}`,
    2,
  )

// A rerun after a bump stopped partway finishes it: each file already at the version is left as it is.
async function bump(version: string, date: string) {
  if (!SEMVER.test(version))
    fail(`Give the version as <major>.<minor>.<patch>, such as 0.1.0; got ${version}`, 2)
  const changelog = await Bun.file(CHANGELOG).text()
  const texts = new Map<string, string>()
  for (const path of VERSIONED) texts.set(path, await Bun.file(path).text())
  const versions = new Map(
    [...texts].map(([path, text]) => [path, versionOf(path, JSON.parse(text))]),
  )
  const others = [...new Set(versions.values())].filter((each) => each !== version)
  if (others.length > 1)
    fail(
      `${[...versions].map(([path, each]) => `${path} holds ${each}`).join(", ")}; set them all to one version`,
    )
  const titled = section(changelog, version) !== undefined
  if (others.length === 0 && titled) {
    console.log(`Version ${version} is already set and titled in ${CHANGELOG}; nothing to do`)
    return
  }
  const released = /^## \[(\d+\.\d+\.\d+)\]/m.exec(changelog)?.[1]
  for (const was of titled ? others : [...others, released])
    if (was !== undefined && Bun.semver.order(version, was) !== 1)
      fail(
        `${version} is not above ${was}, the version released or set before it; pick a higher one`,
      )
  let next = changelog
  if (!titled) {
    const unreleased = section(changelog, "Unreleased")
    if (unreleased === undefined)
      fail(`${CHANGELOG}: has no [Unreleased] section; add one as Keep a Changelog shows`)
    if (!/^- /m.test(unreleased))
      fail(`${CHANGELOG}: [Unreleased] lists no change; a release needs at least one entry`)
    const link = /^\[Unreleased\]: (\S+)\/compare\/v\S+\.\.\.HEAD$/m.exec(changelog)
    if (link === null)
      fail(`${CHANGELOG}: has no [Unreleased] compare link; add one as Keep a Changelog shows`)
    next = changelog
      .replace("\n## [Unreleased]\n", `\n## [Unreleased]\n\n## [${version}] - ${date}\n`)
      .replace(
        link[0],
        `[Unreleased]: ${link[1]}/compare/v${version}...HEAD\n[${version}]: ${link[1]}/releases/tag/v${version}`,
      )
  }
  const bumped = new Map<string, string>()
  for (const [path, text] of texts) {
    const was = versions.get(path)
    if (was === version) continue
    const replaced = text.replace(`"version": "${was}"`, `"version": "${version}"`)
    if (replaced === text)
      fail(`${path}: holds no "version": "${was}" line; set it as the other manifests do`)
    bumped.set(path, replaced)
  }
  for (const [path, text] of bumped) await writeWhole(path, text)
  if (!titled) await writeWhole(CHANGELOG, next)
  console.log(`Set version ${version} and titled its section in ${CHANGELOG}`)
}

async function publish(dryRun: boolean) {
  const version = await current()
  const tag = `v${version}`
  // Before v0.1.0 nustack promises its users no stable interface, as AGENTS.md says, so each release before it is a pre-release.
  const prerelease = version.startsWith("0.0.")
  const kind = prerelease ? "pre-release" : "release"
  const body = await notes()
  const list = await $`gh release list --limit 1000 --json tagName --jq .[].tagName`
    .quiet()
    .nothrow()
  if (list.exitCode !== 0)
    fail(
      `gh release list failed, so whether ${tag} is released is unknown: ${list.stderr.toString().trim()}`,
    )
  if (list.stdout.toString().split("\n").includes(tag)) {
    console.log(`${tag} is already released; nothing to do`)
    return
  }
  if (dryRun) {
    console.log(
      `Would tag ${tag} on the release pull request's merge commit and publish this ${kind} page:\n\n${body}`,
    )
    return
  }
  // Tags the commit that made the version whole, so pull requests merged after the release stay out of its tag. Walks
  // back over the commits that change a manifest or plugin/package.json while each leaves those it holds at that
  // version, so a commit that reformats one, or adds or renames a manifest, moves no tag, and a bump merged in parts,
  // or repaired, is tagged at its last part. Git reads a shallow clone's oldest commit as one that adds every file:
  // https://git-scm.com/docs/shallow
  if ((await $`git rev-parse --is-shallow-repository`.text()).trim() === "true")
    fail(
      "This clone is shallow, so the commit that set the version is unknown; fetch main's full history",
    )
  const mergeFirst = "merge the release pull request, then publish from an up-to-date main"
  // Escapes each character an extended regular expression reads as other than itself:
  // https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap09.html#tag_09_04_03
  const sets = `"version"[[:space:]]*:[[:space:]]*"${version.replace(/[.[\\()*+?{|^$]/g, "\\$&")}"`
  // Searches each file as its commit holds it, whatever text conversion the caller's attributes name for it:
  // https://git-scm.com/docs/git-log#Documentation/git-log.txt---no-textconv
  // Git's -S lists the commits that change how many times such a file sets the version; where it lists none, no
  // commit holds the bump, and the walk has nothing to read:
  // https://git-scm.com/docs/git-log#Documentation/git-log.txt--Sstring
  const bumped =
    (
      await $`git log --no-textconv --format=%H --pickaxe-regex -S${sets} -- ${VERSIONED}`.text()
    ).trim() !== ""
  // Lists the commits that change one of those files, each with its parents among them and no parent before a child
  // of it, so the first is the last to change them and one pass meets each parent after its child. Where a merge
  // keeps one parent's files, Git follows that parent alone, so the list holds no commit of the other sides. The walk
  // steps to a parent that holds the version whole, since a merge has several and the bump may be on the line of any:
  // https://git-scm.com/docs/git-rev-list#_history_simplification
  // https://git-scm.com/docs/git-rev-list#Documentation/git-rev-list.txt---parents
  // https://git-scm.com/docs/git-rev-list#Documentation/git-rev-list.txt---topo-order
  const changes = bumped
    ? (await $`git rev-list --topo-order --parents HEAD -- ${VERSIONED}`.text())
        .split("\n")
        .filter(Boolean)
        .map((line) => line.split(" "))
    : []
  const last = changes[0]?.[0]
  if (last === undefined) fail(`No commit sets the version to ${version}; ${mergeFirst}`)
  const problem = await problemAt(last, version)
  if (problem !== undefined)
    fail(
      `${problem}, the last commit to change the manifests or plugin/package.json; bring main to a commit at which each of them holds ${version}, then publish from an up-to-date main`,
    )
  let commit = last
  for (const [change, ...parents] of changes) {
    if (change !== commit) continue
    const parent = await firstWithoutProblem(parents, version)
    if (parent === undefined) break
    commit = parent
  }
  // Git exits with 1 where the commit is not on the branch, and with another status where it cannot tell:
  // https://git-scm.com/docs/git-merge-base#Documentation/git-merge-base.txt---is-ancestor
  const merged = await $`git merge-base --is-ancestor ${commit} origin/main`.quiet().nothrow()
  if (merged.exitCode === 1)
    fail(`${commit}, which set ${version}, is not on origin/main; ${mergeFirst}`)
  if (merged.exitCode !== 0)
    fail(
      `git merge-base failed, so whether ${commit}, which set ${version}, is on origin/main is unknown: ${merged.stderr.toString().trim()}`,
    )
  await $`gh release create ${tag} --target ${commit} --title ${`nustack ${version}`} --prerelease=${prerelease} --notes-file - < ${new Response(body)}`
  console.log(`Published ${tag} on ${commit} as a ${kind}`)
}

async function firstWithoutProblem(
  commits: string[],
  version: string,
): Promise<string | undefined> {
  for (const commit of commits) if ((await problemAt(commit, version)) === undefined) return commit
  return undefined
}

// Reads the manifests and plugin/package.json the commit holds, since it holds none added or renamed after it.
async function problemAt(commit: string, version: string): Promise<string | undefined> {
  for (const path of VERSIONED) {
    const file = `${commit}:${path}`
    // Asks Git for the file by its object name, which is no pathspec for the caller's pathspec variables to change,
    // and in a batch, which prints "<object> missing" for a name the commit lacks where git cat-file -t fails:
    // https://git-scm.com/docs/git#Documentation/git.txt-GITGLOBPATHSPECS
    // https://git-scm.com/docs/git-cat-file#_batch_output
    const type =
      await $`git cat-file ${"--batch-check=%(objecttype)"} < ${new Response(file)}`.text()
    if (type.trimEnd().endsWith(" missing")) continue
    // Drops a byte order mark, as the check script's read of the file and the bump's do: a Blob's text is its bytes
    // by UTF-8 decode, which drops one.
    // https://w3c.github.io/FileAPI/#text-method-algo
    // https://encoding.spec.whatwg.org/#utf-8-decode
    const text = (await $`git show ${file}`.text()).replace(/^\uFEFF/, "")
    let committed: unknown
    try {
      committed = Object(JSON.parse(text)).version
    } catch {
      return `${path}: is not JSON at ${commit}`
    }
    if (committed !== version)
      return `${path}: holds ${JSON.stringify(committed) ?? "no version"} at ${commit}`
  }
}

async function notes(): Promise<string> {
  const version = await current()
  const body = section(await Bun.file(CHANGELOG).text(), version)
  if (!body)
    fail(
      `${CHANGELOG}: has no section for ${version}, the manifests' version; run the release skill's bump`,
    )
  return body
}

async function current(): Promise<string> {
  return versionOf(VERSION_SOURCE, await Bun.file(VERSION_SOURCE).json())
}

function versionOf(path: string, manifest: unknown): string {
  const { version } = Object(manifest)
  if (typeof version !== "string")
    fail(
      `${path}: has no "version" string, got ${JSON.stringify(version)}; set it as the other manifests do`,
    )
  return version
}

function section(changelog: string, title: string): string | undefined {
  const start = changelog.indexOf(`\n## [${title}]`)
  if (start === -1) return undefined
  const body = changelog.slice(changelog.indexOf("\n", start + 1) + 1)
  const end = body.indexOf("\n## [")
  return (end === -1 ? body : body.slice(0, end)).trim()
}

// Writes through a sibling file and a rename, so a bump stopped mid-write leaves each file whole for its rerun.
async function writeWhole(path: string, text: string) {
  await Bun.write(`${path}.tmp`, text)
  await rename(`${path}.tmp`, path)
}

// Exits 2 on a command line the script does not take, as nustack's other scripts do.
function fail(message: string, status = 1): never {
  console.error(message)
  process.exit(status)
}
