/**
 * Cuts a release, as .agents/skills/release/SKILL.md says: `bump <version>` sets the version and titles the
 * changelog section, `notes` prints the section the release page shows, and `publish [--dry-run]` tags and
 * publishes the version the manifests hold, once.
 */
import { $ } from "bun"
import { MANIFESTS } from "./manifests.ts"

// The release workflow runs on a change to this manifest, so its version is the one a release publishes.
const VERSION_SOURCE = "plugin/.claude-plugin/plugin.json"
const VERSIONED = [...MANIFESTS, "plugin/package.json"]
const CHANGELOG = "CHANGELOG.md"
const SEMVER = /^\d+\.\d+\.\d+$/

const [command, argument] = process.argv.slice(2)
if (command === "bump") await bump(argument)
else if (command === "notes") console.log(await notes())
else if (command === "publish") await publish(argument === "--dry-run")
else fail("Run bump <version>, notes or publish [--dry-run]")

// A rerun after a bump stopped partway finishes it: each file already at the version is left as it is.
async function bump(version: string | undefined) {
  if (version === undefined || !SEMVER.test(version))
    fail("Give the version as <major>.<minor>.<patch>, such as 0.1.0")
  const changelog = await Bun.file(CHANGELOG).text()
  const texts = new Map<string, string>()
  for (const path of VERSIONED) texts.set(path, await Bun.file(path).text())
  const versions = new Map(
    [...texts].map(([path, text]) => [path, (JSON.parse(text) as { version: string }).version]),
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
    if (!/^- /m.test(section(changelog, "Unreleased") ?? ""))
      fail(`${CHANGELOG}: [Unreleased] lists no change; a release needs at least one entry`)
    const link = /^\[Unreleased\]: (\S+)\/compare\/v\S+\.\.\.HEAD$/m.exec(changelog)
    if (link === null)
      fail(`${CHANGELOG}: has no [Unreleased] compare link; add one as Keep a Changelog shows`)
    const date = new Date().toISOString().slice(0, 10)
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
  for (const [path, text] of bumped) await Bun.write(path, text)
  if (!titled) await Bun.write(CHANGELOG, next)
  console.log(`Set version ${version} and titled its section in ${CHANGELOG}`)
}

async function publish(dryRun: boolean) {
  const version = await current()
  const tag = `v${version}`
  // A release before v0.1.0, the first version held to a stable interface, is a pre-release.
  const prerelease = version.startsWith("0.0.")
  const kind = prerelease ? "pre-release" : "release"
  const body = await notes()
  const view = await $`gh release view ${tag}`.quiet().nothrow()
  if (view.exitCode === 0) {
    console.log(`${tag} is already released; nothing to do`)
    return
  }
  if (!view.stderr.toString().includes("release not found")) fail(view.stderr.toString().trim())
  if (dryRun) {
    console.log(
      `Would tag ${tag} on the release pull request's merge commit and publish this ${kind} page:\n\n${body}`,
    )
    return
  }
  // Tags the commit that set the version, so pull requests merged after the release stay out of its tag.
  const commit = (
    await $`git log -1 --format=%H -G${'"version":'} -- ${VERSION_SOURCE}`.text()
  ).trim()
  if (commit === "")
    fail(`${VERSION_SOURCE}: no commit in this clone sets its version; fetch main's full history`)
  await $`gh release create ${tag} --target ${commit} --title ${tag} --prerelease=${prerelease} --notes-file - < ${new Response(body)}`
  console.log(`Published ${tag} on ${commit} as a ${kind}`)
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
  return (await Bun.file(VERSION_SOURCE).json()).version
}

function section(changelog: string, title: string): string | undefined {
  const start = changelog.indexOf(`\n## [${title}]`)
  if (start === -1) return undefined
  const body = changelog.slice(changelog.indexOf("\n", start + 1) + 1)
  const end = body.indexOf("\n## [")
  return (end === -1 ? body : body.slice(0, end)).trim()
}

function fail(message: string): never {
  console.error(message)
  process.exit(1)
}
