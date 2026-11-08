/**
 * The files a script reads from the checkout and the problems it finds in them: a file's bytes or a symlink, the reading
 * of a file into a value or a problem, the walk through that value's nested tables, and a parse that runs once per file.
 */
import { isUtf8 } from "node:buffer"
import { constants } from "node:fs"
import { access, lstat, readFile } from "node:fs/promises"
import { join } from "node:path"
import { isCollection, isPair, parseDocument, visit } from "yaml"

/** The files the check reads, by repository path: their bytes, or a symlink, whose target it never reads. */
export type Tree = ReadonlyMap<string, Uint8Array | "symlink">

declare const problemBrand: unique symbol

/** One place that breaks one rule, and the fix: `<path>: <what is wrong>; <fix>`. */
export type Problem = string & { readonly [problemBrand]: true }

const parseCache = new WeakMap<object, Map<unknown, unknown>>()

/** An entry on disk that the check cannot read, whose message is the problem: its path and the fix. */
export class UnreadableEntry extends Error {}

/** A fault in a file that its format's parser takes, and its fix, which decode reports after the file's path. */
export class FileFault extends Error {}

// JSON.parse and Bun's YAML parser would each read a repeated key as its last value.
const REPEATED_KEY = "repeats a key in one table; keep one"
// v0.0.2 read JSON through pydantic-core, which refuses a value inside more than 200 arrays and objects, the outermost
// included, and YAML and TOML are held to the same depth, counted on the value each parser builds.
export const MOST_LEVELS = 200
export const TOO_DEEP = `nests values more than ${MOST_LEVELS} levels deep; flatten them`
// Bun's TOML parser crashes the process, rather than throwing, on inline tables nested 32743 levels deep under a 64 MB
// stack on macOS, its shallowest crash, and each level takes at least one character, so TOML this long cannot reach it.
// Set when nustack's longest TOML file held 1195 characters, the cap refuses a longer file however shallow it nests.
const MOST_TOML_CHARACTERS = 16384

export async function readEntry(
  root: string,
  path: string,
): Promise<Uint8Array | "symlink" | undefined> {
  const stat = await lstat(join(root, path)).catch(async (error: unknown) => {
    const code = isObject(error) ? error.code : undefined
    if (code === "EACCES") throw new UnreadableEntry(await lockedFolder(root, path))
    if (code === "ENOTDIR") throw new UnreadableEntry(await folderInPlace(root, path))
    return rethrowUnlessMissing(error)
  })
  if (stat === undefined || stat.isDirectory()) return undefined
  if (stat.isSymbolicLink()) return "symlink"
  if (!stat.isFile()) throw new UnreadableEntry(neither(path))
  const bytes = await readFile(join(root, path)).catch((error: unknown) => {
    if (!isObject(error) || error.code !== "EACCES") throw error
    throw new UnreadableEntry(`${path}: cannot be read (Permission denied); make it readable`)
  })
  return new Uint8Array(bytes)
}

export function cannotOpen(folder: string): string {
  return `${folder}: cannot be opened (Permission denied); give the folder read and execute permission`
}

export function neither(path: string): string {
  return `${path}: is neither a file nor a folder; remove it`
}

export function neitherInFolderPlace(folder: string): string {
  return `${folder}: is neither a file nor a folder; remove it, then add the folder`
}

// The folders on a path, outermost first.
function folders(path: string): string[] {
  const parts = path.split("/").slice(0, -1)
  return parts.map((_part, index) => parts.slice(0, index + 1).join("/"))
}

async function lockedFolder(root: string, path: string): Promise<string> {
  for (const folder of folders(path)) {
    const opened = await access(join(root, folder), constants.R_OK | constants.X_OK).then(
      () => true,
      () => false,
    )
    if (!opened) return cannotOpen(folder)
  }
  throw new Error(`${path}: lstat is denied, yet every folder on its path opens`)
}

export async function folderInPlace(root: string, path: string): Promise<string> {
  for (const folder of folders(path)) {
    const stat = await lstat(join(root, folder))
    if (stat.isFile())
      return `${folder}: is a file where a folder belongs; move the file, then add the folder`
    if (!stat.isDirectory()) return neitherInFolderPlace(folder)
  }
  throw new Error(`${path}: lstat finds no folder, yet every folder on its path is one`)
}

// A parsed value comes back in a one-item list, so no value read from a file passes as a problem. The bytes are decoded
// with any byte order mark kept, so each format's parser decides whether to read past it.
export function decode<T = unknown>(
  tree: Tree,
  path: string,
  parser: (text: string) => T = parseJson as (text: string) => T,
): [T] | { problem: Problem } {
  const bytes = tree.get(path)
  if (bytes === "symlink") return { problem: symlinkProblem(path) }
  if (bytes === undefined) return { problem: problem(`${path}: is missing; restore it`) }
  return once(bytes, parser, () => {
    if (!isUtf8(bytes)) return { problem: problem(`${path}: is not valid UTF-8; save it as UTF-8`) }
    try {
      return [parser(new TextDecoder("utf-8", { ignoreBOM: true }).decode(bytes))] as [T]
    } catch (error) {
      if (error instanceof FileFault) return { problem: problem(`${path}: ${error.message}`) }
      if (error instanceof SyntaxError)
        return { problem: problem(`${path}: does not parse as its format; fix its syntax`) }
      throw error
    }
  })
}

export function problem(text: string): Problem {
  return text as Problem
}

export function symlinkProblem(path: string): Problem {
  return problem(`${path}: is a symlink; put the file itself there`)
}

// JSON is YAML 1.2, so once JSON.parse takes the text, yaml's parse of it differs only where a table repeats a key;
// any other difference is a bug to surface, not a problem in the file. JSON.parse builds a value of any depth without
// running out of stack, so the walk alone bounds it.
export function parseJson(text: string): unknown {
  const value: unknown = JSON.parse(text)
  if (nestsTooDeep(value)) throw new FileFault(TOO_DEEP)
  const document = parseDocument(text, { uniqueKeys: true })
  const issues = [...document.errors, ...document.warnings]
  if (issues.length > 0 && issues.every(({ code }) => code === "DUPLICATE_KEY"))
    throw new FileFault(REPEATED_KEY)
  if (issues.length > 0)
    throw new Error("yaml refuses JSON that JSON.parse takes", { cause: issues[0] })
  return value
}

// yaml warns, rather than errs, on a %YAML version other than 1.1 or 1.2 and on a tag it cannot resolve, so each
// warning refuses the file too. It reads past a byte order mark, as YAML lets a stream start with one:
// https://yaml.org/spec/1.2.2/#52-character-encodings
// Without resolveKnownTags, YAML 1.1's tags, such as !!set and !!binary, are tags it cannot resolve. Integers come
// back as bigints, so none reaches a caller rounded: a safe one turns back into a number, and any other is refused.
// A JavaScript object key is a string, so a key that is a list or mapping is refused.
// yaml reports a stack overflow while it builds a collection as RESOURCE_EXHAUSTION, so that error, like a stack
// overflow in the steps after it, reads as too deep: https://github.com/eemeli/yaml/blob/v2.9.1/src/compose/compose-node.ts
export function parseYaml(text: string): unknown {
  const document = parseDocument(text, {
    uniqueKeys: true,
    resolveKnownTags: false,
    intAsBigInt: true,
  })
  const issues = [...document.errors, ...document.warnings]
  if (issues.some(({ code }) => code === "RESOURCE_EXHAUSTION")) throw new FileFault(TOO_DEEP)
  if (issues.length > 0 && issues.every(({ code }) => code === "DUPLICATE_KEY"))
    throw new FileFault(REPEATED_KEY)
  if (issues.length > 0) throw new SyntaxError(issues[0]?.message)
  if (nodesTooDeep(document.contents)) throw new FileFault(TOO_DEEP)
  let value: unknown
  try {
    visit(document, {
      Pair(_key, pair) {
        if (isCollection(pair.key))
          throw new FileFault("holds a list or mapping as a key; use a scalar key")
      },
      Scalar(_key, scalar) {
        if (typeof scalar.value !== "bigint") return
        if (scalar.value > Number.MAX_SAFE_INTEGER || scalar.value < Number.MIN_SAFE_INTEGER)
          throw new FileFault("holds an integer outside ±(2^53-1); quote it as a string")
        scalar.value = Number(scalar.value)
      },
    })
    value = document.toJS()
  } catch (error) {
    if (overflowed(error)) throw new FileFault(TOO_DEEP)
    // An alias to an anchor that comes later, or to none, parses and fails only when the value is built.
    if (error instanceof ReferenceError) throw new SyntaxError(error.message)
    throw error
  }
  if (nestsTooDeep(value)) throw new FileFault(TOO_DEEP)
  return value
}

// TOML refuses a byte order mark, which Bun's parser reads past: https://toml.io/en/v1.0.0#spec
export function parseToml(text: string): unknown {
  if (text.startsWith("\uFEFF")) throw new SyntaxError("a byte order mark starts the file")
  if (text.length > MOST_TOML_CHARACTERS) {
    throw new FileFault(
      `holds more than ${MOST_TOML_CHARACTERS} characters, the most the TOML reader takes; shorten it`,
    )
  }
  let value: unknown
  try {
    value = Bun.TOML.parse(text)
  } catch (error) {
    if (overflowed(error)) throw new FileFault(TOO_DEEP)
    throw error
  }
  if (nestsTooDeep(value)) throw new FileFault(TOO_DEEP)
  return value
}

// yaml's visit takes time quadratic in a document's depth, so its nodes are counted first, with a stack of their own,
// counting collections as nestsTooDeep counts the arrays and objects they build.
function nodesTooDeep(root: unknown): boolean {
  const pending: [unknown, number][] = [[root, 0]]
  for (let next = pending.pop(); next !== undefined; next = pending.pop()) {
    const [node, level] = next
    if (isPair(node)) pending.push([node.key, level], [node.value, level])
    else if (isCollection(node)) {
      if (level >= MOST_LEVELS) return true
      for (const item of node.items) pending.push([item, level + 1])
    }
  }
  return false
}

/**
 * Whether a parsed value nests more than MOST_LEVELS arrays and objects deep, the outermost included, walked with a stack
 * of its own, so no depth overflows it. A value an alias shares is walked again only when reached deeper than before,
 * since a set of seen values would miss a deeper path to a value first reached shallow; each value is then walked at most
 * MOST_LEVELS times, and a cycle counts as too deep.
 */
export function nestsTooDeep(value: unknown): boolean {
  const deepest = new Map<object, number>()
  const pending: [unknown, number][] = [[value, 1]]
  for (let next = pending.pop(); next !== undefined; next = pending.pop()) {
    const [item, level] = next
    if (typeof item !== "object" || item === null || (deepest.get(item) ?? 0) >= level) continue
    if (level > MOST_LEVELS) return true
    deepest.set(item, level)
    for (const child of Object.values(item)) pending.push([child, level + 1])
  }
  return false
}

// A parser that recurses once per level throws this once a value outruns the stack, whose size depends on the host.
function overflowed(error: unknown): boolean {
  return error instanceof RangeError && error.message.startsWith("Maximum call stack size exceeded")
}

export function once<T>(owner: object, key: unknown, parse: () => T): T {
  let cache = parseCache.get(owner)
  if (cache === undefined) {
    cache = new Map()
    parseCache.set(owner, cache)
  }
  if (!cache.has(key)) cache.set(key, parse())
  return cache.get(key) as T
}

export function rethrowUnlessMissing(error: unknown): undefined {
  if (!isObject(error) || error.code !== "ENOENT") throw error
}

// The value at a path of nested tables, or undefined where a table on the way is missing or holds no table, so one
// problem names the setting to fix however much of its path is missing.
export function valueAt(value: unknown, keys: readonly string[]): unknown {
  return keys.reduce<unknown>((table, key) => (isObject(table) ? table[key] : undefined), value)
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}
