/**
 * parseManifest and parsePackage turn a file into a frozen value of the fields a release reads, or refuse it; the
 * metadata rule holds the host manifests to one JSON value, and the package, pyproject.toml and the marketplaces to its
 * name and version.
 */
import { describe, expect, test } from "bun:test"
import {
  CLAUDE_MANIFEST,
  MANIFESTS,
  MARKETPLACES,
  metadataProblems,
  PACKAGE,
  PYPROJECT,
  parseManifest,
  parsePackage,
} from "../../../scripts/metadata.ts"
import { problem, type Tree } from "../../../scripts/tree.ts"
import { manifest, tree } from "../../fixtures/metadata.ts"

const plugin = {
  name: manifest.name,
  version: manifest.version,
  description: manifest.description,
  repository: manifest.repository,
}
const market = { plugins: [{ name: "nustack", source: "plugin" }] }
const encode = (value: unknown) =>
  new TextEncoder().encode(typeof value === "string" ? value : JSON.stringify(value))
const metadata = (changes: Record<string, unknown> = {}): Tree =>
  new Map(
    Object.entries({
      ...Object.fromEntries(MANIFESTS.map((path) => [path, manifest])),
      [PACKAGE]: { name: "nustack", version: "0.1.0" },
      [PYPROJECT]: '[project]\nversion = "0.1.0"\n',
      ...Object.fromEntries(MARKETPLACES.map((path) => [path, market])),
      ...changes,
    })
      .filter(([, value]) => value !== undefined)
      .map(([path, value]) => [path, encode(value)]),
  )

describe("parseManifest", () => {
  test("parses a manifest into a frozen value of the fields a release reads", () => {
    const parsed = parseManifest(tree(CLAUDE_MANIFEST, manifest), CLAUDE_MANIFEST)
    expect(parsed).toEqual(plugin)
    expect(Object.isFrozen(parsed)).toBeTrue()
  })

  test.each([
    [
      "a name led by a hyphen",
      { name: "-a" },
      "name is missing or not in kebab case; set it in kebab case",
    ],
    [
      "a name with a double hyphen",
      { name: "a--b" },
      "name is missing or not in kebab case; set it in kebab case",
    ],
    [
      "a version with a leading zero",
      { version: "01.0.0" },
      "version is missing or malformed; set it as <major>.<minor>.<patch>",
    ],
    [
      "a pre-release version",
      { version: "1.0.0-rc" },
      "version is missing or malformed; set it as <major>.<minor>.<patch>",
    ],
    ["a blank description", { description: " " }, "description is missing or empty; fill it in"],
    ["no repository", { repository: undefined }, "repository is missing or empty; fill it in"],
  ])("gives %s one problem", (_, change, wrong) => {
    expect(
      parseManifest(tree(CLAUDE_MANIFEST, { ...manifest, ...change }), CLAUDE_MANIFEST),
    ).toEqual([problem(`${CLAUDE_MANIFEST}: ${wrong}`)])
  })
})

describe("parsePackage", () => {
  test("parses plugin/package.json into a frozen value of its name and version", () => {
    const parsed = parsePackage(
      tree(PACKAGE, { name: "nustack", version: "0.1.0", type: "module" }),
    )
    expect(parsed).toEqual({ name: "nustack", version: "0.1.0" })
    expect(Object.isFrozen(parsed)).toBeTrue()
  })

  test("refuses a missing name and a version that is not <major>.<minor>.<patch>", () => {
    expect(parsePackage(tree(PACKAGE, { version: "1" }))).toEqual([
      problem(`${PACKAGE}: name is missing or empty; fill it in`),
      problem(`${PACKAGE}: version is missing or malformed; set it as <major>.<minor>.<patch>`),
    ])
  })
})

describe("metadataProblems", () => {
  test("passes metadata that agrees", () => {
    expect(metadataProblems(metadata())).toEqual([])
  })

  test.each([
    [
      "a host manifest that differs",
      { [MANIFESTS[2] as string]: { ...manifest, homepage: "https://x" } },
      [`${MANIFESTS[2]}: differs from ${CLAUDE_MANIFEST}; make every manifest the same`],
    ],
    [
      "a missing host manifest",
      { [MANIFESTS[1] as string]: undefined },
      [`${MANIFESTS[1]}: is missing; restore it`],
    ],
    [
      "a package of another version",
      { [PACKAGE]: { name: "nustack", version: "0.2.0" } },
      [`${PACKAGE}: name or version is not the manifests'; set both`],
    ],
    [
      "a package of another name",
      { [PACKAGE]: { name: "other", version: "0.1.0" } },
      [`${PACKAGE}: name or version is not the manifests'; set both`],
    ],
    [
      "a pyproject.toml of another version",
      { [PYPROJECT]: '[project]\nversion = "0.2.0"\n' },
      [`${PYPROJECT}: [project] version is not the manifests'; set it to theirs`],
    ],
    [
      "a marketplace that lists another plugin",
      { [MARKETPLACES[1] as string]: { plugins: [{ name: "other" }] } },
      [`${MARKETPLACES[1]}: plugins does not list the manifests' name; list the plugin by it`],
    ],
    [
      "a marketplace that lists no plugins",
      { [MARKETPLACES[0] as string]: {} },
      [`${MARKETPLACES[0]}: plugins does not list the manifests' name; list the plugin by it`],
    ],
    [
      "a pyproject.toml too long for Bun's parser",
      { [PYPROJECT]: `[project]\nversion = "0.1.0"\n#${"x".repeat(16384)}\n` },
      [
        "pyproject.toml: holds more than 16384 characters, the most Bun's parser reads safely; shorten it",
      ],
    ],
    [
      "a pyproject.toml nested too deep for Bun's parser",
      { [PYPROJECT]: `[project]\nversion = "0.1.0"\na = ${"[".repeat(201)}${"]".repeat(201)}\n` },
      [
        "pyproject.toml: may nest more than 200 levels deep, the most Bun's parser reads safely; flatten it",
      ],
    ],
  ])("gives %s its problem", (_, changes, problems) => {
    expect(metadataProblems(metadata(changes))).toEqual(problems.map(problem))
  })

  test("reads the rest against no manifest that does not parse, and gives its problems alone", () => {
    expect(
      metadataProblems(metadata({ [CLAUDE_MANIFEST]: { ...manifest, version: "1" } })),
    ).toEqual([
      problem(`${MANIFESTS[1]}: differs from ${CLAUDE_MANIFEST}; make every manifest the same`),
      problem(`${MANIFESTS[2]}: differs from ${CLAUDE_MANIFEST}; make every manifest the same`),
      problem(
        `${CLAUDE_MANIFEST}: version is missing or malformed; set it as <major>.<minor>.<patch>`,
      ),
    ])
  })
})
