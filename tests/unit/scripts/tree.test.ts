/**
 * readEntry reads a path as a file's bytes or a symlink, and as nothing where it holds no file; decode reads a file
 * of the tree into a value or one problem, parsing each file once, and throws a parser's error other than a syntax
 * error, so the script fails; problem() alone builds a problem;
 * rethrowUnlessMissing passes only ENOENT; valueAt reads a value through nested tables, of which isObject takes only a
 * non-array object.
 */
import { afterEach, expect, test } from "bun:test"
import { mkdir, symlink, writeFile } from "node:fs/promises"
import { join } from "node:path"
import {
  capped,
  decode,
  isObject,
  nestsTooDeep,
  once,
  type Problem,
  parseToml,
  parseYaml,
  problem,
  readEntry,
  rethrowUnlessMissing,
  valueAt,
} from "../../../scripts/tree.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"

const folders = new TemporaryFolders()
afterEach(() => folders.clear())

const encoded = (text: string) => new TextEncoder().encode(text)

test("reads a file's bytes, a symlink as one, and and a folder, a fifo or a missing path as no file", async () => {
  const root = await folders.make()
  await writeFile(join(root, "f"), "x")
  await symlink("f", join(root, "l"))
  await mkdir(join(root, "d"))
  expect(Bun.spawnSync(["mkfifo", join(root, "p")]).exitCode).toBe(0)
  const read = await Promise.all(["f", "l", "d", "p", "gone"].map((path) => readEntry(root, path)))
  expect(read).toEqual([encoded("x"), "symlink", undefined, undefined, undefined])
})

test("decodes a file's JSON into a one-item list", () => {
  expect(decode(new Map([["a.json", encoded('{"a":1}')]]), "a.json")).toEqual([{ a: 1 }])
})

test.each([
  [new Map(), "a.json: is missing; restore it"],
  [new Map([["a.json", "symlink" as const]]), "a.json: is a symlink; put the file itself there"],
  [new Map([["a.json", new Uint8Array([0xff])]]), "a.json: is not valid UTF-8; save it as UTF-8"],
  [new Map([["a.json", encoded("{")]]), "a.json: does not parse as its format; fix its syntax"],
])("gives the problem of a file that does not decode, case %#", (tree, text) => {
  expect(decode(tree, "a.json")).toEqual({ problem: problem(text) })
})

test("builds a problem only through problem(), so no bare string passes as one", () => {
  // @ts-expect-error a bare string, such as a value read from a file, is no problem
  const bare: Problem = "a.json: is missing; restore it"
  expect(bare).toBe(problem("a.json: is missing; restore it"))
})

const decoded = (path: string, text: string, parser?: (text: string) => unknown) =>
  decode(new Map([[path, encoded(text)]]), path, parser)

test.each([
  ["YAML", Bun.YAML.parse, "a: [\n"],
  ["TOML", Bun.TOML.parse, "a = ["],
])("gives %s that does not parse the syntax problem", (_, parser, text) => {
  expect(decoded("a", text, parser)).toEqual({
    problem: problem("a: does not parse as its format; fix its syntax"),
  })
})

const brackets = (levels: number) => "[".repeat(levels) + "]".repeat(levels)

test.each([
  [
    "a string that closes 8000 brackets first",
    `a: "${"]".repeat(8000)}"\nb: ${"[".repeat(8000)}`,
    true,
  ],
  [
    "a comment that closes 8000 brackets first",
    `# ${"]".repeat(8000)}\nb: ${"[".repeat(8000)}`,
    true,
  ],
  ["8000 nested sequence entries", `${"- ".repeat(8000)}x`, true],
  ["8000 nested complex keys", `${"? ".repeat(8000)}x`, true],
  ["a line indented 100 columns", `${" ".repeat(100)}x`, true],
  ["a line indented 99 columns", `${" ".repeat(99)}x`, false],
])("counts whether %s is too deep to parse", (_, text, deep) => {
  expect(nestsTooDeep(text)).toBe(deep)
})

test("refuses text whose parser overflows the stack anyway, as the same fault", () => {
  const overflowing = capped(() => {
    throw new RangeError("Maximum call stack size exceeded.")
  })
  expect(decoded("a", "x", overflowing)).toEqual({
    problem: problem(
      "a: may nest more than 200 levels deep, the most Bun's parser reads safely; flatten it",
    ),
  })
})

test("throws a parser's RangeError other than a stack overflow, which is a bug rather than a problem in the file", () => {
  const bug = new RangeError("Invalid array length")
  const failing = capped(() => {
    throw bug
  })
  expect(() => decoded("a", "x", failing)).toThrow(bug)
})

test.each([
  ["YAML", parseYaml, brackets(200_000)],
  ["TOML", parseToml, `a = ${brackets(200_000)}`],
])("refuses %s nested too deep before Bun's parser reads it, naming the fix", (_, parser, text) => {
  expect(decoded("a", text, parser)).toEqual({
    problem: problem(
      "a: holds more than 16384 characters, the most Bun's parser reads safely; shorten it",
    ),
  })
})

test.each([
  ["YAML of 16384 brackets", parseYaml, "[".repeat(16384)],
  ["YAML of 8192 balanced brackets", parseYaml, brackets(8192)],
  ["YAML of 201 braces", parseYaml, "{".repeat(201) + "}".repeat(201)],
  ["TOML of 201 brackets", parseToml, `a = ${brackets(201)}`],
  [
    "YAML whose string closes 8000 brackets first",
    parseYaml,
    `a: "${"]".repeat(8000)}"\nb: ${"[".repeat(8000)}`,
  ],
  [
    "YAML whose comment closes 8000 brackets first",
    parseYaml,
    `# ${"]".repeat(8000)}\nb: ${"[".repeat(8000)}`,
  ],
  ["YAML of 8000 nested sequence entries", parseYaml, `${"- ".repeat(8000)}x`],
  ["YAML of 8000 nested complex keys", parseYaml, `${"? ".repeat(8000)}x`],
])("refuses %s before Bun's parser reads it, naming the fix", (_, parser, text) => {
  expect(decoded("a", text, parser)).toEqual({
    problem: problem(
      "a: may nest more than 200 levels deep, the most Bun's parser reads safely; flatten it",
    ),
  })
})

test.each([
  ["YAML", parseYaml, brackets(200)],
  ["TOML", parseToml, `a = ${brackets(200)}`],
])("reads %s nested 200 levels deep, the most it reads", (_, parser, text) => {
  expect(decoded("a", text, parser)).not.toHaveProperty("problem")
})

test.each([
  ["YAML", parseYaml, `a: "${"x".repeat(16379)}"`],
  ["TOML", parseToml, `a = "${"x".repeat(16378)}"`],
])("reads %s of 16384 characters, the most it reads", (_, parser, text) => {
  expect(text).toHaveLength(16384)
  expect(decoded("a", text, parser)).toEqual([{ a: text.slice(text.indexOf('"') + 1, -1) }])
})

test("throws a parser's error other than a syntax error, which is a bug rather than a problem in the file", () => {
  const bug = new TypeError("bug")
  expect(() =>
    decoded("a.json", "{}", () => {
      throw bug
    }),
  ).toThrow(bug)
})

test("parses each owner and key once", () => {
  const owner = {}
  let runs = 0
  const parse = () => ++runs
  expect([once(owner, "k", parse), once(owner, "k", parse), once(owner, "j", parse)]).toEqual([
    1, 1, 2,
  ])
})

test("passes a missing file as undefined, and throws any other error", () => {
  expect(rethrowUnlessMissing(Object.assign(new Error("gone"), { code: "ENOENT" }))).toBeUndefined()
  const denied = Object.assign(new Error("denied"), { code: "EACCES" })
  expect(() => rethrowUnlessMissing(denied)).toThrow(denied)
})

test("reads the value at a path of nested tables, and undefined where a table on the way is missing or no table", () => {
  const value = { a: { b: 1 }, list: [{ b: 2 }], none: null }
  expect(valueAt(value, ["a", "b"])).toBe(1)
  expect(valueAt(value, [])).toBe(value)
  expect(
    ["a,c", "list,0", "none,b", "a,b,c"].map((path) => valueAt(value, path.split(","))),
  ).toEqual([undefined, undefined, undefined, undefined])
})

test("takes only a non-array object as a table", () => {
  expect([{}, { a: 1 }, [], null, "x", 1, undefined].map(isObject)).toEqual([
    true,
    true,
    false,
    false,
    false,
    false,
    false,
  ])
})
