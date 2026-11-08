/**
 * The plugin's metadata files, which hold one name and version: the host manifests, plugin/package.json,
 * pyproject.toml and the marketplaces. The release reads the plugin from them, and the check's metadata rule holds them
 * to one another. A problem repeats no value read from a file.
 */
import { VERSION } from "./plugin.ts"
import { KEBAB } from "./record.ts"
import { decode, isObject, type Problem, parseToml, problem, type Tree, valueAt } from "./tree.ts"

/** The plugin's manifest fields a release reads. */
export type Plugin = Readonly<Record<"name" | "version" | "description" | "repository", string>>

/** plugin/package.json's fields, by which OpenCode loads the plugin under its name and version. */
export type Package = Readonly<{ name: string; version: string }>

// Claude Code's manifest stands for all three, since the check holds them to the same JSON.
export const CLAUDE_MANIFEST = "plugin/.claude-plugin/plugin.json"
export const MANIFESTS = Object.freeze([
  CLAUDE_MANIFEST,
  ...["cursor", "devin"].map((host) => `plugin/.${host}-plugin/plugin.json`),
])
export const MARKETPLACES = Object.freeze([
  ".claude-plugin/marketplace.json",
  ".cursor-plugin/marketplace.json",
])
export const PACKAGE = "plugin/package.json"
export const PYPROJECT = "pyproject.toml"

export function parseManifest(tree: Tree, path: string): Plugin | Problem[] {
  const read = decode(tree, path)
  if (!Array.isArray(read)) return [read.problem]
  const [manifest] = read
  const { name, version, description, repository } = isObject(manifest) ? manifest : {}
  const problems = [
    ...textProblems(path, { description, repository }),
    ...(typeof name === "string" && KEBAB.test(name)
      ? []
      : [problem(`${path}: name is missing or not in kebab case; set it in kebab case`)]),
    ...versionProblems(path, version),
  ]
  if (problems.length > 0) return problems
  return Object.freeze({ name, version, description, repository } as Plugin)
}

export function parsePackage(tree: Tree): Package | Problem[] {
  const read = decode(tree, PACKAGE)
  if (!Array.isArray(read)) return [read.problem]
  const [pkg] = read
  const { name, version } = isObject(pkg) ? pkg : {}
  const problems = [...textProblems(PACKAGE, { name }), ...versionProblems(PACKAGE, version)]
  if (problems.length > 0) return problems
  return Object.freeze({ name, version } as Package)
}

// The host manifests are one JSON value, so a field one host reads differently from another cannot ship; the other
// files hold their name and version, and each marketplace lists the plugin by that name.
export function metadataProblems(tree: Tree): Problem[] {
  const reference = decode(tree, CLAUDE_MANIFEST)
  const problems = MANIFESTS.slice(1).flatMap((path) => {
    const read = decode(tree, path)
    if (!Array.isArray(read)) return [read.problem]
    if (Array.isArray(reference) && !Bun.deepEquals(read[0], reference[0], true))
      return [problem(`${path}: differs from ${CLAUDE_MANIFEST}; make every manifest the same`)]
    return []
  })
  const plugin = parseManifest(tree, CLAUDE_MANIFEST)
  if (Array.isArray(plugin)) return [...problems, ...plugin]
  const pkg = parsePackage(tree)
  if (Array.isArray(pkg)) problems.push(...pkg)
  else if (pkg.name !== plugin.name || pkg.version !== plugin.version)
    problems.push(problem(`${PACKAGE}: name or version is not the manifests'; set both`))
  const pyproject = decode(tree, PYPROJECT, parseToml)
  if (!Array.isArray(pyproject)) problems.push(pyproject.problem)
  else if (valueAt(pyproject[0], ["project", "version"]) !== plugin.version)
    problems.push(
      problem(`${PYPROJECT}: [project] version is not the manifests'; set it to theirs`),
    )
  for (const path of MARKETPLACES) {
    const read = decode(tree, path)
    if (!Array.isArray(read)) problems.push(read.problem)
    else {
      const plugins = valueAt(read[0], ["plugins"])
      const listed =
        Array.isArray(plugins) && plugins.some((entry) => valueAt(entry, ["name"]) === plugin.name)
      if (!listed)
        problems.push(
          problem(`${path}: plugins does not list the manifests' name; list the plugin by it`),
        )
    }
  }
  return problems
}

function textProblems(path: string, fields: Record<string, unknown>): Problem[] {
  return Object.entries(fields).flatMap(([field, value]) =>
    typeof value === "string" && value.trim() !== ""
      ? []
      : [problem(`${path}: ${field} is missing or empty; fill it in`)],
  )
}

function versionProblems(path: string, version: unknown): Problem[] {
  if (typeof version === "string" && VERSION.test(version)) return []
  return [problem(`${path}: version is missing or malformed; set it as <major>.<minor>.<patch>`)]
}
