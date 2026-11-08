/**
 * The plugin's metadata files, each parsed once where it enters: the host manifests, the marketplaces,
 * plugin/package.json, pyproject.toml and CHANGELOG.md into a frozen value of the fields the check compares, beside a
 * problem for each field to fix, and the release workflow's tags, which the check compares with tag_format, into their
 * problems. readMetadata reads them all once per tree for the check. A problem repeats no value read from a file.
 */

import { decodeNamedCharacterReference } from "decode-named-character-reference"
import { micromark } from "micromark"
import { gfm, gfmHtml } from "micromark-extension-gfm"
import { decodeNumericCharacterReference } from "micromark-util-decode-numeric-character-reference"
import { type Markdown, markdown, type Span, within } from "./markdown.ts"
import { VERSION } from "./plugin.ts"
import { KEBAB, UPSTREAM } from "./record.ts"
import {
  decode,
  isObject,
  once,
  type Problem,
  parseToml,
  parseYaml,
  problem,
  type Tree,
  valueAt,
} from "./tree.ts"
import { RELEASE_WORKFLOW } from "./workflows.ts"

/** A host manifest, plugin/.<host>-plugin/plugin.json, which the hosts read as one plugin. */
export type Manifest = Readonly<{
  name: string
  version: string
  description: string
  author: Readonly<{ name: string }>
  homepage: string
  repository: string
  license: string
}>

/** A marketplace, which lists the plugin for its host. */
export type Marketplace = Readonly<{
  name: string
  owner: Readonly<{ name: string }>
  plugin: Readonly<{ name: string; description: string }>
  description: string
}>

/** plugin/package.json, by which OpenCode loads the plugin as the ES module its exports names. */
export type Package = Readonly<{ name: string; version: string }>

/** The pyproject.toml settings a release reads: [project] version, which cz bump sets with the manifests'. */
export type Pyproject = Readonly<{ version: string }>

/** CHANGELOG.md's latest release, the version its first release section titles. */
// latest is absent while no release is titled, as before the first.
export type Changelog = Readonly<{ latest?: string }>

/** The fields of a value that parsed, each kept only where it is well formed, so a file with a broken field still takes
 * part in every comparison its other fields allow. */
export type Found<T> = { readonly [K in keyof T]?: T[K] extends string ? T[K] : Found<T[K]> }

/** A file read into the fields that parsed and a problem for each that did not; with no problem, every field parsed. */
export type Read<T> = Readonly<{ found: Found<T>; problems: readonly Problem[] }>

/** Every metadata file of a tree, each parsed once, with the problems of every field that did not parse. */
export type Metadata = Readonly<{
  manifests: readonly Readonly<{ path: string; found: Found<Manifest> }>[]
  marketplaces: readonly Readonly<{ path: string; found: Found<Marketplace> }>[]
  pkg: Found<Package>
  pyproject: Found<Pyproject>
  // undefined where CHANGELOG.md does not read, which its own problem reports
  changelog: Found<Changelog> | undefined
  problems: readonly Problem[]
}>

// A text field's check, and the fix its problem gives when the check fails.
type TextRule = readonly [valid: (text: string) => boolean, fix: string]

// Claude Code's manifest stands for all three where one is enough, since make check holds them to the same fields.
export const CLAUDE_MANIFEST = "plugin/.claude-plugin/plugin.json"
export const MANIFESTS = Object.freeze([
  CLAUDE_MANIFEST,
  ...["cursor", "devin"].map((host) => `plugin/.${host}-plugin/plugin.json`),
])
// Cursor's marketplace holds its description under metadata; Claude Code's at the top.
export const MARKETPLACES = deepFreeze([
  { path: ".claude-plugin/marketplace.json", source: "./plugin", about: "description" },
  { path: ".cursor-plugin/marketplace.json", source: "plugin", about: "metadata" },
] as const)
export const PACKAGE = "plugin/package.json"
export const PYPROJECT = "pyproject.toml"
export const CHANGELOG = "CHANGELOG.md"
// cz bump sets the version in each file version_files lists, and finds the last release by tag_format:
// https://commitizen-tools.github.io/commitizen/config/bump/
export const VERSION_FILES = Object.freeze(
  [...MANIFESTS, PACKAGE].map((path) => `${path}:version`).sort(),
)
// The loader's SkillFile.BLANK, which plugin/opencode.ts must hold itself, since nothing outside plugin/ reaches a
// user, and which the check cannot import before it knows plugin/package.json lets the loader load; a test keeps both
// the same.
export const BLANK =
  /^[\t\n\v\f\r \x85\xa0\u1680\u2000-\u200d\u2028\u2029\u202f\u205f\u2060\u3000\ufeff]*$/
const FILLED: TextRule = Object.freeze([(text: string) => !BLANK.test(text), "fill it in"])
const KEBAB_CASE: TextRule = Object.freeze([
  (text: string) => KEBAB.test(text),
  "set it in kebab case",
])
const SEMVER: TextRule = Object.freeze([
  (text: string) => VERSION.test(text),
  "set it as <major>.<minor>.<patch>",
])
// The longest URL v0.0.2 took, pydantic's HttpUrl limit, after which some browsers cut a URL off.
const URL_LENGTH = 2083
// The manifest's fields in the order its hosts document them, each with its check and its fix.
const MANIFEST_FIELDS = deepFreeze({
  name: KEBAB_CASE,
  version: SEMVER,
  description: FILLED,
  author: [FILLED[0], "give the author's name, and only that"],
  homepage: [
    (text: string) => /^https:\/\/\S+$/.test(text) && text.length <= URL_LENGTH,
    `set it to an https URL of at most ${URL_LENGTH} characters`,
  ],
  repository: [(text: string) => UPSTREAM.test(text), "set it to https://<host>/<owner>/<name>"],
  license: FILLED,
} as const satisfies Record<keyof Manifest, TextRule>)
// satisfies holds the table to exactly the manifest's fields, so its keys are those.
export const MANIFEST_KEYS = Object.freeze(Object.keys(MANIFEST_FIELDS) as (keyof Manifest)[])

// Of the elements GitHub keeps, only an image shows without text, a details element shows the summary it always has,
// and GitHub shows each tag GFM disallows as text:
// https://github.com/gjtorikian/html-pipeline/blob/v2.14.3/lib/html/pipeline/sanitization_filter.rb
// https://html.spec.whatwg.org/multipage/interactive-elements.html#the-details-element
// https://github.github.com/gfm/#disallowed-raw-html-extension-
const SHOWN_TAG =
  /<(?:img|details|title|textarea|style|xmp|iframe|noembed|noframes|script|plaintext)[\s/>]/i

/** Reads one parsed file's fields, keeping a problem for each that is missing, malformed or unknown. */
class Fields {
  readonly problems: Problem[] = []

  constructor(readonly path: string) {}

  // An object that is not one gives that problem alone, and no field of it is read.
  object(
    value: unknown,
    keys: readonly string[],
    at = "",
  ): Readonly<Record<string, unknown>> | undefined {
    const where = at === "" ? "" : `${at} `
    if (!isObject(value)) {
      this.problems.push(problem(`${this.path}: ${where}is not an object; make it one`))
      return undefined
    }
    if (Object.keys(value).some((key) => !keys.includes(key)))
      this.problems.push(
        problem(`${this.path}: ${where}holds a field besides ${keys.join(", ")}; drop it`),
      )
    return value
  }

  // An object that holds only a name, such as an author or an owner, gives one problem for any break.
  named(value: unknown, field: string, rule: TextRule): { name: string } | undefined {
    const name =
      isObject(value) && Bun.deepEquals(Object.keys(value), ["name"]) ? value.name : undefined
    return named(this.text(name, field, rule))
  }

  text(value: unknown, field: string, [valid, fix]: TextRule): string | undefined {
    if (typeof value === "string" && valid(value)) return value
    this.problems.push(problem(`${this.path}: ${field} is missing or malformed; ${fix}`))
  }

  holds(holds: boolean, wrong: string): void {
    if (!holds) this.problems.push(problem(`${this.path}: ${wrong}`))
  }

  done<T>(found: Found<T>): Read<T> {
    return deepFreeze({ found: defined(found), problems: this.problems })
  }
}

export function readMetadata(tree: Tree): Metadata {
  return once(tree, readMetadata, () => {
    const manifests = MANIFESTS.map((path) => ({ path, ...readManifest(tree, path) }))
    const marketplaces = MARKETPLACES.map((host) => ({
      path: host.path,
      ...readMarketplace(tree, host),
    }))
    const [pkg, pyproject, changelog] = [
      readPackage(tree),
      readPyproject(tree),
      readChangelog(tree),
    ]
    const problems = [...manifests, pyproject, pkg, ...marketplaces, changelog].flatMap(
      (read) => read.problems,
    )
    problems.push(...releaseTagsProblems(tree))
    return deepFreeze({
      manifests: manifests.map(({ path, found }) => ({ path, found })),
      marketplaces: marketplaces.map(({ path, found }) => ({ path, found })),
      pkg: pkg.found,
      pyproject: pyproject.found,
      changelog: changelog.problems.length > 0 ? undefined : changelog.found,
      problems,
    })
  })
}

export function parseManifest(tree: Tree, path: string): Manifest | Problem[] {
  return whole(readManifest(tree, path))
}

export function readManifest(tree: Tree, path: string): Read<Manifest> {
  const read = decode(tree, path)
  if (!Array.isArray(read)) return unread(read.problem)
  const fields = new Fields(path)
  const manifest = fields.object(read[0], MANIFEST_KEYS)
  if (manifest === undefined) return fields.done({})
  const text = (field: Exclude<keyof Manifest, "author">) =>
    fields.text(manifest[field], field, MANIFEST_FIELDS[field])
  return fields.done<Manifest>({
    name: text("name"),
    version: text("version"),
    description: text("description"),
    author: fields.named(manifest.author, "author", MANIFEST_FIELDS.author),
    homepage: text("homepage"),
    repository: text("repository"),
    license: text("license"),
  })
}

export function readMarketplace(
  tree: Tree,
  host: (typeof MARKETPLACES)[number],
): Read<Marketplace> {
  const { path, source } = host
  const read = decode(tree, path)
  if (!Array.isArray(read)) return unread(read.problem)
  const fields = new Fields(path)
  const market = fields.object(read[0], ["name", "owner", "plugins", host.about])
  if (market === undefined) return fields.done({})
  const name = fields.text(market.name, "name", KEBAB_CASE)
  const owner = fields.named(market.owner, "owner", [
    FILLED[0],
    "give the owner's name, and only that",
  ])
  const plugins: unknown[] = Array.isArray(market.plugins) ? market.plugins : []
  if (!Array.isArray(market.plugins))
    fields.holds(false, "plugins is not a list; list the plugin in it")
  else fields.holds(plugins.length > 0, "plugins does not list the plugin; list it")
  fields.holds(plugins.length < 2, "plugins lists more than the plugin; list only the plugin")
  const listed =
    plugins.length > 0
      ? fields.object(plugins[0], ["name", "description", "source"], "plugins' entry")
      : undefined
  if (listed !== undefined)
    fields.holds(listed.source === source, `plugins' source is not ${source}; set it to that`)
  const plugin = listed && {
    name: fields.text(listed.name, "plugins' name", KEBAB_CASE),
    description: fields.text(listed.description, "plugins' description", FILLED),
  }
  const [about, field] =
    host.about === "metadata"
      ? [fields.object(market.metadata, ["description"], "metadata"), "metadata description"]
      : [{ description: market.description }, "description"]
  const description = about && fields.text(about.description, field, FILLED)
  return fields.done<Marketplace>({
    name,
    owner,
    plugin,
    description,
  })
}

export function parsePackage(tree: Tree): Package | Problem[] {
  return whole(readPackage(tree))
}

export function readPackage(tree: Tree): Read<Package> {
  const read = decode(tree, PACKAGE)
  if (!Array.isArray(read)) return unread(read.problem)
  const fields = new Fields(PACKAGE)
  const pkg = fields.object(read[0], ["name", "version", "type", "exports"])
  if (pkg === undefined) return fields.done({})
  const name = fields.text(pkg.name, "name", KEBAB_CASE)
  const version = fields.text(pkg.version, "version", SEMVER)
  fields.holds(pkg.type === "module", 'type is not module; set it to "module"')
  fields.holds(
    Bun.deepEquals(pkg.exports, { ".": "./opencode.ts" }, true),
    'exports does not name the loader; set it to { ".": "./opencode.ts" }',
  )
  return fields.done<Package>({ name, version })
}

// pyproject.toml holds other tools' settings too, which those tools check, so this reads only the fields it names.
export function readPyproject(tree: Tree): Read<Pyproject> {
  const read = decode(tree, PYPROJECT, parseToml)
  if (!Array.isArray(read)) return unread(read.problem)
  const fields = new Fields(PYPROJECT)
  const version = fields.text(valueAt(read[0], ["project", "version"]), "[project] version", SEMVER)
  const listed = valueAt(read[0], ["tool", "commitizen", "version_files"])
  fields.holds(
    Array.isArray(listed) && Bun.deepEquals([...listed].sort(), VERSION_FILES),
    `[tool.commitizen] version_files is not the files whose version the check compares; list each of ${VERSION_FILES.join(", ")} once`,
  )
  fields.holds(
    valueAt(read[0], ["tool", "commitizen", "tag_format"]) === "v$version",
    "[tool.commitizen] tag_format is not the release tags' form; set it to v$version",
  )
  return fields.done<Pyproject>({ version })
}

// The latest release is the first ## heading that links a version by its label, as Keep a Changelog orders them
// (https://keepachangelog.com/en/1.1.0/) and the release titles them; a changelog with none has no latest release,
// which the check finds when it compares that with the manifests' version. A heading that names a version in brackets
// with no definition of its label renders as text and links no release, so it is refused rather than skipped. Releases
// titled with a version and a day run newest first, by version and by date, as Keep a Changelog lists them.
export function readChangelog(tree: Tree): Read<Changelog> {
  const read = decode(tree, CHANGELOG, markdown)
  if (!Array.isArray(read)) return unread(read.problem)
  const releases = read[0].headings.filter(
    ({ depth, text }) => depth === 2 && text.startsWith("[") && !text.startsWith("[Unreleased]"),
  )
  const fields = new Fields(CHANGELOG)
  fields.holds(
    releases.every(({ reference }) => reference !== undefined),
    "a ## heading names a version in brackets whose label no definition defines; define it, as the release titles it",
  )
  const titled = releases.flatMap(({ reference, text }) => {
    const date = /^\[[^\]]*\] - (\d{4}-\d{2}-\d{2})$/.exec(text)?.[1]
    return reference !== undefined && VERSION.test(reference) && date !== undefined
      ? [{ version: reference, date }]
      : []
  })
  for (const [at, below] of titled.entries()) {
    const above = titled[at - 1]
    if (above === undefined) continue
    fields.holds(
      !newer(below.version, above.version),
      `has the entry for ${above.version} above the one for ${below.version}; list releases newest first, by version`,
    )
    fields.holds(
      above.date >= below.date,
      `has the entry dated ${above.date} above the one dated ${below.date}; list releases newest first, by date`,
    )
  }
  const latest = releases.find(({ reference }) => reference !== undefined)
  if (latest?.reference !== undefined) fields.problems.push(...entryProblems(read[0], latest))
  return fields.done<Changelog>({ latest: latest?.reference })
}

// The release page copies a release's entry outside the repository, where a relative link breaks and a reference
// defined elsewhere in the file reads differently, so each link and image the entry renders has a full URL, each
// reference it uses is defined inside it, and each of its ### groups shows something. The check holds the latest
// release to this, and notes the one it copies.
export function entryProblems(read: Markdown, heading: Markdown["headings"][number]): Problem[] {
  const name = `the entry for ${heading.reference}`
  const next = read.headings.find(({ depth, start }) => depth <= 2 && start > heading.start)
  const entry: Span = { start: heading.lines.end, end: next?.start ?? read.text.length }
  const problems: Problem[] = []
  const used = [
    ...read.links.flatMap(({ definition, ...link }) =>
      definition !== undefined && within(link, entry) ? [definition] : [],
    ),
    ...read.footnotes.flatMap(({ definition, ...note }) =>
      within(note, entry) ? [definition] : [],
    ),
  ]
  if (used.some((definition) => !within(definition, entry)))
    problems.push(
      problem(
        `${CHANGELOG}: uses a reference in ${name} that is defined elsewhere in the file, so it reads differently on the release page; define it inside ${name}, under a label no other definition in the file uses`,
      ),
    )
  const relative = read.links.filter(
    (link) => within(link, entry) && !/^[a-z][a-z\d+.-]*:|^\/\//i.test(link.destination),
  )
  for (const destination of new Set(relative.map((link) => link.destination)))
    problems.push(
      problem(
        `${CHANGELOG}: links ${destination} from ${name}, which the release page copies, where a relative link breaks; link it by its full URL`,
      ),
    )
  const groups = read.headings.filter(
    ({ depth, start }) => depth === 3 && within({ start, end: start }, entry),
  )
  for (const group of groups) {
    const after = read.headings.find(({ depth, start }) => depth <= 3 && start > group.start)
    const body = read.text.slice(group.lines.end, after?.start ?? entry.end)
    if (!shows(body))
      problems.push(
        problem(
          `${CHANGELOG}: shows nothing in the ${group.text} group of ${name}; list its changes under it, or remove it`,
        ),
      )
  }
  return problems
}

// Whether Markdown, rendered as GitHub renders it, shows anything: text that is not blank once its character references
// are decoded, an image or a tag GitHub shows. A comment shows nothing, and nor does any other tag of itself, such as a
// thematic break, a task item's checkbox or an empty list item or table cell, though GitHub may draw it.
function shows(text: string): boolean {
  const html = micromark(text, {
    allowDangerousHtml: true,
    extensions: [gfm()],
    htmlExtensions: [gfmHtml()],
  }).replace(/<!--[\s\S]*?(?:-->|$)/g, "")
  if (SHOWN_TAG.test(html)) return true
  const shown = html
    .replace(/<[^>]*>/g, "")
    .replace(/&(?:#(\d+)|#x([\da-f]+)|(\w+));/gi, (reference, decimal, hex, name) =>
      decimal !== undefined || hex !== undefined
        ? decodeNumericCharacterReference(decimal ?? hex, decimal === undefined ? 16 : 10)
        : decodeNamedCharacterReference(name) || reference,
    )
  return !BLANK.test(shown)
}

// The release workflow holds GitHub Actions' other keys, which actionlint checks, and its jobs, which workflows.ts checks,
// so this reads only on.push.tags; the workflows rule reports a release workflow that does not parse.
export function releaseTagsProblems(tree: Tree): Problem[] {
  const read = decode(tree, RELEASE_WORKFLOW, parseYaml)
  if (!Array.isArray(read)) return []
  const fields = new Fields(RELEASE_WORKFLOW)
  fields.holds(
    Bun.deepEquals(valueAt(read[0], ["on", "push", "tags"]), ["v*"]),
    'on.push.tags is not ["v*"], the tags tag_format gives; set it to that',
  )
  return fields.problems
}

// With no problem every field parsed, so the found fields are the whole value.
function whole<T>({ found, problems }: Read<T>): T | Problem[] {
  return problems.length > 0 ? [...problems] : (found as T)
}

// Whether one <major>.<minor>.<patch> version is newer than another, comparing each part as a BigInt, since a part can
// hold more digits than a number holds exactly.
function newer(version: string, than: string): boolean {
  const others = than.split(".").map(BigInt)
  for (const part of version.split(".").map(BigInt)) {
    const other = others.shift()
    if (other === undefined || part !== other) return other === undefined || part > other
  }
  return false
}

function named(name: string | undefined): { name: string } | undefined {
  return name === undefined ? undefined : { name }
}

function unread<T>(problem: Problem): Read<T> {
  return deepFreeze({ found: {}, problems: [problem] })
}

// Drops each top-level field that did not parse, so a Found value lists only the fields the file gives.
function defined<T extends object>(value: T): T {
  return Object.fromEntries(Object.entries(value).filter(([, field]) => field !== undefined)) as T
}

function deepFreeze<T extends object>(value: T): T {
  for (const field of Object.values(value)) if (typeof field === "object") deepFreeze(field)
  return Object.freeze(value)
}
