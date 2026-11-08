/**
 * The files a script reads from the checkout and the problems it finds in them: a file's bytes or a symlink, the reading
 * of a file into a value or a problem, the walk through that value's nested tables, and a parse that runs once per file.
 * A file that does not parse is a problem; the commit hooks check-json, check-yaml and check-toml name what is wrong.
 */
import { isUtf8 } from "node:buffer"
import { lstat, readFile } from "node:fs/promises"
import { join } from "node:path"

/** The files the check reads, by repository path: their bytes, or a symlink, whose target it never reads. */
export type Tree = ReadonlyMap<string, Uint8Array | "symlink">

declare const problemBrand: unique symbol

/** One place that breaks one rule, and the fix: `<path>: <what is wrong>; <fix>`. */
export type Problem = string & { readonly [problemBrand]: true }

const parseCache = new WeakMap<object, Map<unknown, unknown>>()

// Bun's YAML and TOML parsers recurse once per level: on Linux's 8 MB stack YAML nested about 5000 levels deep throws
// a stack overflow, and on the 64 MB stack macOS gives make, a value nested tens of thousands of levels deep crashes the
// process instead of throwing. So text is refused before it is parsed, the same way on any stack, when it is longer than
// any of the repository's YAML or TOML files needs, or when a line may sit more than 200 levels deep, the loader's own
// limit. A line's depth is counted high: the brackets and braces left open before it, with no regard to quoting or
// comments and never below zero, plus two levels per column of indent and one, plus one per block indicator on the line,
// a -, ? or : followed by a space or the line's end. Each level of YAML's block nesting takes a column of indent or an
// indicator, and each level of YAML's flow nesting or of TOML's arrays and inline tables a bracket or brace, so the count
// bounds those; Bun parses TOML's dotted keys and table headers without deep recursion, so the count leaves them be. A
// stack overflow the parser throws anyway is refused as the same fault.
export const MOST_CHARACTERS = 16384
export const MOST_LEVELS = 200

class TooLong extends Error {}
class TooDeep extends Error {}

export function nestsTooDeep(text: string): boolean {
  let depth = 0
  for (const line of text.split("\n")) {
    const indent = line.length - line.trimStart().length
    const indicators = line.match(/[-?:](?=\s|$)/g)?.length ?? 0
    if (depth + 2 * (indent + 1) + indicators > MOST_LEVELS) return true
    for (const character of line) {
      if (character === "[" || character === "{") depth += 1
      else if (character === "]" || character === "}") depth = Math.max(0, depth - 1)
      if (depth > MOST_LEVELS) return true
    }
  }
  return false
}

function overflowed(error: unknown): boolean {
  return error instanceof RangeError && error.message.startsWith("Maximum call stack size exceeded")
}

export function capped<T>(parser: (text: string) => T): (text: string) => T {
  return (text) => {
    if (text.length > MOST_CHARACTERS) throw new TooLong()
    if (nestsTooDeep(text)) throw new TooDeep()
    try {
      return parser(text)
    } catch (error) {
      if (overflowed(error)) throw new TooDeep()
      throw error
    }
  }
}

export const parseYaml = capped(Bun.YAML.parse)
export const parseToml = capped(Bun.TOML.parse)

export async function readEntry(
  root: string,
  path: string,
): Promise<Uint8Array | "symlink" | undefined> {
  const stat = await lstat(join(root, path)).catch(rethrowUnlessMissing)
  if (stat?.isSymbolicLink()) return "symlink"
  if (!stat?.isFile()) return undefined
  return new Uint8Array(await readFile(join(root, path)))
}

// A parsed value comes back in a one-item list, so no value read from a file passes as a problem.
export function decode<T = unknown>(
  tree: Tree,
  path: string,
  parser: (text: string) => T = JSON.parse,
): [T] | { problem: Problem } {
  const bytes = tree.get(path)
  if (bytes === "symlink") return { problem: symlinkProblem(path) }
  if (bytes === undefined) return { problem: problem(`${path}: is missing; restore it`) }
  return once(bytes, parser, () => {
    if (!isUtf8(bytes)) return { problem: problem(`${path}: is not valid UTF-8; save it as UTF-8`) }
    try {
      return [parser(new TextDecoder("utf-8", { ignoreBOM: true }).decode(bytes))] as [T]
    } catch (error) {
      if (error instanceof SyntaxError)
        return { problem: problem(`${path}: does not parse as its format; fix its syntax`) }
      if (error instanceof TooLong)
        return {
          problem: problem(
            `${path}: holds more than ${MOST_CHARACTERS} characters, the most Bun's parser reads safely; shorten it`,
          ),
        }
      if (error instanceof TooDeep)
        return {
          problem: problem(
            `${path}: may nest more than ${MOST_LEVELS} levels deep, the most Bun's parser reads safely; flatten it`,
          ),
        }
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
