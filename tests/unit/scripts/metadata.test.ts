/**
 * Each metadata parser turns a file into a frozen value holding only the fields the check compares, or refuses it, and
 * each workflow reader gives only the problems of its workflows.
 */
import { describe, expect, test } from "bun:test"
import { SkillFile } from "../../../plugin/opencode.ts"
import {
  BLANK,
  MARKETPLACES,
  parseManifest,
  parsePackage,
  readChangelog,
  readManifest,
  readMarketplace,
  readMetadata,
  readPyproject,
  releaseTagsProblems,
  VERSION_FILES,
} from "../../../scripts/metadata.ts"
import { problem, type Tree } from "../../../scripts/tree.ts"
import { manifest, tree } from "../../fixtures/metadata.ts"

const MANIFEST = "plugin/.devin-plugin/plugin.json"
const [claude, cursor] = MARKETPLACES
const market = {
  name: "n",
  owner: { name: "A" },
  plugins: [{ name: "nustack", description: "d", source: "plugin" }],
  metadata: { description: "m" },
}
const pkg = { name: "nustack", version: "0.1.0", type: "module", exports: { ".": "./opencode.ts" } }
const commitizen = `tag_format = "v$version"\nversion_files = ${JSON.stringify(
  ["claude", "cursor", "devin"].map((host) => `plugin/.${host}-plugin/plugin.json:version`),
).replace("]", ', "plugin/package.json:version"]')}\n`

const frozen = (value: unknown): boolean =>
  typeof value !== "object" ||
  value === null ||
  (Object.isFrozen(value) && Object.values(value).every(frozen))

test("BLANK is the loader's, so the check counts a blank text as the loader does", () => {
  expect(BLANK.source).toBe(SkillFile.BLANK.source)
})

test("readMetadata reads no workflow's jobs, which the workflows rule checks", () => {
  const encode = (text: string) => new TextEncoder().encode(text)
  const files: Tree = new Map([
    [".github/workflows/release.yml", encode('on:\n  push:\n    tags: ["v*"]\njobs: {}\n')],
    [
      ".github/workflows/ci.yml",
      encode("jobs:\n  a:\n    steps:\n      - run: bun scripts/check.ts\n"),
    ],
  ])
  expect(readMetadata(files).problems.filter((found) => found.includes("jobs."))).toEqual([])
})

test("readMetadata parses each file once into a result frozen all the way down", () => {
  const files = tree(MANIFEST, manifest)
  const metadata = readMetadata(files)
  expect(readMetadata(files)).toBe(metadata)
  expect(frozen(metadata)).toBeTrue()
})

// check.test.ts holds the refusals a whole tree shows; this holds each parser's own, matched exactly.
describe("parseManifest", () => {
  test("parses a manifest into a value frozen all the way down", () => {
    const parsed = parseManifest(tree(MANIFEST, manifest), MANIFEST)
    expect(parsed).toEqual(manifest)
    expect(frozen(parsed)).toBeTrue()
  })

  test("takes a homepage of 2083 characters", () => {
    const homepage = `https://h/${"a".repeat(2073)}`
    expect(parseManifest(tree(MANIFEST, { ...manifest, homepage }), MANIFEST)).toEqual({
      ...manifest,
      homepage,
    })
  })

  test.each([
    ["no object", [], "is not an object; make it one"],
    [
      "a repository ending in .git",
      { ...manifest, repository: "https://h/o/n.git" },
      "repository is missing or malformed; set it to https://<host>/<owner>/<name>",
    ],
    [
      "a repository naming a user",
      { ...manifest, repository: "https://u@h/o/n" },
      "repository is missing or malformed; set it to https://<host>/<owner>/<name>",
    ],
    [
      "a version with a leading zero",
      { ...manifest, version: "01.0.0" },
      "version is missing or malformed; set it as <major>.<minor>.<patch>",
    ],
    [
      "a pre-release version",
      { ...manifest, version: "1.0.0-rc" },
      "version is missing or malformed; set it as <major>.<minor>.<patch>",
    ],
    [
      "a name led by a hyphen",
      { ...manifest, name: "-a" },
      "name is missing or malformed; set it in kebab case",
    ],
    [
      "a name with a double hyphen",
      { ...manifest, name: "a--b" },
      "name is missing or malformed; set it in kebab case",
    ],
    [
      "a description of zero-width spaces",
      { ...manifest, description: "\u200b" },
      "description is missing or malformed; fill it in",
    ],
    [
      "a homepage with no host",
      { ...manifest, homepage: "https://" },
      "homepage is missing or malformed; set it to an https URL of at most 2083 characters",
    ],
    [
      "a homepage over 2083 characters",
      { ...manifest, homepage: `https://h/${"a".repeat(2074)}` },
      "homepage is missing or malformed; set it to an https URL of at most 2083 characters",
    ],
    [
      "a homepage holding a space",
      { ...manifest, homepage: "https://h x" },
      "homepage is missing or malformed; set it to an https URL of at most 2083 characters",
    ],
    [
      "an author that is no object",
      { ...manifest, author: "A" },
      "author is missing or malformed; give the author's name, and only that",
    ],
  ])("gives %s one problem", (_, value, wrong) => {
    expect(parseManifest(tree(MANIFEST, value), MANIFEST)).toEqual([
      problem(`${MANIFEST}: ${wrong}`),
    ])
  })
})

describe("readManifest", () => {
  test("keeps each field that parses beside the problems of those that do not", () => {
    const { homepage: _, ...rest } = manifest
    const read = readManifest(tree(MANIFEST, { ...rest, typo_key: 1 }), MANIFEST)
    expect(read).toEqual({
      found: rest,
      problems: [
        problem(
          `${MANIFEST}: holds a field besides name, version, description, author, homepage, repository, license; drop it`,
        ),
        problem(
          `${MANIFEST}: homepage is missing or malformed; set it to an https URL of at most 2083 characters`,
        ),
      ],
    })
    expect(Object.keys(read.found)).toEqual(Object.keys(rest))
    expect(frozen(read)).toBeTrue()
  })

  test("keeps no author of a manifest whose author is malformed", () => {
    const { author: _, ...rest } = manifest
    expect(readManifest(tree(MANIFEST, { ...rest, author: "A" }), MANIFEST).found).toEqual(rest)
  })

  test("keeps no field of a file that does not parse", () => {
    expect(readManifest(tree(MANIFEST, "{"), MANIFEST)).toEqual({
      found: {},
      problems: [problem(`${MANIFEST}: does not parse as its format; fix its syntax`)],
    })
  })
})

describe("readMarketplace", () => {
  test("parses a marketplace into a value frozen all the way down", () => {
    const { found: parsed, problems } = readMarketplace(tree(cursor.path, market), cursor)
    expect(problems).toEqual([])
    expect(parsed).toEqual({
      name: "n",
      owner: { name: "A" },
      plugin: { name: "nustack", description: "d" },
      description: "m",
    })
    expect(frozen(parsed)).toBeTrue()
  })

  test.each([
    [
      "a second plugin",
      { ...market, plugins: [...market.plugins, ...market.plugins] },
      "plugins lists more than the plugin; list only the plugin",
    ],
    [
      "a plugin with an unknown field",
      { ...market, plugins: [{ ...market.plugins[0], version: "1" }] },
      "plugins' entry holds a field besides name, description, source; drop it",
    ],
    ["no plugin", { ...market, plugins: [] }, "plugins does not list the plugin; list it"],
    [
      "plugins that is no list",
      { ...market, plugins: market.plugins[0] },
      "plugins is not a list; list the plugin in it",
    ],
    [
      "a plugin that is no object",
      { ...market, plugins: ["nustack"] },
      "plugins' entry is not an object; make it one",
    ],
    [
      "a plugin's name out of kebab case",
      { ...market, plugins: [{ ...market.plugins[0], name: "N" }] },
      "plugins' name is missing or malformed; set it in kebab case",
    ],
    [
      "a plugin's description of zero-width spaces",
      { ...market, plugins: [{ ...market.plugins[0], description: "\u200b" }] },
      "plugins' description is missing or malformed; fill it in",
    ],
    [
      "a plugin with no source",
      { ...market, plugins: [{ name: "nustack", description: "d" }] },
      "plugins' source is not plugin; set it to that",
    ],
    [
      "another host's source",
      { ...market, plugins: [{ ...market.plugins[0], source: "./plugin" }] },
      "plugins' source is not plugin; set it to that",
    ],
    [
      "an owner besides a name",
      { ...market, owner: { name: "A", email: "e" } },
      "owner is missing or malformed; give the owner's name, and only that",
    ],
    [
      "an owner of zero-width spaces",
      { ...market, owner: { name: "\u200b" } },
      "owner is missing or malformed; give the owner's name, and only that",
    ],
    [
      "no owner",
      { ...market, owner: undefined },
      "owner is missing or malformed; give the owner's name, and only that",
    ],
    [
      "a name out of kebab case",
      { ...market, name: "N n" },
      "name is missing or malformed; set it in kebab case",
    ],
    [
      "metadata that is no object",
      { ...market, metadata: "m" },
      "metadata is not an object; make it one",
    ],
    [
      "a blank metadata description",
      { ...market, metadata: { description: "\u200b" } },
      "metadata description is missing or malformed; fill it in",
    ],
    [
      "the other host's description field",
      { ...market, description: "m" },
      "holds a field besides name, owner, plugins, metadata; drop it",
    ],
  ])("gives %s one problem", (_, value, wrong) => {
    expect(readMarketplace(tree(cursor.path, value), cursor).problems).toEqual([
      problem(`${cursor.path}: ${wrong}`),
    ])
  })

  test("gives a marketplace that is no object one problem", () => {
    expect(readMarketplace(tree(cursor.path, []), cursor)).toEqual({
      found: {},
      problems: [problem(`${cursor.path}: is not an object; make it one`)],
    })
  })

  test("reads Claude Code's description at the top", () => {
    const { metadata: _, ...rest } = market
    const value = {
      ...rest,
      description: "m",
      plugins: [{ ...market.plugins[0], source: "./plugin" }],
    }
    expect(readMarketplace(tree(claude.path, value), claude).problems).toEqual([])
    expect(readMarketplace(tree(claude.path, value), claude).found).toEqual({
      name: "n",
      owner: { name: "A" },
      plugin: { name: "nustack", description: "d" },
      description: "m",
    })
    expect(
      readMarketplace(tree(claude.path, { ...value, description: "\u200b" }), claude).problems,
    ).toEqual([problem(`${claude.path}: description is missing or malformed; fill it in`)])
  })

  test("freezes each host's settings", () => {
    expect(frozen(MARKETPLACES)).toBeTrue()
  })

  test("keeps the owner and plugin of a marketplace with an unknown field", () => {
    const read = readMarketplace(tree(cursor.path, { ...market, typo_key: 1 }), cursor)
    expect(read.found).toEqual({
      name: "n",
      owner: { name: "A" },
      plugin: { name: "nustack", description: "d" },
      description: "m",
    })
  })
})

describe("parsePackage", () => {
  test("refuses a package.json that repeats a key, through decode's parseJson", () => {
    const bytes = new TextEncoder().encode('{"name":"nustack","name":"nustack"}')
    expect(parsePackage(new Map([["plugin/package.json", bytes]]))).toEqual([
      problem("plugin/package.json: repeats a key in one table; keep one"),
    ])
  })

  test("parses plugin/package.json into a frozen value of its name and version", () => {
    const parsed = parsePackage(tree("plugin/package.json", pkg))
    expect(parsed).toEqual({ name: "nustack", version: "0.1.0" })
    expect(frozen(parsed)).toBeTrue()
  })

  test("refuses a name that is not kebab case and a version that is not <major>.<minor>.<patch>", () => {
    expect(parsePackage(tree("plugin/package.json", { ...pkg, name: "N", version: "1" }))).toEqual([
      problem("plugin/package.json: name is missing or malformed; set it in kebab case"),
      problem(
        "plugin/package.json: version is missing or malformed; set it as <major>.<minor>.<patch>",
      ),
    ])
  })

  test("gives a package.json that is no object one problem", () => {
    expect(parsePackage(tree("plugin/package.json", []))).toEqual([
      problem("plugin/package.json: is not an object; make it one"),
    ])
  })
})

describe("readPyproject", () => {
  test("parses pyproject.toml into a frozen value of its version, leaving other tools' settings unread", () => {
    const text = `[project]\nversion = "0.1.0"\n\n[tool.commitizen]\n${commitizen}version_provider = "uv"\n`
    const { found: parsed, problems } = readPyproject(tree("pyproject.toml", text))
    expect(problems).toEqual([])
    expect(parsed).toEqual({ version: "0.1.0" })
    expect(frozen(parsed)).toBeTrue()
  })

  test.each([
    [
      "a [project] version that is not <major>.<minor>.<patch>",
      `[project]\nversion = "0.1"\n\n[tool.commitizen]\n${commitizen}`,
      ["[project] version is missing or malformed; set it as <major>.<minor>.<patch>"],
    ],
    [
      "no [project] table",
      `[tool.commitizen]\n${commitizen}`,
      ["[project] version is missing or malformed; set it as <major>.<minor>.<patch>"],
    ],
    [
      "version_files that lists a file twice",
      `[project]\nversion = "0.1.0"\n\n[tool.commitizen]\n${commitizen.replace(
        '"plugin/package.json:version"]',
        '"plugin/package.json:version", "plugin/package.json:version"]',
      )}`,
      [
        "[tool.commitizen] version_files is not the files whose version the check compares; list each of plugin/.claude-plugin/plugin.json:version, plugin/.cursor-plugin/plugin.json:version, plugin/.devin-plugin/plugin.json:version, plugin/package.json:version once",
      ],
    ],
    [
      "a tool table that is no table",
      `tool = 1\n\n[project]\nversion = "0.1.0"\n`,
      [
        "[tool.commitizen] version_files is not the files whose version the check compares; list each of plugin/.claude-plugin/plugin.json:version, plugin/.cursor-plugin/plugin.json:version, plugin/.devin-plugin/plugin.json:version, plugin/package.json:version once",
        "[tool.commitizen] tag_format is not the release tags' form; set it to v$version",
      ],
    ],
  ])("refuses %s", (_, text, problems) => {
    expect(readPyproject(tree("pyproject.toml", text)).problems).toEqual(
      problems.map((wrong) => problem(`pyproject.toml: ${wrong}`)),
    )
  })

  test("takes version_files in any order", () => {
    const reordered = `tag_format = "v$version"\nversion_files = ${JSON.stringify([...VERSION_FILES].reverse())}\n`
    const text = `[project]\nversion = "0.1.0"\n\n[tool.commitizen]\n${reordered}`
    expect(readPyproject(tree("pyproject.toml", text)).problems).toEqual([])
  })
})

describe("readChangelog", () => {
  const undefinedRelease = problem(
    "CHANGELOG.md: a ## heading names a version in brackets whose label no definition defines; define it, as the release titles it",
  )
  test.each([
    [
      "## [Unreleased]\n\n## [0.2.0] - 2026-02-01\n\n## [0.1.0] - 2026-01-01\n\n[unreleased]: u\n[0.2.0]: v\n[0.1.0]: w\n",
      { latest: "0.2.0" },
      [],
    ],
    [
      "## [Unreleased]\n\n```\n## [9.9.9] - 2026-03-01\n```\n\n## [0.2.0] - 2026-02-01\n\n[Unreleased]: u\n[9.9.9]: x\n[0.2.0]: v\n",
      { latest: "0.2.0" },
      [],
    ],
    ["## [Unreleased]\n\n## [0.2.0] - 2026-02-01\n\n[Unreleased]: u\n", {}, [undefinedRelease]],
    [
      "## [Unreleased]\n\n## [0.2.0] - 2026-02-01\n\n## [0.1.0] - 2026-01-01\n\n[0.1.0]: w\n",
      { latest: "0.1.0" },
      [undefinedRelease],
    ],
    [
      "## [Unreleased]\n\n### [0.3.0] - 2026-03-01\n\n## [0.2.0] - 2026-02-01\n\n[0.3.0]: x\n[0.2.0]: v\n",
      { latest: "0.2.0" },
      [],
    ],
    ["## [Unreleased]\n", {}, []],
    [
      "## [0.10.0] - 2026-02-01\n\n## [0.9.0] - 2026-01-01\n\n[0.10.0]: v\n[0.9.0]: w\n",
      { latest: "0.10.0" },
      [],
    ],
    [
      "## [0.1.0] - 2026-02-01\n\n## [0.2.0] - 2026-01-01\n\n[0.1.0]: v\n[0.2.0]: w\n",
      { latest: "0.1.0" },
      [
        problem(
          "CHANGELOG.md: has the entry for 0.1.0 above the one for 0.2.0; list releases newest first, by version",
        ),
      ],
    ],
    [
      "## [0.2.0] - 2026-01-01\n\n## [0.1.0] - 2026-02-01\n\n[0.2.0]: v\n[0.1.0]: w\n",
      { latest: "0.2.0" },
      [
        problem(
          "CHANGELOG.md: has the entry dated 2026-01-01 above the one dated 2026-02-01; list releases newest first, by date",
        ),
      ],
    ],
    [
      "## [0.2.0] - 2026-01-01\n\n## [0.1.0] - 2026-01-01\n\n[0.2.0]: v\n[0.1.0]: w\n",
      { latest: "0.2.0" },
      [],
    ],
  ])("reads the latest release of %p", (text, found, problems) => {
    expect(readChangelog(tree("CHANGELOG.md", text))).toEqual({ found, problems })
  })
})

describe("releaseTagsProblems", () => {
  const path = ".github/workflows/release.yml"
  const tags = problem(
    `${path}: on.push.tags is not ["v*"], the tags tag_format gives; set it to that`,
  )

  test.each([
    ['on:\n  push:\n    tags: ["v*"]\n', []],
    ["on: push\n", [tags]],
    ['on:\n  push:\n    tags: ["v*", "x"]\n', [tags]],
    ["- on\n", [tags]],
    ["on: [\n", []],
  ])("reads %p", (text, problems) => {
    expect(releaseTagsProblems(tree(path, text))).toEqual(problems)
  })
})
