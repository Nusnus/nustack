/**
 * readEntry reads a path as a file's bytes or a symlink, and as nothing where it holds no file; decode reads a file
 * of the tree into a value or one problem, parsing each file once; problem() alone builds a problem; rethrowUnlessMissing passes only ENOENT; valueAt reads a value
 * through nested tables, of which isObject takes only a non-array object.
 */
import { afterEach, expect, spyOn, test } from "bun:test"
import { chmod, mkdir, symlink, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { Document } from "yaml"
import { SkillFile } from "../../../plugin/opencode.ts"
import {
  decode,
  isObject,
  MOST_LEVELS,
  nestsTooDeep,
  once,
  type Problem,
  parseJson,
  parseToml,
  parseYaml,
  problem,
  readEntry,
  rethrowUnlessMissing,
  UnreadableEntry,
  valueAt,
} from "../../../scripts/tree.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"

const folders = new TemporaryFolders()
afterEach(() => folders.clear())

const encoded = (text: string) => new TextEncoder().encode(text)

test("reads a file's bytes, a symlink as one, and a folder or a missing path as no file", async () => {
  const root = await folders.make()
  await writeFile(join(root, "f"), "x")
  await symlink("f", join(root, "l"))
  await mkdir(join(root, "d"))
  const read = await Promise.all(["f", "l", "d", "gone"].map((path) => readEntry(root, path)))
  expect(read).toEqual([new TextEncoder().encode("x"), "symlink", undefined, undefined])
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
const SYNTAX = "does not parse as its format; fix its syntax"
const REPEAT = "repeats a key in one table; keep one"
const LONG_INTEGER = "holds an integer outside ±(2^53-1); quote it as a string"
const TOO_DEEP = "nests values more than 200 levels deep; flatten them"
const brackets = (levels: number) => "[".repeat(levels) + "]".repeat(levels)
const arrays = (levels: number) =>
  Array.from({ length: levels - 1 }).reduce<unknown[]>((inner) => [inner], [])

test("reads JSON with parseJson unless given another parser", () => {
  expect(decoded("a.json", '{"a":1,"a":2}')).toEqual(decoded("a.json", '{"a":1,"a":2}', parseJson))
})

test.each([
  ['{"a":1,"a":2}', REPEAT],
  ['{"a":1,"\\u0061":2}', REPEAT],
  ['{"x":{"a":1},"y":[{"a":1}]}', undefined],
  ['{"s":"\\"a\\":1,\\"a\\":2"}', undefined],
  ["{a:1}", SYNTAX],
  ["{'a':1}", SYNTAX],
  ['{"a":1} # x', SYNTAX],
  ['{"a":1,}', SYNTAX],
  ['{"a":NaN}', SYNTAX],
  ['{"a":Infinity}', SYNTAX],
  ["a: 1", SYNTAX],
  ['\uFEFF{"a":1}', SYNTAX],
  [brackets(200), undefined],
  [brackets(201), TOO_DEEP],
])("reads the JSON %p as JSON alone, refusing a key one table repeats", (text, refusal) => {
  const read = decoded("a.json", text)
  expect(Array.isArray(read) ? undefined : read.problem).toEqual(
    refusal === undefined ? undefined : problem(`a.json: ${refusal}`),
  )
})

test.each([
  ["a: 1\na: 2\n", REPEAT],
  ['{"a": 1, "\\u0061": 2}', REPEAT],
  ["%YAML 1.3\n---\na: 1\n", SYNTAX],
  ["%YAML 1.3\n---\na: 1\na: 2\n", SYNTAX],
  ["a: !!x b\n", SYNTAX],
  ["x: !!int x\n", SYNTAX],
  ["x: !!set {a}\n", SYNTAX],
  ["a: 9007199254740993\n", LONG_INTEGER],
  ["a: -9007199254740993\n", LONG_INTEGER],
  [`a: ${"1".repeat(5000)}\n`, LONG_INTEGER],
  [`%YAML 1.1\n---\na: 0${"7".repeat(30)}\n`, LONG_INTEGER],
  ["? [b, c]\n: f\n", "holds a list or mapping as a key; use a scalar key"],
  ["? {b: 1}\n: f\n", "holds a list or mapping as a key; use a scalar key"],
  ["a: *b\n", SYNTAX],
  ["a: [\n", SYNTAX],
  [`a: ${brackets(199)}\n`, { a: arrays(199) }],
  [`a: ${brackets(200)}\n`, TOO_DEEP],
  [`a: ${brackets(10000)}\n`, TOO_DEEP],
  [`a: ${"[".repeat(200)}9007199254740993${"]".repeat(200)}\n`, TOO_DEEP],
  [`a: [[&x ${brackets(197)}]]\nb: *x\n`, { a: [[arrays(197)]], b: arrays(197) }],
  [`a: [[&x ${brackets(198)}]]\nb: *x\n`, TOO_DEEP],
  ["a: &x [*x]\n", TOO_DEEP],
  ['a: "\\UFFFFFFFF"\n', SYNTAX],
  ["%YAML 1.1\n---\na: 1\n", { a: 1 }],
  ["a: 9007199254740991\n", { a: 9007199254740991 }],
  ["a: -9007199254740991\n", { a: -9007199254740991 }],
  ["\uFEFFa: 1\n", { a: 1 }],
  ["a: _1\n", { a: "_1" }],
  ["a: 2026-02-30\n", { a: "2026-02-30" }],
  ['a: "\\x07"\n', { a: "\u0007" }],
  ["a: >\n  x\n\n  y\n", { a: "x\ny\n" }],
  ["a: !!str bar\n", { a: "bar" }],
  ["a: !!seq [b: 1]\n", { a: [{ b: 1 }] }],
  ["a: !!str 2026-01-01\n", { a: "2026-01-01" }],
  ["# a\n%YAML 1.1\n---\na: yes\n", { a: true }],
  ["%YAML 1.1\n---\na: 0b_1\n", { a: 1 }],
  ["%YAML 1.1\n---\na: 0x_1\n", { a: 1 }],
])(
  "reads the YAML %p, refusing a repeated key, an unknown version, an unresolved tag or alias, an integer outside ±(2^53-1) and a list or mapping as a key",
  (text, expected) => {
    const read = decoded("a.yml", text, parseYaml)
    expect(Array.isArray(read) ? read[0] : read.problem).toEqual(
      typeof expected === "string" ? problem(`a.yml: ${expected}`) : expected,
    )
  },
)

test.each([
  ["a = 1\na = 2\n", SYNTAX],
  ["\uFEFFa = 1\n", SYNTAX],
  ["a = 1\n", { a: 1 }],
  [`a = ${brackets(199)}\n`, { a: arrays(199) }],
  [`a = ${brackets(200)}\n`, TOO_DEEP],
  [`a = [${"[], ".repeat(300)}]\n`, { a: Array.from({ length: 300 }, () => []) }],
  [
    `a = "${"[".repeat(300)}"\nb = '${"[".repeat(300)}'\nc = """\n${"[".repeat(300)}"""\nd = '''\n${"[".repeat(300)}'''\n# ${"[".repeat(300)}\n`,
    { a: "[".repeat(300), b: "[".repeat(300), c: "[".repeat(300), d: "[".repeat(300) },
  ],
])(
  "reads the TOML %p, refusing a repeated key, a byte order mark and a value nested past the bound",
  (text, expected) => {
    const read = decoded("a.toml", text, parseToml)
    expect(Array.isArray(read) ? read[0] : read.problem).toEqual(
      typeof expected === "string" ? problem(`a.toml: ${expected}`) : expected,
    )
  },
)

const keys = (count: number) => Array.from({ length: count }, (_, at) => `k${at}`).join(".")
const TOML_TOO_LONG = "holds more than 16384 characters, the most the TOML reader takes; shorten it"

test.each([
  ["a dotted key 200 levels deep", `${keys(200)} = 1\n`, undefined],
  ["a dotted key 201 levels deep", `${keys(201)} = 1\n`, TOO_DEEP],
  ["a table header 200 levels deep", `[${keys(199)}]\n`, undefined],
  ["a table header 201 levels deep", `[${keys(200)}]\n`, TOO_DEEP],
  ["an array of tables 200 levels deep", `[[${keys(198)}]]\n`, undefined],
  ["an array of tables 201 levels deep", `[[${keys(199)}]]\n`, TOO_DEEP],
  ["an inline table's dotted key 200 levels deep", `a = { ${keys(199)} = 1 }\n`, undefined],
  ["an inline table's dotted key 201 levels deep", `a = { ${keys(200)} = 1 }\n`, TOO_DEEP],
  ["a dotted key 6000 levels deep", `${keys(6000)} = 1\n`, TOML_TOO_LONG],
  ["a table header 6000 levels deep", `[${keys(6000)}]\nx = 1\n`, TOML_TOO_LONG],
  ["an array of tables 6000 levels deep", `[[${keys(6000)}]]\nx = 1\n`, TOML_TOO_LONG],
  ["an inline table's dotted key 6000 levels deep", `a = { ${keys(6000)} = 1 }\n`, TOML_TOO_LONG],
  ["16384 characters", `a = "${"x".repeat(16377)}"\n`, undefined],
  ["16385 characters", `a = "${"x".repeat(16378)}"\n`, TOML_TOO_LONG],
])(
  "reads TOML holding %s, counting levels on the value it parses into and refusing it past the bound or past 16384 characters",
  (_, text, refusal) => {
    const read = decoded("a.toml", text, parseToml)
    expect(Array.isArray(read) ? undefined : read.problem).toEqual(
      refusal === undefined ? undefined : problem(`a.toml: ${refusal}`),
    )
  },
)

const shared = (inner: number) => {
  const value = arrays(inner)
  return { a: [[value]], b: value }
}
const cycle: unknown[] = []
cycle.push(cycle)
const doubled = Array.from({ length: 64 }).reduce<unknown[]>((inner) => [inner, inner], [])

test.each([
  ["a scalar", "a", false],
  ["200 arrays", arrays(200), false],
  ["201 arrays", arrays(201), true],
  ["a value an alias shares, 200 deep along its deeper path", shared(197), false],
  [
    "a value an alias shares, 201 deep along its deeper path, which the walk takes second",
    shared(198),
    true,
  ],
  ["a cycle", cycle, true],
  ["64 levels that each hold the next twice", doubled, false],
])(
  "counts %s on the parsed value, in scripts/check.ts and in the loader alike",
  (_, value, deep) => {
    expect([nestsTooDeep(value), SkillFile.nestsTooDeep(value)]).toEqual([deep, deep])
  },
)

test("reads a stack overflow while yaml builds a value as too deep, and throws any other error, a plain error naming a stack overflow included", () => {
  const build = spyOn(Document.prototype, "toJS")
  try {
    build.mockImplementation(() => {
      throw new RangeError("Maximum call stack size exceeded.")
    })
    expect(decoded("a.yml", "a: 1\n", parseYaml)).toEqual({
      problem: problem(`a.yml: ${TOO_DEEP}`),
    })
    const other = new RangeError("Invalid array length")
    build.mockImplementation(() => {
      throw other
    })
    expect(() => decoded("a.yml", "a: 1\n", parseYaml)).toThrow(other)
    const plain = new Error("Maximum call stack size exceeded.")
    build.mockImplementation(() => {
      throw plain
    })
    expect(() => decoded("a.yml", "a: 1\n", parseYaml)).toThrow(plain)
  } finally {
    build.mockRestore()
  }
})

test("reads a stack overflow while Bun parses TOML as too deep, and throws any other error, a plain error naming a stack overflow included", () => {
  const parse = spyOn(Bun.TOML, "parse")
  try {
    parse.mockImplementation(() => {
      throw new RangeError("Maximum call stack size exceeded.")
    })
    expect(decoded("a.toml", "a = 1\n", parseToml)).toEqual({
      problem: problem(`a.toml: ${TOO_DEEP}`),
    })
    const other = new RangeError("Invalid array length")
    parse.mockImplementation(() => {
      throw other
    })
    expect(() => decoded("a.toml", "a = 1\n", parseToml)).toThrow(other)
    const plain = new Error("Maximum call stack size exceeded.")
    parse.mockImplementation(() => {
      throw plain
    })
    expect(() => decoded("a.toml", "a = 1\n", parseToml)).toThrow(plain)
  } finally {
    parse.mockRestore()
  }
})

test("holds frontmatter to the bound it holds JSON, YAML and TOML to", () => {
  expect(SkillFile.MOST_LEVELS).toBe(MOST_LEVELS)
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
