/**
 * Cuts a release, as .agents/skills/release/SKILL.md says: `bump <version>` sets the version and titles the
 * changelog section, `notes` prints the section the release page shows, and `publish [--dry-run]` tags and
 * publishes the version the manifests hold, once.
 */
import { $ } from "bun"

const MANIFESTS = [
  "plugin/.claude-plugin/plugin.json",
  "plugin/.cursor-plugin/plugin.json",
  "plugin/.devin-plugin/plugin.json",
  "plugin/package.json",
]
const CHANGELOG = "CHANGELOG.md"
const SEMVER = /^\d+\.\d+\.\d+$/

function fail(message: string): never {
  console.error(message)
  process.exit(1)
}

async function current(): Promise<string> {
  return (await Bun.file(MANIFESTS[0] ?? "").json()).version
}

function section(changelog: string, title: string): string | undefined {
  const start = changelog.indexOf(`\n## [${title}]`)
  if (start === -1) return undefined
  const body = changelog.slice(changelog.indexOf("\n", start + 1) + 1)
  const end = body.indexOf("\n## [")
  return (end === -1 ? body : body.slice(0, end)).trim()
}

function newer(version: string, than: string): boolean {
  const [a, b] = [version, than].map((each) => each.split(".").map(Number))
  for (let index = 0; index < 3; index++)
    if ((a?.[index] ?? 0) !== (b?.[index] ?? 0)) return (a?.[index] ?? 0) > (b?.[index] ?? 0)
  return false
}

async function bump(version: string | undefined) {
  if (version === undefined || !SEMVER.test(version))
    fail("Give the version as <major>.<minor>.<patch>, such as 0.1.0")
  const changelog = await Bun.file(CHANGELOG).text()
  const was = await current()
  if (was === version && section(changelog, version) !== undefined) {
    console.log(`Version ${version} is already set and titled in ${CHANGELOG}; nothing to do`)
    return
  }
  if (!newer(version, was))
    fail(`${version} is not above the manifests' version ${was}; pick a higher one`)
  if (!/^- /m.test(section(changelog, "Unreleased") ?? ""))
    fail(`${CHANGELOG}: [Unreleased] lists no change; a release needs at least one entry`)
  const link = /^\[Unreleased\]: (\S+)\/compare\/v\S+\.\.\.HEAD$/m.exec(changelog)
  if (link === null)
    fail(`${CHANGELOG}: has no [Unreleased] compare link; add one as Keep a Changelog shows`)
  const date = new Date().toISOString().slice(0, 10)
  const titled = changelog
    .replace("\n## [Unreleased]\n", `\n## [Unreleased]\n\n## [${version}] - ${date}\n`)
    .replace(
      link[0],
      `[Unreleased]: ${link[1]}/compare/v${version}...HEAD\n[${version}]: ${link[1]}/releases/tag/v${version}`,
    )
  const bumped = new Map<string, string>()
  for (const path of MANIFESTS) {
    const text = await Bun.file(path).text()
    const next = text.replace(`"version": "${was}"`, `"version": "${version}"`)
    if (next === text)
      fail(`${path}: holds no "version": "${was}" line; set it as the other manifests do`)
    bumped.set(path, next)
  }
  for (const [path, text] of bumped) await Bun.write(path, text)
  await Bun.write(CHANGELOG, titled)
  console.log(`Set version ${version} and titled [Unreleased] as [${version}] - ${date}`)
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
    await $`git log -1 --format=%H -G${'"version":'} -- ${MANIFESTS[0]}`.text()
  ).trim()
  if (commit === "")
    fail(`${MANIFESTS[0]}: no commit in this clone sets its version; fetch main's full history`)
  await $`gh release create ${tag} --target ${commit} --title ${tag} --prerelease=${prerelease} --notes-file - < ${new Response(body)}`
  console.log(`Published ${tag} on ${commit} as a ${kind}`)
}

const [command, argument] = process.argv.slice(2)
if (command === "bump") await bump(argument)
else if (command === "notes") console.log(await notes())
else if (command === "publish") await publish(argument === "--dry-run")
else fail("Run bump <version>, notes or publish [--dry-run]")
