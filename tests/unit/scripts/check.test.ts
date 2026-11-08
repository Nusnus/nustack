/** Each rule check.ts holds reports a copy of a passing tree broken the way it forbids, with the file and the fix. */
import { describe, expect, spyOn, test } from "bun:test"
import { check } from "../../../scripts/check.ts"
import * as parser from "../../../scripts/markdown.ts"
import { blobOf, type CopyRecord, recordText } from "../../../scripts/record.ts"
import { problem, type Tree } from "../../../scripts/tree.ts"
import { manifest } from "../../fixtures/metadata.ts"

const bytes = (text: string) => new TextEncoder().encode(text)
const rewriting = [
  "end-of-file-fixer",
  "fix-byte-order-marker",
  "mixed-line-ending",
  "trailing-whitespace",
  "markdownlint-cli2",
]
const hooks = (
  copies: string,
  hook = (id: string) => `      - id: ${id}\n        exclude: *copy\n`,
) =>
  `repos:\n  - repo: local\n    hooks:\n      - id: check-yaml\n        exclude: &copy ^(?:${copies})/\n${rewriting.map(hook).join("")}`
const plugin = { name: "nustack", description: "d" }
const pkg = { name: "nustack", version: "0.1.0", exports: { ".": "./opencode.ts" }, type: "module" }
const versionFiles = [
  "plugin/.claude-plugin/plugin.json:version",
  "plugin/.cursor-plugin/plugin.json:version",
  "plugin/.devin-plugin/plugin.json:version",
  "plugin/package.json:version",
]
const broken = JSON.stringify({ ...manifest, name: "N", version: "1", repository: "x" })
const knap = "---\nname: knap\ndescription: k\nlicense: MIT\n---\n[x](../../nowhere.md)\n"
const mode = [
  "---\nname: nus-mode\ndescription: m\n---\n# nus-mode\n",
  "## Playbooks\n\n- [p](playbooks/p.md)\n",
  "## Principles\n\n- [n](../principle-naming/SKILL.md), [web](https://x.y), [a](#goal)\n",
].join("\n")
const record: CopyRecord = {
  upstream: "https://github.com/o/n",
  source: "skills",
  folder: "plugin/skills",
  skills: ["knap"],
  commit: "a".repeat(40),
  files: { "knap/LICENSE": blobOf(bytes("MIT")), "knap/SKILL.md": blobOf(bytes(knap)) },
}

const hosts = (value: object) =>
  Object.fromEntries(
    [".claude", ".cursor", ".devin"].map((host) => [
      `plugin/${host}-plugin/plugin.json`,
      JSON.stringify(value),
    ]),
  )
const principle = (name: string, description: string) =>
  `---\nname: ${name}\ndescription: ${description}\ndisable-model-invocation: true\ntriggers: [user]\n---\n`
const modeBody = mode.slice(mode.indexOf("\n---\n") + 5).trim()
const modeOf = (size: number) => `${mode}\n${"x".repeat(size - modeBody.length - 2)}`

const quickStart =
  "## Quick start\n\n### 1️⃣ Install\n\n[a](https://h) and [b][b]\n\n[b]: https://h\n\n### 2️⃣ Use\n\nx\n"
const TABLE_HEAD = "| Skill | What |\n| --- | --- |\n"
const rowsOf = (skills: readonly string[]) =>
  `\n## Skills\n\n${TABLE_HEAD}${skills.map((skill) => `| [${skill}](plugin/skills/${skill}/SKILL.md) | ${skill[0]} |\n`).join("")}`
const rows = rowsOf(["nus-mode", "principle-naming", "knap"])

const changelogOf = (entry: string) =>
  `## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\n${entry}\n[Unreleased]: u\n[0.1.0]: v\n`
const groupsOf = (parts: readonly string[]) =>
  parts.map((part, at) => `### G${at + 1}\n\n${part}\n`).join("")

function tree(changes: Record<string, string | null | "symlink"> = {}): Tree {
  const files: Record<string, string | null | "symlink"> = {
    LICENSE: "MIT",
    ".gitattributes": "plugin/** text eol=lf\nplugin/skills/knap/** -text\n",
    ".pre-commit-config.yaml": hooks("plugin/skills/knap"),
    "plugin/LICENSE": "MIT",
    "pyproject.toml": `[project]\nversion = "0.1.0"\n\n[tool.commitizen]\ntag_format = "v$version"\nversion_files = ${JSON.stringify(versionFiles)}\n`,
    "CHANGELOG.md": "## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\n[Unreleased]: u\n[0.1.0]: v\n",
    "plugin/.claude-plugin/plugin.json": JSON.stringify(manifest),
    "plugin/.cursor-plugin/plugin.json": JSON.stringify(manifest),
    "plugin/.devin-plugin/plugin.json": JSON.stringify(manifest),
    "plugin/package.json": JSON.stringify(pkg),
    ".claude-plugin/marketplace.json": JSON.stringify({
      name: "n",
      owner: manifest.author,
      plugins: [{ ...plugin, source: "./plugin" }],
      description: "m",
    }),
    ".cursor-plugin/marketplace.json": JSON.stringify({
      name: "n",
      owner: manifest.author,
      plugins: [{ ...plugin, source: "plugin" }],
      metadata: { description: "m" },
    }),
    ".github/workflows/ci.yml": "jobs:\n  release-zip:\n    needs: make-check\n",
    ".github/workflows/release.yml":
      'on:\n  push:\n    tags: ["v*"]\njobs:\n  ci:\n    needs: tag\n  publish:\n    needs: ci\n',
    ".github/workflows/sync.yml": "jobs: {}\n",
    "tests/unit/a.test.ts": "",
    "plugin/opencode.ts": "export {}\n",
    "plugin/skills/nus-mode/SKILL.md": mode,
    "plugin/skills/nus-mode/playbooks/p.md": "# p\n\n[mode](../SKILL.md)\n",
    "plugin/skills/principle-naming/SKILL.md":
      "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
    "plugin/skills/knap/SKILL.md": knap,
    "plugin/skills/knap/LICENSE": "MIT",
    "vendored/obsidian-skills.json": recordText(record),
    ...changes,
  }
  // The README gives each skill folder the tree holds its row, as the real one does, unless a test writes its own.
  const skills = Object.entries(files)
    .filter(([path, text]) => text !== null && /^plugin\/skills\/[^/]+\/./.test(path))
    .map(([path]) => path.split("/")[2] ?? "")
  files["README.md"] ??= quickStart + rowsOf([...new Set(skills)])
  if (changes["README.md"] === null) delete files["README.md"]
  return new Map(
    Object.entries(files).flatMap(([path, text]) =>
      text === null ? [] : [[path, text === "symlink" ? text : bytes(text)] as const],
    ),
  )
}

describe("check", () => {
  const syncSteps = (steps: string) => ({
    ".github/workflows/sync.yml": `jobs:\n  sync:\n    steps:\n${steps}`,
  })
  const uninstalled = [
    ".github/workflows/sync.yml: jobs.sync runs bun scripts/ before installing bun.lock; run bun install --frozen-lockfile in that job first, after setup-bun",
  ]

  test("passes a tree that keeps every rule", async () => {
    expect(await check(tree())).toEqual([])
  })

  test("parses each Markdown file once, however many rules and headings read it", async () => {
    const parse = spyOn(parser, "markdown")
    try {
      await check(tree())
      const texts = parse.mock.calls.map(([text]) => text)
      expect(texts.length).toBeGreaterThan(1)
      expect(new Set(texts).size).toBe(texts.length)
    } finally {
      parse.mockRestore()
    }
  })

  test("reads a skill's frontmatter as no heading and its values as no link", async () => {
    const mode = "---\nname: nus-mode\ndescription: see [x](gone.md)\n---\n"
    const files = tree()
    const text = new TextDecoder().decode(
      files.get("plugin/skills/nus-mode/SKILL.md") as Uint8Array,
    )
    const changed = tree({
      "plugin/skills/nus-mode/SKILL.md": text.replace(/^---\n[\s\S]*?\n---\n/, mode),
    })
    expect(await check(changed)).toEqual([])
  })

  test.each([
    [
      "a manifest that differs",
      { "plugin/.devin-plugin/plugin.json": JSON.stringify({ ...manifest, version: "0.2.0" }) },
      [
        "plugin/.devin-plugin/plugin.json: version differs from plugin/.claude-plugin/plugin.json; make every manifest the same",
      ],
    ],
    [
      "a manifest that differs in every field but its version",
      {
        "plugin/.devin-plugin/plugin.json": JSON.stringify({
          ...manifest,
          name: "other",
          description: "y",
          author: { name: "z" },
          homepage: "https://h.example",
          repository: "https://github.com/o/other",
          license: "Apache-2.0",
        }),
      },
      [
        "plugin/.devin-plugin/plugin.json: name, description, author, homepage, repository, license differs from plugin/.claude-plugin/plugin.json; make every manifest the same",
      ],
    ],
    [
      "a package.json and marketplaces that disagree with the manifests",
      {
        "plugin/package.json": JSON.stringify({ ...pkg, version: "9.0.0" }),
        ".claude-plugin/marketplace.json": JSON.stringify({
          name: "n",
          owner: { name: "B" },
          plugins: [{ ...plugin, description: "e", source: "./plugin" }],
          description: "m",
        }),
        ".cursor-plugin/marketplace.json": JSON.stringify({
          name: "x",
          owner: manifest.author,
          plugins: [{ ...plugin, source: "plugin" }],
          metadata: { description: "m" },
        }),
      },
      [
        "plugin/package.json: name or version is not the manifests'; set both",
        ".claude-plugin/marketplace.json: the plugin's name or description is not the manifests'; set both to theirs",
        ".claude-plugin/marketplace.json: owner differs from the manifests' author; set it to theirs",
        ".cursor-plugin/marketplace.json: name or description differs from the other's; match it",
      ],
    ],
    [
      "manifests and package.json that are missing, unreadable or of the wrong shape",
      {
        "plugin/.claude-plugin/plugin.json": null,
        "plugin/package.json": "{",
        ".claude-plugin/marketplace.json": null,
        "plugin/.cursor-plugin/plugin.json": broken,
        "plugin/.devin-plugin/plugin.json": broken.replace('"x"', '"https://h/o/n/"'),
      },
      [
        "plugin/.claude-plugin/plugin.json: is missing; restore it",
        "plugin/.cursor-plugin/plugin.json: name is missing or malformed; set it in kebab case",
        "plugin/.cursor-plugin/plugin.json: version is missing or malformed; set it as <major>.<minor>.<patch>",
        "plugin/.cursor-plugin/plugin.json: repository is missing or malformed; set it to https://<host>/<owner>/<name>",
        "plugin/.devin-plugin/plugin.json: name is missing or malformed; set it in kebab case",
        "plugin/.devin-plugin/plugin.json: version is missing or malformed; set it as <major>.<minor>.<patch>",
        "plugin/.devin-plugin/plugin.json: repository is missing or malformed; set it to https://<host>/<owner>/<name>",
        "plugin/package.json: does not parse as its format; fix its syntax",
        ".claude-plugin/marketplace.json: is missing; restore it",
      ],
    ],
    [
      "a pyproject.toml whose version is not the manifests' and that has no commitizen settings, and no LICENSE",
      { "pyproject.toml": '[project]\nversion = "0.0.9"\n', LICENSE: null, "plugin/LICENSE": null },
      [
        "pyproject.toml: [tool.commitizen] version_files is not the files whose version the check compares; list each of plugin/.claude-plugin/plugin.json:version, plugin/.cursor-plugin/plugin.json:version, plugin/.devin-plugin/plugin.json:version, plugin/package.json:version once",
        "pyproject.toml: [tool.commitizen] tag_format is not the release tags' form; set it to v$version",
        "pyproject.toml: [project] version is not the manifests'; set it to theirs",
        "LICENSE: is missing; restore it",
      ],
    ],
    [
      "a marketplace with an unknown field whose owner is not the manifests' author",
      {
        ".cursor-plugin/marketplace.json": JSON.stringify({
          name: "n",
          owner: { name: "B" },
          plugins: [{ ...plugin, source: "plugin" }],
          metadata: { description: "m" },
          typo_key: 1,
        }),
      },
      [
        ".cursor-plugin/marketplace.json: holds a field besides name, owner, plugins, metadata; drop it",
        ".cursor-plugin/marketplace.json: owner differs from the manifests' author; set it to theirs",
      ],
    ],
    [
      "a manifest with an unknown field whose description is not the others'",
      {
        "plugin/.cursor-plugin/plugin.json": JSON.stringify({
          ...manifest,
          description: "other",
          typo_key: 1,
        }),
      },
      [
        "plugin/.cursor-plugin/plugin.json: holds a field besides name, version, description, author, homepage, repository, license; drop it",
        "plugin/.cursor-plugin/plugin.json: description differs from plugin/.claude-plugin/plugin.json; make every manifest the same",
      ],
    ],
    [
      "manifests with no homepage whose version is not the other files'",
      hosts({ ...manifest, homepage: undefined, version: "9.9.9" }),
      [
        "plugin/.claude-plugin/plugin.json: homepage is missing or malformed; set it to an https URL of at most 2083 characters",
        "plugin/.cursor-plugin/plugin.json: homepage is missing or malformed; set it to an https URL of at most 2083 characters",
        "plugin/.devin-plugin/plugin.json: homepage is missing or malformed; set it to an https URL of at most 2083 characters",
        "pyproject.toml: [project] version is not the manifests'; set it to theirs",
        "plugin/package.json: name or version is not the manifests'; set both",
        "CHANGELOG.md: its latest release is not the manifests' version; title that release, or set the version to it",
      ],
    ],
    [
      "a plugin/package.json with an unknown field whose version is not the manifests'",
      { "plugin/package.json": JSON.stringify({ ...pkg, version: "9.9.9", typo_key: 1 }) },
      [
        "plugin/package.json: holds a field besides name, version, type, exports; drop it",
        "plugin/package.json: name or version is not the manifests'; set both",
      ],
    ],
    [
      "a plugin/package.json whose name is not the manifests'",
      { "plugin/package.json": JSON.stringify({ ...pkg, name: "other" }) },
      ["plugin/package.json: name or version is not the manifests'; set both"],
    ],
    [
      "a marketplace whose plugin's name is not the manifests'",
      {
        ".claude-plugin/marketplace.json": JSON.stringify({
          name: "n",
          owner: manifest.author,
          plugins: [{ ...plugin, name: "other", source: "./plugin" }],
          description: "m",
        }),
      },
      [
        ".claude-plugin/marketplace.json: the plugin's name or description is not the manifests'; set both to theirs",
      ],
    ],
    [
      "marketplaces whose descriptions differ",
      {
        ".cursor-plugin/marketplace.json": JSON.stringify({
          name: "n",
          owner: manifest.author,
          plugins: [{ ...plugin, source: "plugin" }],
          metadata: { description: "other" },
        }),
      },
      [".cursor-plugin/marketplace.json: name or description differs from the other's; match it"],
    ],
    [
      "a manifest whose license alone differs",
      { "plugin/.devin-plugin/plugin.json": JSON.stringify({ ...manifest, license: "other" }) },
      [
        "plugin/.devin-plugin/plugin.json: license differs from plugin/.claude-plugin/plugin.json; make every manifest the same",
      ],
    ],
    [
      "manifests with an unknown field, an author besides a name, and no homepage or license",
      {
        "plugin/.claude-plugin/plugin.json": JSON.stringify({
          name: "nustack",
          version: "0.1.0",
          description: "d",
          author: { name: "A", email: "e" },
          repository: "https://h/o/n",
          typo_key: 1,
        }),
        "plugin/.cursor-plugin/plugin.json": JSON.stringify({
          name: "nustack",
          version: "0.1.0",
          description: "d",
          author: { name: "A", email: "e" },
          repository: "https://h/o/n",
          typo_key: 1,
        }),
        "plugin/.devin-plugin/plugin.json": JSON.stringify({
          name: "nustack",
          version: "0.1.0",
          description: "d",
          author: { name: "A", email: "e" },
          repository: "https://h/o/n",
          typo_key: 1,
        }),
      },
      [
        "plugin/.claude-plugin/plugin.json: holds a field besides name, version, description, author, homepage, repository, license; drop it",
        "plugin/.claude-plugin/plugin.json: author is missing or malformed; give the author's name, and only that",
        "plugin/.claude-plugin/plugin.json: homepage is missing or malformed; set it to an https URL of at most 2083 characters",
        "plugin/.claude-plugin/plugin.json: license is missing or malformed; fill it in",
        "plugin/.cursor-plugin/plugin.json: holds a field besides name, version, description, author, homepage, repository, license; drop it",
        "plugin/.cursor-plugin/plugin.json: author is missing or malformed; give the author's name, and only that",
        "plugin/.cursor-plugin/plugin.json: homepage is missing or malformed; set it to an https URL of at most 2083 characters",
        "plugin/.cursor-plugin/plugin.json: license is missing or malformed; fill it in",
        "plugin/.devin-plugin/plugin.json: holds a field besides name, version, description, author, homepage, repository, license; drop it",
        "plugin/.devin-plugin/plugin.json: author is missing or malformed; give the author's name, and only that",
        "plugin/.devin-plugin/plugin.json: homepage is missing or malformed; set it to an https URL of at most 2083 characters",
        "plugin/.devin-plugin/plugin.json: license is missing or malformed; fill it in",
      ],
    ],
    [
      "an unknown field in a manifest besides the first",
      { "plugin/.devin-plugin/plugin.json": JSON.stringify({ ...manifest, typo_key: 1 }) },
      [
        "plugin/.devin-plugin/plugin.json: holds a field besides name, version, description, author, homepage, repository, license; drop it",
      ],
    ],
    [
      "a pyproject.toml whose version is not the manifests'",
      {
        "pyproject.toml": `[project]\nversion = "0.0.9"\n\n[tool.commitizen]\ntag_format = "v$version"\nversion_files = ${JSON.stringify(versionFiles)}\n`,
      },
      ["pyproject.toml: [project] version is not the manifests'; set it to theirs"],
    ],
    [
      "a homepage that is not https",
      {
        "plugin/.claude-plugin/plugin.json": JSON.stringify({ ...manifest, homepage: "http://h" }),
        "plugin/.cursor-plugin/plugin.json": JSON.stringify({ ...manifest, homepage: "http://h" }),
        "plugin/.devin-plugin/plugin.json": JSON.stringify({ ...manifest, homepage: "http://h" }),
      },
      [
        "plugin/.claude-plugin/plugin.json: homepage is missing or malformed; set it to an https URL of at most 2083 characters",
        "plugin/.cursor-plugin/plugin.json: homepage is missing or malformed; set it to an https URL of at most 2083 characters",
        "plugin/.devin-plugin/plugin.json: homepage is missing or malformed; set it to an https URL of at most 2083 characters",
      ],
    ],
    [
      "marketplaces with no name, an empty description and an unknown field",
      {
        ".claude-plugin/marketplace.json": JSON.stringify({
          owner: manifest.author,
          plugins: [{ ...plugin, source: "./plugin" }],
          description: "",
          extra: 1,
        }),
        ".cursor-plugin/marketplace.json": JSON.stringify({
          name: "n",
          owner: manifest.author,
          plugins: [{ ...plugin, source: "plugin" }],
          metadata: { description: "d", version: "1" },
        }),
      },
      [
        ".claude-plugin/marketplace.json: holds a field besides name, owner, plugins, description; drop it",
        ".claude-plugin/marketplace.json: name is missing or malformed; set it in kebab case",
        ".claude-plugin/marketplace.json: description is missing or malformed; fill it in",
        ".cursor-plugin/marketplace.json: metadata holds a field besides description; drop it",
      ],
    ],
    [
      "a changelog with no release beside a sound version",
      { "CHANGELOG.md": "## [Unreleased]\n" },
      [
        "CHANGELOG.md: its latest release is not the manifests' version; title that release, or set the version to it",
      ],
    ],
    [
      "a first manifest with a broken homepage, beside two whose homepages differ",
      {
        "plugin/.claude-plugin/plugin.json": JSON.stringify({ ...manifest, homepage: "http://x" }),
        "plugin/.devin-plugin/plugin.json": JSON.stringify({
          ...manifest,
          homepage: "https://other",
        }),
      },
      [
        "plugin/.claude-plugin/plugin.json: homepage is missing or malformed; set it to an https URL of at most 2083 characters",
        "plugin/.devin-plugin/plugin.json: homepage differs from plugin/.cursor-plugin/plugin.json; make every manifest the same",
      ],
    ],
    [
      "manifests whose description, author name and license are blank",
      hosts({ ...manifest, description: "\u200b", author: { name: "\u200b" }, license: "\u200b" }),
      [
        "plugin/.claude-plugin/plugin.json: description is missing or malformed; fill it in",
        "plugin/.claude-plugin/plugin.json: author is missing or malformed; give the author's name, and only that",
        "plugin/.claude-plugin/plugin.json: license is missing or malformed; fill it in",
        "plugin/.cursor-plugin/plugin.json: description is missing or malformed; fill it in",
        "plugin/.cursor-plugin/plugin.json: author is missing or malformed; give the author's name, and only that",
        "plugin/.cursor-plugin/plugin.json: license is missing or malformed; fill it in",
        "plugin/.devin-plugin/plugin.json: description is missing or malformed; fill it in",
        "plugin/.devin-plugin/plugin.json: author is missing or malformed; give the author's name, and only that",
        "plugin/.devin-plugin/plugin.json: license is missing or malformed; fill it in",
      ],
    ],
    [
      "no manifest that parses, with every other metadata file still checked",
      {
        "plugin/.claude-plugin/plugin.json": null,
        "plugin/.cursor-plugin/plugin.json": null,
        "plugin/.devin-plugin/plugin.json": null,
        "plugin/package.json": "{",
        "pyproject.toml": "x =",
        ".claude-plugin/marketplace.json": "{",
      },
      [
        "plugin/.claude-plugin/plugin.json: is missing; restore it",
        "plugin/.cursor-plugin/plugin.json: is missing; restore it",
        "plugin/.devin-plugin/plugin.json: is missing; restore it",
        "pyproject.toml: does not parse as its format; fix its syntax",
        "plugin/package.json: does not parse as its format; fix its syntax",
        ".claude-plugin/marketplace.json: does not parse as its format; fix its syntax",
      ],
    ],
    [
      "a package.json with a field besides its four, type commonjs and another export",
      {
        "plugin/package.json": JSON.stringify({
          ...pkg,
          type: "commonjs",
          exports: { ".": "./x.ts" },
          main: "x",
        }),
      },
      [
        "plugin/package.json: holds a field besides name, version, type, exports; drop it",
        'plugin/package.json: type is not module; set it to "module"',
        'plugin/package.json: exports does not name the loader; set it to { ".": "./opencode.ts" }',
      ],
    ],
    [
      "commitizen settings that leave out package.json and tag a bare version, and a release workflow on every tag",
      {
        ".github/workflows/release.yml":
          'on:\n  push:\n    tags: ["*"]\njobs:\n  ci:\n    needs: tag\n  publish:\n    needs: ci\n',
        "pyproject.toml": `[project]\nversion = "0.1.0"\n\n[tool.commitizen]\ntag_format = "$version"\nversion_files = ${JSON.stringify(versionFiles.slice(0, 3))}\n`,
      },
      [
        "pyproject.toml: [tool.commitizen] version_files is not the files whose version the check compares; list each of plugin/.claude-plugin/plugin.json:version, plugin/.cursor-plugin/plugin.json:version, plugin/.devin-plugin/plugin.json:version, plugin/package.json:version once",
        "pyproject.toml: [tool.commitizen] tag_format is not the release tags' form; set it to v$version",
        '.github/workflows/release.yml: on.push.tags is not ["v*"], the tags tag_format gives; set it to that',
      ],
    ],
    [
      "a release that publishes before CI passes and a release zip built before make check passes",
      {
        ".github/workflows/ci.yml": "jobs:\n  release-zip:\n    runs-on: ubuntu-26.04\n",
        ".github/workflows/release.yml":
          'on:\n  push:\n    tags: ["v*"]\njobs:\n  ci:\n    needs: tag\n  publish:\n    needs: tag\n',
      },
      [
        ".github/workflows/release.yml: jobs.publish.needs is not ci, so a release could publish before CI passes; set it to ci",
        ".github/workflows/ci.yml: jobs.release-zip.needs is not make-check, so the release zip could build from a commit make check fails; set it to make-check",
      ],
    ],
    [
      "a release workflow whose tag job runs a script before it installs bun.lock",
      {
        ".github/workflows/release.yml":
          'on:\n  push:\n    tags: ["v*"]\njobs:\n  tag:\n    steps:\n      - run: bun scripts/release.ts verify-tag v0.0.1\n  ci:\n    needs: tag\n  publish:\n    needs: ci\n',
      },
      [
        ".github/workflows/release.yml: jobs.tag runs bun scripts/ before installing bun.lock; run bun install --frozen-lockfile in that job first, after setup-bun",
      ],
    ],
    [
      "a CI workflow whose release zip job runs a script before it installs bun.lock",
      {
        ".github/workflows/ci.yml":
          "jobs:\n  release-zip:\n    needs: make-check\n    steps:\n      - run: bun scripts/release.ts notes\n",
      },
      [
        ".github/workflows/ci.yml: jobs.release-zip runs bun scripts/ before installing bun.lock; run bun install --frozen-lockfile in that job first, after setup-bun",
      ],
    ],
    [
      "a sync workflow whose sync job runs a script before it installs bun.lock",
      {
        ".github/workflows/sync.yml":
          "jobs:\n  sync:\n    steps:\n      - run: bun scripts/sync.ts list\n",
      },
      [
        ".github/workflows/sync.yml: jobs.sync runs bun scripts/ before installing bun.lock; run bun install --frozen-lockfile in that job first, after setup-bun",
      ],
    ],
    [
      "a sync job that runs a script through bun run before it installs bun.lock",
      syncSteps("      - run: bun run scripts/sync.ts list\n"),
      uninstalled,
    ],
    [
      "a sync job that runs a script by its ./ path before it installs bun.lock",
      syncSteps("      - run: bun ./scripts/sync.ts list\n"),
      uninstalled,
    ],
    [
      "a sync job that only echoes the install before it runs a script",
      syncSteps(
        "      - run: echo bun install --frozen-lockfile\n      - run: bun scripts/sync.ts list\n",
      ),
      uninstalled,
    ],
    [
      "a sync job that installs another folder's bun.lock before it runs a script",
      syncSteps(
        "      - run: bun install --frozen-lockfile --cwd tests/fixtures/smoke\n      - run: bun scripts/sync.ts list\n",
      ),
      uninstalled,
    ],
    [
      "a sync job that runs a script after && before it installs bun.lock",
      syncSteps("      - run: true && bun scripts/sync.ts list\n"),
      uninstalled,
    ],
    [
      "a sync job that runs a script on its run's second line before it installs bun.lock",
      syncSteps("      - run: |\n          export GH_HOST=h\n          bun scripts/sync.ts list\n"),
      uninstalled,
    ],
    [
      "a sync job that runs a script after ; before it installs bun.lock",
      syncSteps("      - run: true; bun scripts/sync.ts list\n"),
      uninstalled,
    ],
    [
      "a sync job that runs a script after | before it installs bun.lock",
      syncSteps("      - run: true | bun scripts/sync.ts list\n"),
      uninstalled,
    ],
    [
      "a sync job that runs a script after || before it installs bun.lock",
      syncSteps("      - run: false || bun scripts/sync.ts list\n"),
      uninstalled,
    ],
    [
      "a sync job that runs a script in backticks before it installs bun.lock",
      syncSteps("      - run: copies=`bun scripts/sync.ts list`\n"),
      uninstalled,
    ],
    [
      "a sync job that runs a script in a command substitution before it installs bun.lock",
      syncSteps("      - run: copies=$(bun scripts/sync.ts list)\n"),
      uninstalled,
    ],
    [
      "a sync job that runs a script after setting a variable, before it installs bun.lock",
      syncSteps("      - run: CI=1 bun scripts/sync.ts list\n"),
      uninstalled,
    ],
    [
      "a sync job that installs bun.lock and runs a script in one step, which passes",
      syncSteps("      - run: bun install --frozen-lockfile && bun scripts/sync.ts list\n"),
      [],
    ],
    [
      "a workflow besides the release, CI and sync workflows whose job runs a script before it installs bun.lock",
      {
        ".github/workflows/other.yaml":
          "jobs:\n  build:\n    steps:\n      - run: bun scripts/check.ts\n",
      },
      [
        ".github/workflows/other.yaml: jobs.build runs bun scripts/ before installing bun.lock; run bun install --frozen-lockfile in that job first, after setup-bun",
      ],
    ],
    [
      "a sync job that runs a script through env before it installs bun.lock",
      syncSteps("      - run: env CI=1 bun scripts/sync.ts list\n"),
      uninstalled,
    ],
    [
      "a sync job that installs bun.lock in another folder by its step's working-directory",
      syncSteps(
        "      - run: bun install --frozen-lockfile\n        working-directory: tests/fixtures/smoke\n      - run: bun scripts/sync.ts list\n",
      ),
      uninstalled,
    ],
    [
      "a sync job that installs bun.lock in another folder by its job's defaults",
      {
        ".github/workflows/sync.yml":
          "jobs:\n  sync:\n    defaults:\n      run:\n        working-directory: tests/fixtures/smoke\n    steps:\n      - run: bun install --frozen-lockfile\n      - run: bun scripts/sync.ts list\n",
      },
      uninstalled,
    ],
    [
      "a sync job that installs bun.lock in another folder by the workflow's defaults",
      {
        ".github/workflows/sync.yml":
          "defaults:\n  run:\n    working-directory: tests/fixtures/smoke\njobs:\n  sync:\n    steps:\n      - run: bun install --frozen-lockfile\n      - run: bun scripts/sync.ts list\n",
      },
      uninstalled,
    ],
    [
      "a sync job that only echoes a script's path, which passes",
      syncSteps("      - run: echo bun scripts/sync.ts list\n"),
      [],
    ],
    [
      "a file directly in plugin/skills/, which no skill folder holds",
      { "plugin/skills/notes.md": "notes\n" },
      ["plugin/skills/notes.md: is not a file the plugin installs; move it out of plugin/"],
    ],
    [
      "a changelog whose latest release is not the manifests' version, past a line and a fenced heading that only name it",
      {
        "CHANGELOG.md":
          "## [Unreleased]\n\n- Name ## [0.1.0] mid-line.\n\n```\n## [0.1.0] - 2026-02-01\n```\n\n## [0.0.9] - 2026-01-01\n\n[Unreleased]: u\n[0.1.0]: v\n[0.0.9]: w\n",
      },
      [
        "CHANGELOG.md: its latest release is not the manifests' version; title that release, or set the version to it",
      ],
    ],
    [
      "a changelog whose newer release names a version no definition defines, above the manifests' version",
      {
        "CHANGELOG.md":
          "## [Unreleased]\n\n## [0.2.0] - 2026-02-01\n\n## [0.1.0] - 2026-01-01\n\n[Unreleased]: u\n[0.1.0]: w\n",
      },
      [
        "CHANGELOG.md: a ## heading names a version in brackets whose label no definition defines; define it, as the release titles it",
      ],
    ],
    [
      "a changelog with a plain ## heading beside its releases, which links nothing and passes",
      {
        "CHANGELOG.md":
          "## Notes\n\n## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\n[Unreleased]: u\n[0.1.0]: w\n",
      },
      [],
    ],
    [
      "a changelog whose only release names the manifests' version with no definition",
      { "CHANGELOG.md": "## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\n[Unreleased]: u\n" },
      [
        "CHANGELOG.md: a ## heading names a version in brackets whose label no definition defines; define it, as the release titles it",
      ],
    ],
    // test_document.py's parts at 94e75bd6, each a ### group of the latest entry, but for those that hold a heading,
    // which ends the group, and ![](logo.png), which the relative-link row refuses.
    [
      "a latest entry whose every group shows something, from text, code or a shown tag",
      {
        "CHANGELOG.md": changelogOf(
          groupsOf([
            "Adds.\n",
            "<!-- Draft: write release notes here --> Adds.\n",
            "<!--\nDraft\n-->\nAdds.\n",
            "[kit]: https://example.com\n\n[kit]\n",
            "&copy;\n",
            "\u200bAdds.\n",
            "<p>&copy;</p>\n",
            "<div>&copy;</div>\n",
            "<p>&#8203;Adds.</p>\n",
            "---\n\nAdds.\n",
            "<hr>Adds.\n",
            "- [ ] <!-- x --> Adds.\n",
            "- [x] <!-- x --> Adds.\n",
            "<b>Adds.</b>\n",
            "<br>Adds.\n",
            "- Adds.\n",
            "1. Adds.\n",
            "<table><tr><td>Adds.</td></tr></table>\n",
            "| Adds. |\n|-|\n| |\n",
            "```\n<!-- -->\n```\n",
            "~~&copy;~~\n",
            "~<!-- x -->Adds.~\n",
            "- Adds. <!-- Draft -->\n",
            "Adds. <b></b>\n",
            "&lt;!-- --&gt;\n",
            "`<!-- -->`\n",
            "    <!-- -->\n",
            '<img alt="Launch" src="https://example.com/a.png">\n',
            '<img src="logo.png">\n',
            '<p><img alt="Launch" src="https://example.com/a.png"></p>\n',
            "<script></script>\n",
            "<style>a{}</style>\n",
            "<textarea>a</textarea>\n",
            "<details></details>\n",
            "- [ ]\n",
            "&nbsp;~~~~&nbsp;~~~~\n",
            "<p>&#1114112;</p>\n",
          ]),
        ),
      },
      [],
    ],
    [
      "a latest entry whose every group shows nothing, from markup with no content",
      {
        "CHANGELOG.md": changelogOf(
          groupsOf([
            "",
            "<!-- Draft: write release notes here -->\n",
            "<!--\nDraft\n-->\n",
            "[kit]: https://example.com\n",
            "&nbsp;\n",
            "\u200b\n",
            "<p>&nbsp;</p>\n",
            "<div>&nbsp;</div>\n",
            "<p>&#8203;</p>\n",
            "---\n",
            "<hr>\n",
            "- [ ] <!-- x -->\n",
            "- [x] <!-- x -->\n",
            "<b></b>\n",
            "<br>\n",
            "-\n",
            "1.\n",
            "<table><tr><td></td></tr></table>\n",
            "| |\n|-|\n| |\n",
            "```\n```\n",
            "~~&nbsp;~~\n",
            "~<!-- x -->~\n",
            '<!-- <img src="https://example.com/a.png"> -->\n',
          ]),
        ),
      },
      [
        "CHANGELOG.md: shows nothing in the G1 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G2 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G3 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G4 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G5 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G6 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G7 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G8 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G9 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G10 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G11 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G12 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G13 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G14 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G15 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G16 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G17 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G18 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G19 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G20 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G21 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G22 group of the entry for 0.1.0; list its changes under it, or remove it",
        "CHANGELOG.md: shows nothing in the G23 group of the entry for 0.1.0; list its changes under it, or remove it",
      ],
    ],
    [
      "a latest entry that ends in an empty group above an older entry that has text",
      {
        "CHANGELOG.md":
          "## [Unreleased]\n\n## [0.1.0] - 2026-02-01\n\n### Added\n\n## [0.0.9] - 2026-01-01\n\nText.\n\n[Unreleased]: u\n[0.1.0]: v\n[0.0.9]: w\n",
      },
      [
        "CHANGELOG.md: shows nothing in the Added group of the entry for 0.1.0; list its changes under it, or remove it",
      ],
    ],
    [
      "a latest entry that uses a reference defined outside it",
      { "CHANGELOG.md": `[ref-x]: https://example.com\n\n${changelogOf("See [ref-x].\n")}` },
      [
        "CHANGELOG.md: uses a reference in the entry for 0.1.0 that is defined elsewhere in the file, so it reads differently on the release page; define it inside the entry for 0.1.0, under a label no other definition in the file uses",
      ],
    ],
    [
      "a latest entry that calls a footnote defined outside it",
      { "CHANGELOG.md": `[^x]: n\n\n${changelogOf("See[^x].\n")}` },
      [
        "CHANGELOG.md: uses a reference in the entry for 0.1.0 that is defined elsewhere in the file, so it reads differently on the release page; define it inside the entry for 0.1.0, under a label no other definition in the file uses",
      ],
    ],
    [
      "a latest entry that links a file and an image by relative links, beside a protocol-relative link, which passes",
      {
        "CHANGELOG.md": changelogOf(
          "See [the readme](README.md), ![](logo.png), [r](/r.md), [t](#top) and [a mirror](//example.com/a).\n",
        ),
      },
      [
        "CHANGELOG.md: links README.md from the entry for 0.1.0, which the release page copies, where a relative link breaks; link it by its full URL",
        "CHANGELOG.md: links logo.png from the entry for 0.1.0, which the release page copies, where a relative link breaks; link it by its full URL",
        "CHANGELOG.md: links /r.md from the entry for 0.1.0, which the release page copies, where a relative link breaks; link it by its full URL",
        "CHANGELOG.md: links #top from the entry for 0.1.0, which the release page copies, where a relative link breaks; link it by its full URL",
      ],
    ],
    [
      "two stray files, a symlink and a changed LICENSE",
      {
        "plugin/notes.txt": "x",
        "plugin/hooks/hooks.json": "{}",
        "plugin/hooks/link.sh": "symlink",
        "plugin/LICENSE": "BSD",
      },
      [
        "plugin/hooks/hooks.json: is not a file the plugin installs; move it out of plugin/",
        "plugin/hooks/link.sh: is a symlink; put the file itself there",
        "plugin/notes.txt: is not a file the plugin installs; move it out of plugin/",
        "plugin/LICENSE: is not the repository's LICENSE; copy that one here",
      ],
    ],
    [
      "a skill file with a suffix past SKILL.md",
      { "plugin/skills/nus-mode/SKILL.mdx": "x" },
      [
        "plugin/skills/nus-mode/SKILL.mdx: is not a file the plugin installs; move it out of plugin/",
      ],
    ],
    [
      "a manifest folder for a host the plugin does not ship to",
      { "plugin/.evil-plugin/plugin.json": "{}" },
      [
        "plugin/.evil-plugin/plugin.json: is not a file the plugin installs; move it out of plugin/",
      ],
    ],
    [
      "a file directly in plugin/ besides its own",
      { "plugin/NOTICE": "x" },
      ["plugin/NOTICE: is not a file the plugin installs; move it out of plugin/"],
    ],
    [
      "a playbook in a principle",
      { "plugin/skills/principle-naming/playbooks/p.md": "# p\n" },
      [
        "plugin/skills/principle-naming/playbooks/p.md: is not a file the plugin installs; move it out of plugin/",
      ],
    ],
    [
      "a playbook in a language skill",
      { "plugin/skills/language-x/playbooks/p.md": "# p\n" },
      [
        "plugin/skills/language-x/playbooks/p.md: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/language-x: has no SKILL.md; add one or remove it",
        "plugin/skills/nus-mode/SKILL.md: ## Languages does not link plugin/skills/language-x/SKILL.md; link it there",
      ],
    ],
    [
      "a file in the mode's playbooks that is not Markdown",
      { "plugin/skills/nus-mode/playbooks/y.txt": "x" },
      [
        "plugin/skills/nus-mode/playbooks/y.txt: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/nus-mode/SKILL.md: ## Playbooks does not link plugin/skills/nus-mode/playbooks/y.txt; link it there",
      ],
    ],
    [
      "a symlinked LICENSE, manifest and marketplace",
      {
        LICENSE: "symlink",
        "plugin/.devin-plugin/plugin.json": "symlink",
        ".claude-plugin/marketplace.json": "symlink",
      },
      [
        "plugin/.devin-plugin/plugin.json: is a symlink; put the file itself there",
        ".claude-plugin/marketplace.json: is a symlink; put the file itself there",
        "LICENSE: is a symlink; put the file itself there",
      ],
    ],
    [
      "no OpenCode loader or changelog, and tier folders holding a file that is no test",
      {
        "plugin/opencode.ts": null,
        "CHANGELOG.md": null,
        "tests/unit/helper.ts": "",
        "tests/integration/helper.ts": "",
      },
      [
        "CHANGELOG.md: is missing; restore it",
        "plugin/opencode.ts: is missing; restore it",
        "tests/unit/helper.ts: is no test, so it does not belong in a tier folder; move it to tests/fixtures/",
        "tests/integration/helper.ts: is no test, so it does not belong in a tier folder; move it to tests/fixtures/",
      ],
    ],
    [
      "a symlinked SKILL.md",
      { "plugin/skills/principle-naming/SKILL.md": "symlink" },
      [
        "plugin/skills/principle-naming/SKILL.md: is a symlink; put the file itself there",
        "plugin/skills/principle-naming: has no SKILL.md; add one or remove it",
        "plugin/skills/nus-mode/SKILL.md: links ../principle-naming/SKILL.md, no file under plugin/; link one, or a full URL",
      ],
    ],
    [
      "a skill folder named out of kebab case",
      { "plugin/skills/Bad/SKILL.md": "---\nname: Bad\ndescription: b\n---\n" },
      [
        "plugin/skills/Bad/SKILL.md: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/Bad: is not named in kebab case; rename it",
      ],
    ],
    [
      "a skill folder named with an underscore",
      { "plugin/skills/nam_ing/SKILL.md": "---\nname: nam_ing\ndescription: n\n---\n" },
      [
        "plugin/skills/nam_ing/SKILL.md: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/nam_ing: is not named in kebab case; rename it",
      ],
    ],
    [
      "a principle with an extra field, the wrong name and no invocation settings",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: naming\ndescription: n\nlicense: x\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: name is not its folder's; use one for both",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
        "plugin/skills/principle-naming/SKILL.md: needs disable-model-invocation: true and triggers: [user]",
      ],
    ],
    [
      "a principle whose triggers are not [user]",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [model]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: needs disable-model-invocation: true and triggers: [user]",
      ],
    ],
    [
      "a principle with triggers but no disable-model-invocation",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: needs disable-model-invocation: true and triggers: [user]",
      ],
    ],
    [
      "a principle whose triggers list starts its entry at the line's start, which passes",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers:\n- user\n---\n",
      },
      [],
    ],
    [
      "a skill folder with no SKILL.md, and one the loader refuses",
      {
        "plugin/skills/principle-naming/SKILL.md": "no frontmatter",
        "plugin/skills/language-x/a.md": "x",
      },
      [
        "plugin/skills/language-x/a.md: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/language-x: has no SKILL.md; add one or remove it",
        "plugin/skills/principle-naming/SKILL.md: has no frontmatter; open it with a line that holds only ---, and save it with no byte order mark and with LF or CRLF line endings",
        "plugin/skills/nus-mode/SKILL.md: ## Languages does not link plugin/skills/language-x/SKILL.md; link it there",
      ],
    ],
    [
      "a skill of exactly the line limit",
      {
        "plugin/skills/principle-naming/SKILL.md": `---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n${"x\n".repeat(494)}`,
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has 500 lines, where it needs under 500; shorten it",
      ],
    ],
    [
      "a skill of exactly the line limit with no final newline",
      {
        "plugin/skills/principle-naming/SKILL.md": `---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n${"x\n".repeat(493)}x`,
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has 500 lines, where it needs under 500; shorten it",
      ],
    ],
    [
      "a skill whose frontmatter nests a mapping",
      {
        "plugin/skills/principle-naming/SKILL.md": `${principle("principle-naming", "n").slice(0, -4)}metadata:\n  sub: x\n---\n`,
      },
      [
        "plugin/skills/principle-naming/SKILL.md: a field or list entry spans lines; keep each to one line",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "a skill whose description goes on in a line holding a dash",
      {
        "plugin/skills/principle-naming/SKILL.md": principle(
          "principle-naming",
          "n\n  and more - words",
        ),
      },
      [
        "plugin/skills/principle-naming/SKILL.md: a field or list entry spans lines; keep each to one line",
      ],
    ],
    [
      "a skill whose frontmatter holds a raw control character",
      { "plugin/skills/principle-naming/SKILL.md": principle("principle-naming", "a\u0001b") },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a control character YAML cannot read; delete it",
      ],
    ],
    [
      "a skill whose frontmatter value holds U+2028",
      { "plugin/skills/principle-naming/SKILL.md": principle("principle-naming", "a\u2028b") },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a NEL, a Unicode line separator or a paragraph separator, which hosts read differently and most editors hide; delete it",
      ],
    ],
    [
      "a skill whose frontmatter value holds U+2029",
      { "plugin/skills/principle-naming/SKILL.md": principle("principle-naming", "a\u2029b") },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a NEL, a Unicode line separator or a paragraph separator, which hosts read differently and most editors hide; delete it",
      ],
    ],
    [
      "a skill whose frontmatter holds a tab in quotes, a !!str tag, an anchor and a trailing comment, which pass",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: principle-naming\ndescription: !!str "a\tb" # c\ndisable-model-invocation: true\ntriggers: &t [user]\n---\n',
      },
      [],
    ],
    [
      "a skill with no frontmatter at the line limit",
      { "plugin/skills/principle-naming/SKILL.md": `# N\n${"x\n".repeat(499)}` },
      [
        "plugin/skills/principle-naming/SKILL.md: has no frontmatter; open it with a line that holds only ---, and save it with no byte order mark and with LF or CRLF line endings",
        "plugin/skills/principle-naming/SKILL.md: has 500 lines, where it needs under 500; shorten it",
      ],
    ],
    [
      "frontmatter with a tag outside YAML's core schema: !!binary",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: !!binary aGk=\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: uses a tag outside YAML's core schema; drop it"],
    ],
    [
      "frontmatter with a tag outside YAML's core schema: !!set",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: !!set {user, model}\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: uses a tag outside YAML's core schema; drop it",
        "plugin/skills/principle-naming/SKILL.md: needs disable-model-invocation: true and triggers: [user]",
      ],
    ],
    [
      "frontmatter with a tag outside YAML's core schema: !!omap",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: !!omap [user: 1]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: uses a tag outside YAML's core schema; drop it",
        "plugin/skills/principle-naming/SKILL.md: needs disable-model-invocation: true and triggers: [user]",
      ],
    ],
    [
      "frontmatter with a tag outside YAML's core schema: !!pairs",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: !!pairs [user: 1]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: uses a tag outside YAML's core schema; drop it",
        "plugin/skills/principle-naming/SKILL.md: needs disable-model-invocation: true and triggers: [user]",
      ],
    ],
    [
      "frontmatter with a tag outside YAML's core schema: !!timestamp",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: !!timestamp 2026-01-01\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: uses a tag outside YAML's core schema; drop it"],
    ],
    [
      "frontmatter with a tag outside YAML's core schema: a local tag",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: !custom x\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: uses a tag outside YAML's core schema; drop it"],
    ],
    [
      "frontmatter with a key that is a sequence",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: {[canary]: x}\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a key that is not text; write the key as text",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a key that is a sequence of sequences",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: {[[canary, b], [c, d]]: x}\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a key that is not text; write the key as text",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a key that is a mapping",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: {{canary: b}: x}\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a key that is not text; write the key as text",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with an empty | block value",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: |\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a blank description; fill it in",
        "plugin/skills/principle-naming/SKILL.md: opens a | or > block value; write the value on its own line",
      ],
    ],
    [
      "frontmatter with an empty > block value",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: >\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a blank description; fill it in",
        "plugin/skills/principle-naming/SKILL.md: opens a | or > block value; write the value on its own line",
      ],
    ],
    [
      "frontmatter with a | block value with an entry under it",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: |\n  - a\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: name is not its folder's; use one for both",
        "plugin/skills/principle-naming/SKILL.md: opens a | or > block value; write the value on its own line",
        "plugin/skills/principle-naming/SKILL.md: a field or list entry spans lines; keep each to one line",
      ],
    ],
    [
      "frontmatter with a > block value with a line under it",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: >\n  a\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: name is not its folder's; use one for both",
        "plugin/skills/principle-naming/SKILL.md: opens a | or > block value; write the value on its own line",
        "plugin/skills/principle-naming/SKILL.md: a field or list entry spans lines; keep each to one line",
      ],
    ],
    [
      "frontmatter with a value continued on a list entry line",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: Use for\n  - naming\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: a field or list entry spans lines; keep each to one line",
      ],
    ],
    [
      "frontmatter with a tab inside a plain value",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: a\tb\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a tab outside quotes; replace it with a space, or quote the value",
      ],
    ],
    [
      "frontmatter with a tab after a plain value",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: a\t\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a tab outside quotes; replace it with a space, or quote the value",
      ],
    ],
    [
      "frontmatter with a key that starts with a digit",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n1a: b\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a line that is neither a field, a key that starts with a letter, a colon and a space before any value, nor a list entry, a dash and a space before its value; rewrite or delete it",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a NEL in a value",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: a\u0085b\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a NEL, a Unicode line separator or a paragraph separator, which hosts read differently and most editors hide; delete it",
      ],
    ],
    [
      "frontmatter with a reused anchor",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: &x n\ndisable-model-invocation: true\ntriggers: &x [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: reuses an anchor's name; give each anchor its own",
      ],
    ],
    [
      "frontmatter with !!str on a sequence",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: !!str [canary]\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a name that is not text; write its text",
        "plugin/skills/principle-naming/SKILL.md: tags a value its tag cannot build; fix the value, or drop the tag",
      ],
    ],
    [
      "frontmatter with !!bool on text",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: !!bool canary\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a disable-model-invocation that is not true or false; set it to true or false",
        "plugin/skills/principle-naming/SKILL.md: tags a value its tag cannot build; fix the value, or drop the tag",
        "plugin/skills/principle-naming/SKILL.md: needs disable-model-invocation: true and triggers: [user]",
      ],
    ],
    [
      "frontmatter with !!int on text",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: !!int canary\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: tags a value its tag cannot build; fix the value, or drop the tag",
      ],
    ],
    [
      "frontmatter with !!null on text",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: !!null canary\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: tags a value its tag cannot build; fix the value, or drop the tag",
      ],
    ],
    [
      "frontmatter with !!seq on a mapping",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: !!seq {a: b}\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: tags a value its tag cannot build; fix the value, or drop the tag",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with !!map on a sequence",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: !!map [a]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: tags a value its tag cannot build; fix the value, or drop the tag",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a | block value under a tag outside YAML's core schema, which gives the block's problem alone",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: !foo |\n  x\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: opens a | or > block value; write the value on its own line",
        "plugin/skills/principle-naming/SKILL.md: a field or list entry spans lines; keep each to one line",
      ],
    ],
    [
      "frontmatter with a | block value on one field and an alias on a later one",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: &a principle-naming\nmetadata: |\n  y\ndescription: *a\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: opens a | or > block value; write the value on its own line",
        "plugin/skills/principle-naming/SKILL.md: a field or list entry spans lines; keep each to one line",
        "plugin/skills/principle-naming/SKILL.md: uses an alias, which a host that reads frontmatter line by line takes as text; write the value out",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with !!float on text",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: !!float canary\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: tags a value its tag cannot build; fix the value, or drop the tag",
      ],
    ],
    [
      "frontmatter with an alias inside its own anchor",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: &loop [*loop]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has frontmatter that nests values more than 200 levels deep; flatten them",
      ],
    ],
    [
      "frontmatter with an alias inside its own anchor, in block form",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: &loop\n  - *loop\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has frontmatter that nests values more than 200 levels deep; flatten them",
      ],
    ],
    [
      "frontmatter with an alias to an earlier anchor",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: &a [user]\nmetadata: [*a, *a]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: uses an alias, which a host that reads frontmatter line by line takes as text; write the value out",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with an alias chain, each anchor holding an alias to the one before",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: {a0: &a0 [], a1: &a1 [*a0], a2: &a2 [*a1], a3: &a3 [*a2]}\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: uses an alias, which a host that reads frontmatter line by line takes as text; write the value out",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with an alias inside its own anchor, before a key that is not text",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: &loop [*loop]\nother: {[k]: x}\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has frontmatter that nests values more than 200 levels deep; flatten them",
      ],
    ],
    [
      "frontmatter with a %YAML directive",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\n%YAML 1.1\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a ... line",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n...\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a line that is neither a field, a key that starts with a letter, a colon and a space before any value, nor a list entry, a dash and a space before its value; rewrite or delete it",
      ],
    ],
    [
      "frontmatter with a %YAML directive after a bare CR",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\r%YAML 1.1\rdescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a list entry indented by a tab",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers:\n\t- user\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a %TAG directive",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\n%TAG !e! tag:example.com,2000:\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a key with no space after its colon",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription:n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a comment line",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\n# a comment\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a line that is neither a field, a key that starts with a letter, a colon and a space before any value, nor a list entry, a dash and a space before its value; rewrite or delete it",
      ],
    ],
    [
      "frontmatter with a double-quoted value across two lines",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: principle-naming\ndescription: "a\nb"\ndisable-model-invocation: true\ntriggers: [user]\n---\n',
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a double-quoted value across a ... line",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: principle-naming\ndescription: "a\n... b"\ndisable-model-invocation: true\ntriggers: [user]\n---\n',
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a byte order mark before a %YAML directive",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "\ufeff---\n%YAML 1.1\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: opens with a byte order mark; save it without one",
      ],
    ],
    [
      "frontmatter with a # right after a flow mapping",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: {a: b}# c\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a quoted list entry across two lines",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers:\n  - "a\n  - b"\n---\n',
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a flow mapping across two lines",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: {a: 1,\nb: 2}\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a quoted value across a - line",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: principle-naming\ndescription: "Use for\n- naming"\ndisable-model-invocation: true\ntriggers: [user]\n---\n',
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a field that ends in two CRs",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\r\r\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a line that is neither a field, a key that starts with a letter, a colon and a space before any value, nor a list entry, a dash and a space before its value; rewrite or delete it",
      ],
    ],
    [
      "frontmatter with a # right after a quoted list entry",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers:\n  - "user"# b\n---\n',
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a # right after a flow sequence",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]# b\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a double-quoted value across a field line",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: principle-naming\ndescription: "a\nname: b"\ndisable-model-invocation: true\ntriggers: [user]\n---\n',
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a # right after a single-quoted value",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: 'principle-naming'# b\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a single-quoted value across a field line",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: 'a\nname: b'\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a tab after a key's colon",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription:\tn\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a line that is neither a field, a key that starts with a letter, a colon and a space before any value, nor a list entry, a dash and a space before its value; rewrite or delete it",
      ],
    ],
    [
      "frontmatter with a double-quoted value across an indented line",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: principle-naming\ndescription: "a\n  b"\ndisable-model-invocation: true\ntriggers: [user]\n---\n',
      },
      [
        "plugin/skills/principle-naming/SKILL.md: a field or list entry spans lines; keep each to one line",
      ],
    ],
    [
      "frontmatter with a # right after a double-quoted value",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: "principle-naming"# b\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n',
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with an empty list entry",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers:\n- \n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has a line that is neither a field, a key that starts with a letter, a colon and a space before any value, nor a list entry, a dash and a space before its value; rewrite or delete it",
        "plugin/skills/principle-naming/SKILL.md: needs disable-model-invocation: true and triggers: [user]",
      ],
    ],
    [
      "frontmatter with a comment line, a separator and a blank line together",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\n# a\nname: principle-naming\ndescription: n\u2028c\ndisable-model-invocation: true\ntriggers: [user]\n\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a NEL, a Unicode line separator or a paragraph separator, which hosts read differently and most editors hide; delete it",
        "plugin/skills/principle-naming/SKILL.md: has a line that is neither a field, a key that starts with a letter, a colon and a space before any value, nor a list entry, a dash and a space before its value; rewrite or delete it",
        "plugin/skills/principle-naming/SKILL.md: holds a blank line; delete it",
      ],
    ],
    [
      "frontmatter with a value nested 5000 deep",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has frontmatter that nests values more than 200 levels deep; flatten them",
      ],
    ],
    [
      "frontmatter with a value nested 200 levels deep, the most it reads",
      {
        "plugin/skills/principle-naming/SKILL.md": `${"---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: "}${"[".repeat(199)}${"]".repeat(199)}\n---\n`,
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a value nested 201 levels deep",
      {
        "plugin/skills/principle-naming/SKILL.md": `${"---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: "}${"[".repeat(200)}${"]".repeat(200)}\n---\n`,
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has frontmatter that nests values more than 200 levels deep; flatten them",
      ],
    ],
    [
      "frontmatter with a value nested 201 levels deep after a quote holding a bracket",
      {
        "plugin/skills/principle-naming/SKILL.md": `${'---\nname: principle-naming\ndescription: see "[docs]" here\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: '}${"[".repeat(200)}${"]".repeat(200)}\n---\n`,
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has frontmatter that nests values more than 200 levels deep; flatten them",
      ],
    ],
    [
      "frontmatter with a value nested 201 levels deep after an apostrophe and a flow list",
      {
        "plugin/skills/principle-naming/SKILL.md": `${"---\nname: principle-naming\ndescription: it's a test\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: "}${"[".repeat(200)}${"]".repeat(200)}\n---\n`,
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has frontmatter that nests values more than 200 levels deep; flatten them",
      ],
    ],
    [
      "frontmatter longer than 4096 characters",
      {
        "plugin/skills/principle-naming/SKILL.md": `---\nname: principle-naming\ndescription: ${"n".repeat(4096)}\ndisable-model-invocation: true\ntriggers: [user]\n---\n`,
      },
      [
        "plugin/skills/principle-naming/SKILL.md: has frontmatter longer than 4096 characters; shorten it",
      ],
    ],
    [
      "a record whose skills nest 200 levels deep, the most it reads",
      {
        "vendored/obsidian-skills.json": JSON.stringify({ ...record, skills: 0 }).replace(
          '"skills":0',
          `"skills":${"[".repeat(199)}${"]".repeat(199)}`,
        ),
      },
      [
        "plugin/skills/knap/LICENSE: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/knap/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
        "plugin/skills: holds 2 modes, where it needs exactly 1; keep one mode, and name each other skill principle-<name> or language-<name>",
        "plugin/skills/knap/SKILL.md: links ../../nowhere.md, no file under plugin/; link one, or a full URL",
        "vendored/obsidian-skills.json: is not a record; make sure skills lists distinct skill names in kebab case",
        "vendored/obsidian-skills.json: is not a record; make sure files maps each file, under one of its skills, to its Git blob",
        "vendored/obsidian-skills.json: is not a record; make sure files gives each skill its SKILL.md and LICENSE",
        ".gitattributes: unsets text for a folder no record in vendored/ names; drop that line",
        ".pre-commit-config.yaml: its &copy exclude names a folder no record in vendored/ names; drop it",
      ],
    ],
    [
      "a record whose skills nest 201 levels deep",
      {
        "vendored/obsidian-skills.json": JSON.stringify({ ...record, skills: 0 }).replace(
          '"skills":0',
          `"skills":${"[".repeat(200)}${"]".repeat(200)}`,
        ),
      },
      [
        "plugin/skills/knap/LICENSE: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/knap/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
        "plugin/skills: holds 2 modes, where it needs exactly 1; keep one mode, and name each other skill principle-<name> or language-<name>",
        "plugin/skills/knap/SKILL.md: links ../../nowhere.md, no file under plugin/; link one, or a full URL",
        "vendored/obsidian-skills.json: nests values more than 200 levels deep; flatten them",
        ".gitattributes: unsets text for a folder no record in vendored/ names; drop that line",
        ".pre-commit-config.yaml: its &copy exclude names a folder no record in vendored/ names; drop it",
      ],
    ],
    [
      "a manifest with a value nested 200 levels deep, the most it reads",
      {
        "plugin/.claude-plugin/plugin.json": JSON.stringify({ ...manifest, x: 0 }).replace(
          '"x":0',
          `"x":${"[".repeat(199)}${"]".repeat(199)}`,
        ),
      },
      [
        "plugin/.claude-plugin/plugin.json: holds a field besides name, version, description, author, homepage, repository, license; drop it",
      ],
    ],
    [
      "a manifest with a value nested 201 levels deep",
      {
        "plugin/.claude-plugin/plugin.json": JSON.stringify({ ...manifest, x: 0 }).replace(
          '"x":0',
          `"x":${"[".repeat(200)}${"]".repeat(200)}`,
        ),
      },
      ["plugin/.claude-plugin/plugin.json: nests values more than 200 levels deep; flatten them"],
    ],
    [
      "frontmatter with two quoted values across lines, the second with a # after its quote",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: "a\n- b"\ndescription: "c\n- d"#e\ndisable-model-invocation: true\ntriggers: [user]\n---\n',
      },
      ["plugin/skills/principle-naming/SKILL.md: has frontmatter that is not valid YAML; fix it"],
    ],
    [
      "frontmatter with a single-pair mapping in a flow sequence, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: [a: [1]]\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a short key, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nt: x\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a list entry that looks like base64, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata:\n  - aGk=\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a value that looks like base64, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: aGk=\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [],
    ],
    [
      "frontmatter with an untagged flow mapping of keys, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: {user, model}\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: needs disable-model-invocation: true and triggers: [user]",
      ],
    ],
    [
      "frontmatter with a date, as text, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: 2026-01-01\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [],
    ],
    [
      "frontmatter with a capital key, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nDescription: B.\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a key with a space and no value, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: \n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with -- inside a value, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: a -- b\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [],
    ],
    [
      "frontmatter with a quoted tab, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: principle-naming\ndescription: "a\tb"\ndisable-model-invocation: true\ntriggers: [user]\n---\n',
      },
      [],
    ],
    [
      "frontmatter with a flow mapping with a text key, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: {canary: x}\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with !!str on a number, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: !!str 1\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [],
    ],
    [
      "frontmatter with !!bool on true, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: !!bool true\ntriggers: [user]\n---\n",
      },
      [],
    ],
    [
      "frontmatter with !!int on an integer, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: !!int 1\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with !!float on a float, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: !!float 1.5\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a # after a space, and one inside a plain value, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          '---\nname: "principle-naming" # b\ndescription: c#d\ndisable-model-invocation: true\ntriggers: [user]\n---\n',
      },
      [],
    ],
    [
      "frontmatter with nested flow collections, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\nmetadata: {kind: c, tags: [[b]]}\n---\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "frontmatter with a comment holding a flow key, which the frontmatter rules read",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\ntags: [a] # {[x]: y}\n---\n# N\n",
      },
      [
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "a mode with no SKILL.md",
      { "plugin/skills/nus-mode/SKILL.md": null },
      [
        "plugin/skills/nus-mode: has no SKILL.md; add one or remove it",
        "plugin/skills/nus-mode/playbooks/p.md: links ../SKILL.md, no file under plugin/; link one, or a full URL",
      ],
    ],
    [
      "a README whose first step calls a footnote a section above defines first and the step defines again",
      {
        "README.md": `[^1]: Above.\n\n### 1️⃣ Install\n\nSee[^1].\n\n[^1]: Note.\n\n### 2️⃣ Use\n\ny\n${rows}`,
      },
      [
        "README.md: ### 1️⃣ Install uses a reference label defined outside that step too, so README and the release page link different targets; define it only inside the step",
      ],
    ],
    ["a missing README", { "README.md": null }, ["README.md: is missing; restore it"]],
    [
      "a README with a table besides its skills tables",
      {
        "README.md": `${quickStart}\n## Other\n\n| A | B |\n| --- | --- |\n| [x](https://h) | y |\n${rows}`,
      },
      [],
    ],
    [
      "a skill whose description runs past the limit, spans lines, holds --- and repeats a field",
      {
        "plugin/skills/principle-naming/SKILL.md": `---\nname: principle-naming\ndescription: ${"d --- ".repeat(200)}\ndisable-model-invocation: true\ntriggers:\n  - user\nextra: |\n  x\nname: principle-naming\n---\n`,
      },
      [
        "plugin/skills/principle-naming/SKILL.md: description has over 1024 characters; shorten it",
        "plugin/skills/principle-naming/SKILL.md: opens a | or > block value; write the value on its own line",
        "plugin/skills/principle-naming/SKILL.md: a field or list entry spans lines; keep each to one line",
        "plugin/skills/principle-naming/SKILL.md: a value holds ---; reword it",
        "plugin/skills/principle-naming/SKILL.md: repeats a field; keep one",
        "plugin/skills/principle-naming/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
      ],
    ],
    [
      "a skill named past the limit",
      {
        "plugin/skills/principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SKILL.md":
          "---\nname: principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SKILL.md: name has over 64 characters; shorten it",
        "plugin/skills/nus-mode/SKILL.md: ## Principles does not link plugin/skills/principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SKILL.md; link it there",
      ],
    ],
    [
      "a principle whose prefix is misspelled",
      {
        "plugin/skills/principal-naming/SKILL.md":
          "---\nname: principal-naming\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      [
        "plugin/skills/principal-naming/SKILL.md: sets disable-model-invocation or triggers, which a mode leaves unset; drop both, or name the folder principle-<name> or language-<name> if it is one",
        "plugin/skills: holds 2 modes, where it needs exactly 1; keep one mode, and name each other skill principle-<name> or language-<name>",
      ],
    ],
    [
      "a principle whose triggers sit in a block list, which is no fault",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndescription: n\ndisable-model-invocation: true\ntriggers:\n  - user\n---\n",
      },
      [],
    ],
    [
      "a blank line in a skill's frontmatter",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\n\ndescription: n\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: holds a blank line; delete it"],
    ],
    [
      "a skill name of exactly 64 characters and a description of exactly 1024",
      {
        "plugin/skills/principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SKILL.md":
          principle(
            "principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "d".repeat(1024),
          ),
        "plugin/skills/nus-mode/SKILL.md": `${mode}- [x](../principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SKILL.md)\n`,
      },
      [],
    ],
    [
      "a skill name of 65 characters and a description of 1025",
      {
        "plugin/skills/principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SKILL.md":
          principle(
            "principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "d".repeat(1025),
          ),
        "plugin/skills/nus-mode/SKILL.md": `${mode}- [x](../principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SKILL.md)\n`,
      },
      [
        "plugin/skills/principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SKILL.md: name has over 64 characters; shorten it",
        "plugin/skills/principle-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/SKILL.md: description has over 1024 characters; shorten it",
      ],
    ],
    [
      "frontmatter with CRLF line ends that repeats a field",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\r\nname: principle-naming\r\nname: principle-naming\r\ndescription: n\r\ndisable-model-invocation: true\r\ntriggers: [user]\r\n---\r\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: repeats a field; keep one"],
    ],
    [
      "a skill with no description, which the loader refuses",
      {
        "plugin/skills/principle-naming/SKILL.md":
          "---\nname: principle-naming\ndisable-model-invocation: true\ntriggers: [user]\n---\n",
      },
      ["plugin/skills/principle-naming/SKILL.md: has no description in its frontmatter; add one"],
    ],
    [
      "a mode that sets triggers and runs past the line limit and the cap",
      {
        "plugin/skills/nus-mode/SKILL.md":
          mode.replace("m\n---", "m\ntriggers: [user]\n---") + "x\n".repeat(4500),
      },
      [
        "plugin/skills/nus-mode/SKILL.md: sets disable-model-invocation or triggers, which a mode leaves unset; drop both, or name the folder principle-<name> or language-<name> if it is one",
        "plugin/skills/nus-mode/SKILL.md: has 4514 lines, where it needs under 500; shorten it",
        "plugin/skills/nus-mode/SKILL.md: body has 9131 characters, over 9000; cut it",
      ],
    ],
    [
      "a mode that sets disable-model-invocation: false",
      {
        "plugin/skills/nus-mode/SKILL.md": mode.replace(
          "m\n---",
          "m\ndisable-model-invocation: false\n---",
        ),
      },
      [
        "plugin/skills/nus-mode/SKILL.md: sets disable-model-invocation or triggers, which a mode leaves unset; drop both, or name the folder principle-<name> or language-<name> if it is one",
      ],
    ],
    [
      "a mode that sets only disable-model-invocation",
      {
        "plugin/skills/nus-mode/SKILL.md": mode.replace(
          "m\n---",
          "m\ndisable-model-invocation: true\n---",
        ),
      },
      [
        "plugin/skills/nus-mode/SKILL.md: sets disable-model-invocation or triggers, which a mode leaves unset; drop both, or name the folder principle-<name> or language-<name> if it is one",
      ],
    ],
    [
      "no mode",
      { "plugin/skills/nus-mode/SKILL.md": null, "plugin/skills/nus-mode/playbooks/p.md": null },
      [
        "plugin/skills: holds 0 modes, where it needs exactly 1; keep one mode, and name each other skill principle-<name> or language-<name>",
      ],
    ],
    [
      "a second mode",
      { "plugin/skills/other-mode/SKILL.md": "---\nname: other-mode\ndescription: o\n---\n" },
      [
        "plugin/skills: holds 2 modes, where it needs exactly 1; keep one mode, and name each other skill principle-<name> or language-<name>",
      ],
    ],
    [
      "a mode under another name",
      {
        "plugin/skills/nus-mode/SKILL.md": null,
        "plugin/skills/nus-mode/playbooks/p.md": null,
        "plugin/skills/core-mode/SKILL.md":
          "---\nname: core-mode\ndescription: m\n---\n# core-mode\n",
        "plugin/skills/core-mode/playbooks/p.md": "# p\n",
      },
      ["plugin/skills: holds a mode not named nus-mode; name its folder nus-mode"],
    ],
    [
      "a mode that lost its index",
      {
        "plugin/skills/nus-mode/SKILL.md":
          "---\nname: nus-mode\ndescription: m\n---\n## Principles\n",
      },
      [
        "plugin/skills/nus-mode/SKILL.md: ## Playbooks does not link plugin/skills/nus-mode/playbooks/p.md; link it there",
        "plugin/skills/nus-mode/SKILL.md: ## Principles does not link plugin/skills/principle-naming/SKILL.md; link it there",
      ],
    ],
    [
      "a principle linked only under ## Playbooks",
      {
        "plugin/skills/nus-mode/SKILL.md": [
          "---\nname: nus-mode\ndescription: m\n---\n# nus-mode\n",
          "## Playbooks\n\n- [p](playbooks/p.md), [n](../principle-naming/SKILL.md)\n",
          "## Principles\n\n- [web](https://x.y)\n",
        ].join("\n"),
      },
      [
        "plugin/skills/nus-mode/SKILL.md: ## Principles does not link plugin/skills/principle-naming/SKILL.md; link it there",
      ],
    ],
    [
      "a principle linked under ## Principles past a # heading, which ends no section",
      {
        "plugin/skills/nus-mode/SKILL.md": mode.replace(
          "## Principles\n\n",
          "## Principles\n\n# Aside\n\n",
        ),
      },
      [],
    ],
    ["a mode body of exactly the cap", { "plugin/skills/nus-mode/SKILL.md": modeOf(9000) }, []],
    [
      "a mode body one character past the cap",
      { "plugin/skills/nus-mode/SKILL.md": modeOf(9001) },
      ["plugin/skills/nus-mode/SKILL.md: body has 9001 characters, over 9000; cut it"],
    ],
    [
      "links that leave plugin/ or reach no file, outside code",
      {
        "AGENTS.md": "# a\n",
        "plugin/skills/nus-mode/playbooks/p.md":
          "[a](../../../../AGENTS.md) [b](gone.md#x) [d](../../../../plugin/LICENSE) `[c](gone.md)`\n",
      },
      [
        "plugin/skills/nus-mode/playbooks/p.md: links ../../../../AGENTS.md, no file under plugin/; link one, or a full URL",
        "plugin/skills/nus-mode/playbooks/p.md: links gone.md#x, no file under plugin/; link one, or a full URL",
        "plugin/skills/nus-mode/playbooks/p.md: links ../../../../plugin/LICENSE, no file under plugin/; link one, or a full URL",
      ],
    ],
    [
      "link definitions, titled and angled links and other schemes, skipping fenced code",
      {
        "plugin/skills/nus-mode/playbooks/p.md": [
          "[a][r] [b](gone.md 'title') [c](<../SKILL.md>) [d](<gone b.md>) [e](file:///etc/passwd) [g](ftp://x)",
          "",
          "[r]: ../../../../AGENTS.md",
          "",
          "- list\n\n  ```\n  [f](gone.md)\n  ```\n",
        ].join("\n"),
      },
      [
        "plugin/skills/nus-mode/playbooks/p.md: links gone.md, no file under plugin/; link one, or a full URL",
        "plugin/skills/nus-mode/playbooks/p.md: links gone b.md, no file under plugin/; link one, or a full URL",
        "plugin/skills/nus-mode/playbooks/p.md: links file:///etc/passwd, no file under plugin/; link one, or a full URL",
        "plugin/skills/nus-mode/playbooks/p.md: links ftp://x, no file under plugin/; link one, or a full URL",
        "plugin/skills/nus-mode/playbooks/p.md: links ../../../../AGENTS.md, no file under plugin/; link one, or a full URL",
      ],
    ],
    [
      "http, mailto and upper-case links, a plugin file's anchor and a fenced link, which pass, and a link to a symlink, which does not",
      {
        "plugin/skills/nus-mode/playbooks/p.md":
          "[h](http://x.y) [m](mailto:a@b.c) [u](HTTPS://X.Y) [s](../SKILL.md#goal) [l](link.md)\n\n```\n[f](fenced.md)\n```\n",
        "plugin/skills/nus-mode/playbooks/link.md": "symlink",
      },
      [
        "plugin/skills/nus-mode/playbooks/link.md: is a symlink; put the file itself there",
        "plugin/skills/nus-mode/SKILL.md: ## Playbooks does not link plugin/skills/nus-mode/playbooks/link.md; link it there",
        "plugin/skills/nus-mode/playbooks/p.md: links link.md, no file under plugin/; link one, or a full URL",
      ],
    ],
    [
      "a link that steps into a folder and back out before it climbs, which stays under plugin/ and passes",
      {
        "plugin/skills/nus-mode/playbooks/p.md":
          "# p\n\n[mode](../SKILL.md)\n[knap](../../../skills/../skills/knap/SKILL.md)\n",
      },
      [],
    ],
    [
      "an absolute link, and a link whose anchor holds steps that would climb",
      {
        "plugin/skills/nus-mode/playbooks/p.md":
          "# p\n\n[abs](/p.md) [mode](../SKILL.md#a/../../../../..)\n",
      },
      [
        "plugin/skills/nus-mode/playbooks/p.md: links the absolute path /p.md, which breaks once the plugin moves; link it by its path from this file",
      ],
    ],
    [
      "a link that climbs out of plugin/ after an empty step",
      { "plugin/skills/nus-mode/playbooks/p.md": "# p\n\n[readme](.//../../../../README.md)\n" },
      [
        "plugin/skills/nus-mode/playbooks/p.md: links .//../../../../README.md, no file under plugin/; link one, or a full URL",
      ],
    ],
    [
      "a link that climbs out of plugin/ after a ./ step",
      { "plugin/skills/nus-mode/playbooks/p.md": "# p\n\n[readme](./../../../../README.md)\n" },
      [
        "plugin/skills/nus-mode/playbooks/p.md: links ./../../../../README.md, no file under plugin/; link one, or a full URL",
      ],
    ],
    [
      "a README whose first step links a relative path and a label only the next step defines",
      {
        "README.md":
          "## Quick start\n\n### 1️⃣ Install\n\n[a](docs/a.md) and [b][missing]\n\n### 2️⃣ Use\n\n[missing]: https://h\n" +
          rows,
      },
      [
        "README.md: ### 1️⃣ Install links docs/a.md; link it by https URL, since the release page copies it",
        "README.md: ### 1️⃣ Install uses a reference label it does not define; define it in that step",
      ],
    ],
    [
      "a README whose first step uses its labels in another case, a collapsed one too",
      {
        "README.md":
          "## Quick start\n\n### 1️⃣ Install\n\n[a](docs/a.md), [Docs][] and [b][DOCS]\n\n[DoCs]: https://h\n\n### 2️⃣ Use\n\nx\n" +
          rows,
      },
      [
        "README.md: ### 1️⃣ Install links docs/a.md; link it by https URL, since the release page copies it",
      ],
    ],
    [
      "a README with neither step the release page copies",
      { "README.md": `# x\n${rows}` },
      [
        "README.md: has no ### 1️⃣ Install heading; add it",
        "README.md: has no ### 2️⃣ Use heading; add it",
      ],
    ],
    [
      "a record with no skills",
      {
        "vendored/obsidian-skills.json": recordText({
          ...record,
          skills: [],
        } as CopyRecord),
      },
      [
        "plugin/skills/knap/LICENSE: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/knap/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
        "plugin/skills: holds 2 modes, where it needs exactly 1; keep one mode, and name each other skill principle-<name> or language-<name>",
        "plugin/skills/knap/SKILL.md: links ../../nowhere.md, no file under plugin/; link one, or a full URL",
        "vendored/obsidian-skills.json: is not a record; make sure skills lists distinct skill names in kebab case",
        "vendored/obsidian-skills.json: is not a record; make sure files maps each file, under one of its skills, to its Git blob",
        ".gitattributes: unsets text for a folder no record in vendored/ names; drop that line",
        ".pre-commit-config.yaml: its &copy exclude names a folder no record in vendored/ names; drop it",
      ],
    ],
    [
      "a record that lists a path out of its skill",
      {
        "vendored/obsidian-skills.json": recordText({
          ...record,
          files: { ...record.files, "knap/../x": "a".repeat(40) },
        } as CopyRecord),
      },
      [
        "vendored/obsidian-skills.json: is not a record; make sure files maps each file, under one of its skills, to its Git blob",
      ],
    ],
    [
      "a record whose folder is no skills folder, which exempts nothing",
      {
        "vendored/obsidian-skills.json": JSON.stringify({
          ...record,
          folder: "plugin",
          skills: ["skills"],
        }),
      },
      [
        "plugin/skills/knap/LICENSE: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/knap/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
        "plugin/skills: holds 2 modes, where it needs exactly 1; keep one mode, and name each other skill principle-<name> or language-<name>",
        "plugin/skills/knap/SKILL.md: links ../../nowhere.md, no file under plugin/; link one, or a full URL",
        "vendored/obsidian-skills.json: is not a record; make sure folder is .agents/skills or plugin/skills",
        "vendored/obsidian-skills.json: is not a record; make sure files maps each file, under one of its skills, to its Git blob",
        "vendored/obsidian-skills.json: is not a record; make sure files gives each skill its SKILL.md and LICENSE",
        ".gitattributes: unsets text for a folder no record in vendored/ names; drop that line",
        ".pre-commit-config.yaml: its &copy exclude names a folder no record in vendored/ names; drop it",
      ],
    ],
    [
      "a record that lists skills named as nus-mode, a language skill and a principle",
      {
        ".gitattributes": `plugin/** text eol=lf\n${["language-x", "nus-mode", "principle-x"].map((skill) => `.agents/skills/${skill}/** -text\n`).join("")}plugin/skills/knap/** -text\n`,
        ".pre-commit-config.yaml": hooks(
          "plugin/skills/knap|\\.agents/skills/language\\-x|\\.agents/skills/nus\\-mode|\\.agents/skills/principle\\-x",
        ),
        "vendored/other.json": recordText({
          ...record,
          folder: ".agents/skills",
          skills: ["language-x", "nus-mode", "principle-x"],
          commit: null,
          files: {},
        } as CopyRecord),
      },
      [
        "vendored/other.json: lists language-x, a name only nustack's own skills hold; drop it from skills",
        "vendored/other.json: lists nus-mode, a name only nustack's own skills hold; drop it from skills",
        "vendored/other.json: lists principle-x, a name only nustack's own skills hold; drop it from skills",
      ],
    ],
    [
      "a record that lists a skill whose name holds principle- past its start, which passes",
      {
        ".gitattributes":
          "plugin/** text eol=lf\n.agents/skills/my-principle-x/** -text\nplugin/skills/knap/** -text\n",
        ".pre-commit-config.yaml": hooks("plugin/skills/knap|\\.agents/skills/my\\-principle\\-x"),
        "vendored/other.json": recordText({
          ...record,
          folder: ".agents/skills",
          skills: ["my-principle-x"],
          commit: null,
          files: {},
        } as CopyRecord),
      },
      [],
    ],
    [
      "a record that copies from this repository",
      { "vendored/obsidian-skills.json": recordText({ ...record, upstream: "https://H/o/n" }) },
      [
        "vendored/obsidian-skills.json: upstream is this repository, whose skills are authored here; copy from another",
      ],
    ],
    [
      "a record that copies from this repository, whose manifests each hold an unknown field",
      {
        ...hosts({ ...manifest, keywords: [] }),
        "vendored/obsidian-skills.json": recordText({
          ...record,
          upstream: "https://h/o/n",
        } as CopyRecord),
      },
      [
        ...[".claude", ".cursor", ".devin"].map(
          (host) =>
            `plugin/${host}-plugin/plugin.json: holds a field besides name, version, description, author, homepage, repository, license; drop it`,
        ),
        "vendored/obsidian-skills.json: upstream is this repository, whose skills are authored here; copy from another",
      ],
    ],
    [
      "a record that copies from this repository, named in another case",
      {
        ...hosts({ ...manifest, repository: "https://H/O/N" }),
        "vendored/obsidian-skills.json": recordText({
          ...record,
          upstream: "https://h/o/n",
        } as CopyRecord),
      },
      [
        "vendored/obsidian-skills.json: upstream is this repository, whose skills are authored here; copy from another",
      ],
    ],
    [
      "a record that copies from this repository by its www host",
      {
        ...hosts({ ...manifest, repository: "https://h/o/n" }),
        "vendored/obsidian-skills.json": recordText({
          ...record,
          upstream: "https://www.h/o/n",
        } as CopyRecord),
      },
      [
        "vendored/obsidian-skills.json: upstream is this repository, whose skills are authored here; copy from another",
      ],
    ],
    [
      "a record that copies from this repository by its www host, named so in the manifests",
      {
        ...hosts({ ...manifest, repository: "https://www.h/o/n" }),
        "vendored/obsidian-skills.json": recordText({
          ...record,
          upstream: "https://h/o/n",
        } as CopyRecord),
      },
      [
        "vendored/obsidian-skills.json: upstream is this repository, whose skills are authored here; copy from another",
      ],
    ],
    [
      "a copy with a changed, an extra and a missing file",
      {
        "plugin/skills/knap/SKILL.md": `${knap}!`,
        "plugin/skills/knap/extra.md": "x",
        "vendored/obsidian-skills.json": recordText({
          ...record,
          files: { ...record.files, "knap/gone.md": "b".repeat(40) },
        } as CopyRecord),
      },
      [
        "plugin/skills/knap/extra.md: is not in vendored/obsidian-skills.json; remove it, or rerun the sync",
        "plugin/skills/knap/SKILL.md: is missing or not the blob vendored/obsidian-skills.json lists; restore it, or rerun the sync",
        "plugin/skills/knap/gone.md: is missing or not the blob vendored/obsidian-skills.json lists; restore it, or rerun the sync",
      ],
    ],
    [
      "a copy whose listed file is a symlink",
      { "plugin/skills/knap/SKILL.md": "symlink" },
      [
        "plugin/skills/knap/SKILL.md: is a symlink; put the file itself there",
        "plugin/skills/knap: has no SKILL.md; add one or remove it",
        "plugin/skills/knap/SKILL.md: is missing or not the blob vendored/obsidian-skills.json lists; restore it, or rerun the sync",
      ],
    ],
    [
      "a record misnamed, and one of the wrong shape",
      {
        "vendored/Bad.json": "{}",
        "vendored/obsidian-skills.json": JSON.stringify({ ...record, commit: null, extra: 1 }),
      },
      [
        "vendored/Bad.json: is not named <copy>.json in kebab case; rename it",
        "vendored/obsidian-skills.json: is not a record; make sure it holds exactly upstream, source, folder, skills, commit and files",
        "vendored/obsidian-skills.json: is not a record; make sure files is {} while commit is null",
      ],
    ],
    [
      "a record that breaks each clause of a record's shape",
      {
        "vendored/obsidian-skills.json": JSON.stringify({
          upstream: "http://h/o/n",
          source: "../s",
          folder: "plugin",
          skills: ["knap", "knap"],
          commit: "abc",
          files: { "other/SKILL.md": "x" },
        }),
      },
      [
        "plugin/skills/knap/LICENSE: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/knap/SKILL.md: holds a field outside name, description, disable-model-invocation, triggers; drop it",
        "plugin/skills: holds 2 modes, where it needs exactly 1; keep one mode, and name each other skill principle-<name> or language-<name>",
        "plugin/skills/knap/SKILL.md: links ../../nowhere.md, no file under plugin/; link one, or a full URL",
        problem(
          "vendored/obsidian-skills.json: is not a record; make sure upstream is https://<host>/<owner>/<name>",
        ),
        "vendored/obsidian-skills.json: is not a record; make sure source is a folder path in upstream",
        "vendored/obsidian-skills.json: is not a record; make sure folder is .agents/skills or plugin/skills",
        "vendored/obsidian-skills.json: is not a record; make sure skills lists distinct skill names in kebab case",
        "vendored/obsidian-skills.json: is not a record; make sure commit is null or a full commit SHA",
        "vendored/obsidian-skills.json: is not a record; make sure files maps each file, under one of its skills, to its Git blob",
        "vendored/obsidian-skills.json: is not a record; make sure files gives each skill its SKILL.md and LICENSE",
        ".gitattributes: unsets text for a folder no record in vendored/ names; drop that line",
        ".pre-commit-config.yaml: its &copy exclude names a folder no record in vendored/ names; drop it",
      ],
    ],
    [
      "a record whose commit is in upper case",
      { "vendored/obsidian-skills.json": recordText({ ...record, commit: "A".repeat(40) }) },
      [
        "vendored/obsidian-skills.json: is not a record; make sure commit is null or a full commit SHA",
      ],
    ],
    [
      "a record whose commit is 41 characters long",
      { "vendored/obsidian-skills.json": recordText({ ...record, commit: "a".repeat(41) }) },
      [
        "vendored/obsidian-skills.json: is not a record; make sure commit is null or a full commit SHA",
      ],
    ],
    [
      "a record whose blob is in upper case",
      {
        "vendored/obsidian-skills.json": recordText({
          ...record,
          files: { ...record.files, "knap/LICENSE": blobOf(bytes("MIT")).toUpperCase() },
        }),
      },
      [
        "vendored/obsidian-skills.json: is not a record; make sure files maps each file, under one of its skills, to its Git blob",
      ],
    ],
    [
      "a record indented by four spaces",
      {
        "vendored/obsidian-skills.json": recordText(record).replace(/^ +/gm, (indent) =>
          indent.repeat(2),
        ),
      },
      [
        "vendored/obsidian-skills.json: is not laid out as the sync writes a record; write it with two-space indents, its keys in the order upstream, source, folder, skills, commit, files, its files sorted and one final newline",
      ],
    ],
    [
      "a record with no final newline",
      { "vendored/obsidian-skills.json": recordText(record).trimEnd() },
      [
        "vendored/obsidian-skills.json: is not laid out as the sync writes a record; write it with two-space indents, its keys in the order upstream, source, folder, skills, commit, files, its files sorted and one final newline",
      ],
    ],
    [
      "a record whose keys are in reverse order",
      {
        "vendored/obsidian-skills.json": `${JSON.stringify(Object.fromEntries(Object.entries(record).reverse()), null, 2)}\n`,
      },
      [
        "vendored/obsidian-skills.json: is not laid out as the sync writes a record; write it with two-space indents, its keys in the order upstream, source, folder, skills, commit, files, its files sorted and one final newline",
      ],
    ],
    [
      "a record whose files are not sorted",
      {
        "vendored/obsidian-skills.json": recordText(record).replace(
          /(\s+)("knap\/LICENSE": "\w+"),(\s+)("knap\/SKILL\.md": "\w+")/,
          "$1$4,$3$2",
        ),
      },
      [
        "vendored/obsidian-skills.json: is not laid out as the sync writes a record; write it with two-space indents, its keys in the order upstream, source, folder, skills, commit, files, its files sorted and one final newline",
      ],
    ],
    [
      "a record whose skill name runs past 64 characters",
      {
        "vendored/other.json": JSON.stringify({
          ...record,
          skills: ["a".repeat(65)],
          commit: null,
          files: {},
        }),
      },
      ["vendored/other.json: is not a record; make sure each skill name is at most 64 characters"],
    ],
    [
      "a record whose commit is set while files is {}",
      { "vendored/other.json": JSON.stringify({ ...record, skills: ["other"], files: {} }) },
      ["vendored/other.json: is not a record; make sure files lists a file once commit is set"],
    ],
    [
      "a record whose files key names a skill folder itself",
      {
        "vendored/other.json": JSON.stringify({
          ...record,
          skills: ["other"],
          files: {
            other: "a".repeat(40),
            "other/LICENSE": "a".repeat(40),
            "other/SKILL.md": "a".repeat(40),
          },
        }),
      },
      [
        "vendored/other.json: is not a record; make sure files maps each file, under one of its skills, to its Git blob",
      ],
    ],
    [
      "a record whose upstream, folder and commit are not strings",
      {
        "vendored/other.json": JSON.stringify({
          ...record,
          upstream: ["https://github.com/o/n"],
          folder: ["plugin/skills"],
          skills: ["other"],
          commit: ["a".repeat(40)],
          files: { "other/LICENSE": "a".repeat(40), "other/SKILL.md": "a".repeat(40) },
        }),
      },
      [
        "vendored/other.json: is not a record; make sure upstream is https://<host>/<owner>/<name>",
        "vendored/other.json: is not a record; make sure folder is .agents/skills or plugin/skills",
        "vendored/other.json: is not a record; make sure commit is null or a full commit SHA",
      ],
    ],
    [
      "a record whose files is []",
      {
        "vendored/other.json": JSON.stringify({
          ...record,
          skills: ["other"],
          commit: null,
          files: [],
        }),
      },
      [
        "vendored/other.json: is not a record; make sure files maps each file, under one of its skills, to its Git blob",
      ],
    ],
    [
      "a record whose skill nests in another record's folder",
      {
        "vendored/other.json": recordText({
          ...record,
          skills: ["knap/inner"],
          commit: null,
          files: {},
        } as CopyRecord),
      },
      [
        "vendored/other.json: is not a record; make sure skills lists distinct skill names in kebab case",
      ],
    ],
    [
      "a copy two records name, guards that miss it or name no copy, and a LICENSE no record names",
      {
        "vendored/other.json": recordText(record),
        ".gitattributes": "plugin/** text eol=lf\nplugin/skills/gone/** -text\n",
        ".pre-commit-config.yaml": hooks("plugin/skills/gone"),
        ".agents/skills/stray/LICENSE": "MIT",
      },
      [
        "plugin/skills/knap: is named by more than one record in vendored/; keep it in one",
        ".gitattributes: does not unset text for plugin/skills/knap; add the line plugin/skills/knap/** -text",
        ".gitattributes: unsets text for a folder no record in vendored/ names; drop that line",
        ".pre-commit-config.yaml: its &copy exclude does not name plugin/skills/knap; add it",
        ".pre-commit-config.yaml: its &copy exclude names a folder no record in vendored/ names; drop it",
        ".agents/skills/stray/LICENSE: sits in a skill folder no record in vendored/ names; write its record, or remove the copy",
      ],
    ],
    [
      "no hook config",
      { ".pre-commit-config.yaml": null },
      [".pre-commit-config.yaml: is missing; restore it"],
    ],
    [
      "no .gitattributes, and hooks with no &copy exclude",
      { ".gitattributes": null, ".pre-commit-config.yaml": "repos: []\n" },
      [
        ".gitattributes: is missing; restore it",
        ".pre-commit-config.yaml: has no exclude: &copy ^(?:<folder>|...)/ naming the copies; add it",
        ".pre-commit-config.yaml: its &copy exclude does not name plugin/skills/knap; add it",
      ],
    ],
    [
      "a .gitattributes line after the lines unsetting text, which can set text on a copy again",
      { ".gitattributes": "plugin/skills/knap/** -text\nplugin/** text eol=lf\n" },
      [
        ".gitattributes: sets attributes after a line unsetting text, which can set text on a copy again; end the file with the lines unsetting text",
      ],
    ],
    [
      "a .gitattributes line unsetting text on a path that is no copy's folder",
      { ".gitattributes": "plugin/** text eol=lf\nREADME.md -text\nplugin/skills/knap/** -text\n" },
      [".gitattributes: unsets text on a path that is no copy's folder; drop -text from that line"],
    ],
    [
      "lines unsetting text out of order",
      {
        ".gitattributes":
          "plugin/** text eol=lf\nplugin/skills/knap/** -text\nplugin/skills/gone/** -text\n",
      },
      [
        ".gitattributes: unsets text for a folder no record in vendored/ names; drop that line",
        ".gitattributes: its lines unsetting text are out of order; sort them",
      ],
    ],
    [
      "no record, with hooks that skip nothing and no line unsetting text",
      {
        "vendored/obsidian-skills.json": null,
        "plugin/skills/knap/LICENSE": null,
        "plugin/skills/knap/SKILL.md": null,
        ".gitattributes": "plugin/** text eol=lf\n",
        ".pre-commit-config.yaml": "repos: []\n",
      },
      [],
    ],
    [
      "guards only in comments",
      {
        ".gitattributes": "plugin/** text eol=lf\n# plugin/skills/knap/** -text\n",
        ".pre-commit-config.yaml": "# exclude: &copy ^(?:plugin/skills/knap)/\n",
      },
      [
        ".gitattributes: does not unset text for plugin/skills/knap; add the line plugin/skills/knap/** -text",
        ".pre-commit-config.yaml: has no exclude: &copy ^(?:<folder>|...)/ naming the copies; add it",
        ".pre-commit-config.yaml: its &copy exclude does not name plugin/skills/knap; add it",
      ],
    ],
    [
      "guards with more after the copy's folder",
      {
        ".gitattributes": "plugin/** text eol=lf\nplugin/skills/knap/** -text eol=lf\n",
        ".pre-commit-config.yaml": "exclude: &copy ^(?:plugin/skills/knap)/x\n",
      },
      [
        ".gitattributes: does not unset text for plugin/skills/knap; add the line plugin/skills/knap/** -text",
        ".gitattributes: unsets text on a path that is no copy's folder; drop -text from that line",
        ".pre-commit-config.yaml: has no exclude: &copy ^(?:<folder>|...)/ naming the copies; add it",
        ".pre-commit-config.yaml: its &copy exclude does not name plugin/skills/knap; add it",
      ],
    ],
    [
      "no line keeping plugin/ at LF",
      { ".gitattributes": "plugin/** text\nplugin/skills/knap/** -text\n" },
      [
        ".gitattributes: does not set plugin/** text eol=lf; add that line above the lines that unset text",
      ],
    ],
    [
      "a file named past LICENSE in a skill folder no record names, which is no copy's license",
      { ".agents/skills/stray/LICENSE.md": "MIT" },
      [],
    ],
    [
      "skills tables with a skill twice, one missing, one the plugin lacks and a row linking two",
      {
        "README.md": `${quickStart}\n## Skills\n\n${TABLE_HEAD}${[
          "| [nus-mode](plugin/skills/nus-mode/SKILL.md) | m |",
          "| [nus-mode](plugin/skills/nus-mode/SKILL.md) | again |",
          "| [gone](plugin/skills/gone/SKILL.md) | g |",
          "| [knap](plugin/skills/knap/SKILL.md) and [k](plugin/skills/knap/SKILL.md) | k |",
        ].join("\n")}\n`,
      },
      [
        "README.md: a skills-table row links other than one SKILL.md; link its skill's alone",
        "README.md: a skills-table row links a skill plugin/skills/ does not hold; drop that row",
        "README.md: more than one skills-table row links plugin/skills/nus-mode; keep one",
        "README.md: no skills-table row links plugin/skills/principle-naming; add one",
      ],
    ],
    [
      "a skills table whose rows link a skill's SKILL.md under another folder and past a suffix",
      {
        "README.md": `${quickStart}\n## Skills\n\n${TABLE_HEAD}${[
          "| [nus-mode](plugin/skills/nus-mode/SKILL.md) | m |",
          "| [principle-naming](plugin/skills/principle-naming/SKILL.mdx) | n |",
          "| [knap](plugin/skills/x/plugin/skills/knap/SKILL.md) | k |",
        ].join("\n")}\n`,
      },
      [
        "README.md: a skills-table row links other than one SKILL.md; link its skill's alone",
        "README.md: no skills-table row links plugin/skills/knap; add one",
        "README.md: no skills-table row links plugin/skills/principle-naming; add one",
      ],
    ],
    [
      "a README whose second step uses a shortcut label only a later section defines, beside a defined one and code",
      {
        "README.md":
          "## Quick start\n\n### 1️⃣ Install\n\n[ok] and `[code]`\n\n[ok]: https://h\n\n### 2️⃣ Use\n\n[docs]\n\n## Then\n\n[docs]: https://h\n" +
          rows,
      },
      ["README.md: ### 2️⃣ Use uses a reference label it does not define; define it in that step"],
    ],
    [
      "a README whose first step shows an image by a label only a later section defines",
      {
        "README.md":
          "## Quick start\n\n### 1️⃣ Install\n\n![logo][img]\n\n### 2️⃣ Use\n\nx\n" +
          rows +
          "\n[img]: https://h/i.png\n",
      },
      [
        "README.md: ### 1️⃣ Install uses a reference label it does not define; define it in that step",
      ],
    ],
    [
      "a README whose second step holds a task-list box, escaped brackets and indented code, as labels a later section defines",
      {
        "README.md":
          "## Quick start\n\n### 1️⃣ Install\n\nx\n\n### 2️⃣ Use\n\n- [x] item\n\n\\[not a ref\\]\n\n    [ -f x ]\n" +
          rows +
          "\n[x]: https://h\n[not a ref]: https://h\n[ -f x ]: https://h\n",
      },
      [],
    ],
    [
      "a README whose first step links past a fenced # line and a deeper heading, and whose second step runs to the end",
      {
        "README.md":
          rows +
          "\n## Quick start\n\n### 1️⃣ Install\n\n```sh\n# comment\n```\n\n[a](docs/a.md)\n\n#### More\n\n[b](docs/b.md)\n\n### 2️⃣ Use\n\n[c](docs/c.md)",
      },
      [
        "README.md: ### 1️⃣ Install links docs/a.md; link it by https URL, since the release page copies it",
        "README.md: ### 1️⃣ Install links docs/b.md; link it by https URL, since the release page copies it",
        "README.md: ### 2️⃣ Use links docs/c.md; link it by https URL, since the release page copies it",
      ],
    ],
    [
      "a README whose second step, under a heading that names more, uses a collapsed label only a later section defines",
      {
        "README.md": `### 1️⃣ Install\n\nx\n\n### 2️⃣ Use - in any host\n\n[x][]\n${rows}\n[x]: https://h\n`,
      },
      ["README.md: ### 2️⃣ Use uses a reference label it does not define; define it in that step"],
    ],
    [
      "a README whose first step a setext heading ends, above a relative link",
      {
        "README.md": `### 1️⃣ Install\n\nx\n\nMore\n---\n\n[a](docs/a.md)\n\n### 2️⃣ Use\n\ny\n${rows}`,
      },
      [],
    ],
    [
      "a README whose first step an indented heading ends, above a relative link",
      {
        "README.md": `### 1️⃣ Install\n\nx\n\n  ## More\n\n[a](docs/a.md)\n\n### 2️⃣ Use\n\ny\n${rows}`,
      },
      [],
    ],
    [
      "a README whose second step a heading with a tab after its marker ends, above a relative link",
      {
        "README.md": `### 1️⃣ Install\n\nx\n\n### 2️⃣ Use\n\ny\n\n##\tMore\n\n[a](docs/a.md)\n${rows}`,
      },
      [],
    ],
    [
      "a README whose second step a bare ## ends, above a relative link",
      { "README.md": `### 1️⃣ Install\n\nx\n\n### 2️⃣ Use\n\ny\n\n##\n\n[a](docs/a.md)\n${rows}` },
      [],
    ],
    [
      "a README whose first step holds indented code that looks like a heading, above a relative link",
      {
        "README.md": `### 1️⃣ Install\n\nx\n\n    ## code\n\n[a](docs/a.md)\n\n### 2️⃣ Use\n\ny\n${rows}`,
      },
      [
        "README.md: ### 1️⃣ Install links docs/a.md; link it by https URL, since the release page copies it",
      ],
    ],
    [
      "a README whose first step nests a label only a later section defines inside a link",
      {
        "README.md": `### 1️⃣ Install\n\n[[docs][x]](https://h/y)\n\n### 2️⃣ Use\n\ny\n${rows}\n[x]: https://h\n`,
      },
      [
        "README.md: ### 1️⃣ Install uses a reference label it does not define; define it in that step",
      ],
    ],
    [
      "a README whose first step holds a relative link only in indented code, escaped brackets, an HTML comment and a code span",
      {
        "README.md": `### 1️⃣ Install\n\n    [a](docs/a.md)\n\n\\[b\\](docs/b.md)\n\n<!-- [c](docs/c.md) -->\n\n\`[d](docs/d.md)\`\n\n### 2️⃣ Use\n\ny\n${rows}`,
      },
      [],
    ],
    [
      "a README whose first step uses a label only a blockquote in a later section defines",
      { "README.md": `### 1️⃣ Install\n\n[a][x]\n\n### 2️⃣ Use\n\ny\n${rows}\n> [x]: docs/a.md\n` },
      [
        "README.md: ### 1️⃣ Install uses a reference label it does not define; define it in that step",
      ],
    ],
    [
      "a README whose first step defines a label in a blockquote by a relative path",
      { "README.md": `### 1️⃣ Install\n\n[a][x]\n\n> [x]: docs/a.md\n\n### 2️⃣ Use\n\ny\n${rows}` },
      [
        "README.md: ### 1️⃣ Install links docs/a.md; link it by https URL, since the release page copies it",
      ],
    ],
    [
      "a README whose first step calls a footnote only a later section defines",
      { "README.md": `### 1️⃣ Install\n\nSee[^1].\n\n### 2️⃣ Use\n\ny\n${rows}\n[^1]: Note.\n` },
      [
        problem(
          "README.md: ### 1️⃣ Install uses a reference label it does not define; define it in that step",
        ),
      ],
    ],
    [
      "a README whose first step calls a footnote it defines",
      { "README.md": `### 1️⃣ Install\n\nSee[^1].\n\n[^1]: Note.\n\n### 2️⃣ Use\n\ny\n${rows}` },
      [],
    ],
    [
      "a README whose first step defines a label again that a section above it defines first",
      {
        "README.md": `[x]: https://a\n\n### 1️⃣ Install\n\n[a][x]\n\n[x]: https://h\n\n### 2️⃣ Use\n\ny\n${rows}`,
      },
      [
        problem(
          "README.md: ### 1️⃣ Install uses a reference label defined outside that step too, so README and the release page link different targets; define it only inside the step",
        ),
      ],
    ],
    [
      "a README whose first step links an https URL with its scheme in upper case",
      { "README.md": `### 1️⃣ Install\n\n[a](HTTPS://h/y)\n\n### 2️⃣ Use\n\ny\n${rows}` },
      [],
    ],
    [
      "a README whose first step links a URL that holds https:// past its start",
      { "README.md": `### 1️⃣ Install\n\n[a](xhttps://h/y)\n\n### 2️⃣ Use\n\ny\n${rows}` },
      [
        "README.md: ### 1️⃣ Install links xhttps://h/y; link it by https URL, since the release page copies it",
      ],
    ],
    [
      "a README whose first step links an http URL",
      { "README.md": `### 1️⃣ Install\n\n[a](http://h/y)\n\n### 2️⃣ Use\n\ny\n${rows}` },
      [
        "README.md: ### 1️⃣ Install links http://h/y; link it by https URL, since the release page copies it",
      ],
    ],
    [
      "a README whose second step holds a checked task-list box a later section defines as a label",
      { "README.md": `### 1️⃣ Install\n\nx\n\n### 2️⃣ Use\n\n- [x] item\n${rows}\n[x]: https://h\n` },
      [],
    ],
    [
      "a plugin file that links only in escaped brackets, indented code and an HTML comment",
      {
        "plugin/skills/nus-mode/playbooks/p.md":
          "# p\n\n[mode](../SKILL.md) \\[x\\](../nowhere.md)\n\n    [y](../nowhere.md)\n\n<!-- [z](../nowhere.md) -->\n",
      },
      [],
    ],
    [
      "a plugin file that defines a label by a missing file in a blockquote and in a list",
      {
        "plugin/skills/nus-mode/playbooks/p.md":
          "# p\n\n[mode](../SKILL.md)\n\n> [q]: gone.md\n\n- [l]: lost.md\n",
      },
      [
        "plugin/skills/nus-mode/playbooks/p.md: links gone.md, no file under plugin/; link one, or a full URL",
        "plugin/skills/nus-mode/playbooks/p.md: links lost.md, no file under plugin/; link one, or a full URL",
      ],
    ],
    [
      "a mode that indexes a principle under a setext ## heading",
      {
        "plugin/skills/nus-mode/SKILL.md": [
          "---\nname: nus-mode\ndescription: m\n---\n# nus-mode\n",
          "Playbooks\n---------\n\n- [p](playbooks/p.md)\n",
          "Principles\n----------\n\n- [n](../principle-naming/SKILL.md)\n",
        ].join("\n"),
      },
      [],
    ],
    [
      "a mode that indexes a principle under a ### heading inside ## Principles",
      {
        "plugin/skills/nus-mode/SKILL.md": [
          "---\nname: nus-mode\ndescription: m\n---\n# nus-mode\n",
          "## Playbooks\n\n- [p](playbooks/p.md)\n",
          "## Principles\n\n### Code\n\n- [n](../principle-naming/SKILL.md)\n",
        ].join("\n"),
      },
      [],
    ],
    [
      "a mode that links a principle under ## Principles only in an HTML comment",
      {
        "plugin/skills/nus-mode/SKILL.md": [
          "---\nname: nus-mode\ndescription: m\n---\n# nus-mode\n",
          "## Playbooks\n\n- [p](playbooks/p.md)\n",
          "## Principles\n\n<!-- [n](../principle-naming/SKILL.md) -->\n",
        ].join("\n"),
      },
      [
        "plugin/skills/nus-mode/SKILL.md: ## Principles does not link plugin/skills/principle-naming/SKILL.md; link it there",
      ],
    ],
    [
      "a skills table that links a skill only in a code span",
      {
        "README.md": `${quickStart}${rowsOf(["nus-mode", "principle-naming"])}| \`[knap](plugin/skills/knap/SKILL.md)\` | k |\n`,
      },
      ["README.md: no skills-table row links plugin/skills/knap; add one"],
    ],
    [
      "a record whose skill is named out of kebab case and whose blob is no SHA",
      {
        "vendored/other.json": recordText({
          ...record,
          upstream: "https://github.com/o/other",
          folder: ".agents/skills",
          skills: ["Knap"],
          files: { "Knap/LICENSE": "a".repeat(40), "Knap/SKILL.md": "x" },
        } as CopyRecord),
      },
      [
        "vendored/other.json: is not a record; make sure skills lists distinct skill names in kebab case",
        "vendored/other.json: is not a record; make sure files maps each file, under one of its skills, to its Git blob",
      ],
    ],
  ])("checks %s", async (_, changes, problems) => {
    expect(await check(tree(changes))).toEqual(problems.map(problem))
  })

  test.each(rewriting)("refuses the hook %s with no exclude: *copy", async (id) => {
    const config = hooks("plugin/skills/knap", (other) =>
      other === id ? `      - id: ${other}\n` : `      - id: ${other}\n        exclude: *copy\n`,
    )
    expect(await check(tree({ ".pre-commit-config.yaml": config }))).toEqual([
      problem(`.pre-commit-config.yaml: ${id} does not exclude the copies; give it exclude: *copy`),
    ])
  })

  test.each(rewriting)("refuses the hook %s excluding another folder", async (id) => {
    const config = hooks(
      "plugin/skills/knap",
      (other) => `      - id: ${other}\n        exclude: ${other === id ? "^docs/" : "*copy"}\n`,
    )
    expect(await check(tree({ ".pre-commit-config.yaml": config }))).toEqual([
      problem(`.pre-commit-config.yaml: ${id} does not exclude the copies; give it exclude: *copy`),
    ])
  })

  test.each(rewriting)("refuses hooks with no %s", async (id) => {
    const config = hooks("plugin/skills/knap", (other) =>
      other === id ? "" : `      - id: ${other}\n        exclude: *copy\n`,
    )
    expect(await check(tree({ ".pre-commit-config.yaml": config }))).toEqual([
      problem(`.pre-commit-config.yaml: has no ${id} hook; restore it`),
    ])
  })

  test.each(["https://user:token@h/o/n", "https://h/o/n.git"])(
    "refuses the upstream %s",
    async (upstream) => {
      const changes = { "vendored/obsidian-skills.json": recordText({ ...record, upstream }) }
      expect(await check(tree(changes))).toEqual([
        problem(
          "vendored/obsidian-skills.json: is not a record; make sure upstream is https://<host>/<owner>/<name>",
        ),
      ])
    },
  )

  test("tells a file that is not UTF-8 from one whose syntax is bad", async () => {
    const changed = new Map(tree({ "plugin/.devin-plugin/plugin.json": "{" }))
    changed.set("plugin/package.json", new Uint8Array([0xff]))
    expect(await check(changed)).toEqual([
      problem("plugin/.devin-plugin/plugin.json: does not parse as its format; fix its syntax"),
      problem("plugin/package.json: is not valid UTF-8; save it as UTF-8"),
    ])
  })

  test("reports a Markdown file under plugin/ that is not UTF-8", async () => {
    const changed = new Map(tree())
    changed.set("plugin/skills/nus-mode/playbooks/p.md", new Uint8Array([0xff]))
    expect(await check(changed)).toEqual([
      problem("plugin/skills/nus-mode/playbooks/p.md: is not valid UTF-8; save it as UTF-8"),
    ])
  })

  test("reads only the loader's own error as a problem, and rethrows any other", async () => {
    const { SkillFile } = await import("../../../plugin/opencode.ts")
    const failure = new TypeError("a bug")
    const decode = spyOn(SkillFile, "decode").mockImplementation(() => {
      throw failure
    })
    try {
      await expect(check(tree())).rejects.toBe(failure)
    } finally {
      decode.mockRestore()
    }
  })
})
