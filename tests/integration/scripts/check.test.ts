/**
 * readTree reads what Git tracks or would track, skipping what it ignores and reading a symlink as one, and stops on a
 * name that is not UTF-8. Run as a command, the check stops on an entry it cannot read, naming its path and the fix, and on a plugin/package.json the loader cannot
 * load, prints its rules on --help, and prints its usage, exiting 1, on any other argument.
 */
import { afterEach, expect, test } from "bun:test"
import { chmod, copyFile, mkdir, rm, symlink, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { readTree } from "../../../scripts/check.ts"
import { git } from "../../../scripts/git.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"
import "../../fixtures/scripts/git.ts"

const folders = new TemporaryFolders()
afterEach(() => folders.clear())

test("reads tracked and untracked files under every path the rules cover, of tests/ only the tier folders, and nothing Git ignores or the working tree lacks", async () => {
  const root = await folders.make()
  await git(["init", "-q"], root)
  for (const folder of [
    "plugin",
    "tests/unit",
    "tests/integration",
    "tests/fixtures",
    ".agents/skills/s",
    ".claude-plugin",
    ".cursor-plugin",
    ".github/workflows",
    "vendored",
  ])
    await mkdir(join(root, folder), { recursive: true })
  const files = {
    ".gitignore": ".DS_Store\nnode_modules/\n",
    "plugin/a.md": "a",
    "plugin/gone.md": "g",
    "plugin/.DS_Store": "x",
    "README.md": "r",
    "tests/unit/a.test.ts": "u",
    "tests/integration/a.test.ts": "i",
    "tests/fixtures/a.ts": "f",
    ".agents/skills/s/SKILL.md": "x",
    ".claude-plugin/marketplace.json": "x",
    ".cursor-plugin/marketplace.json": "x",
    ".gitattributes": "x",
    ".github/workflows/ci.yml": "x",
    ".pre-commit-config.yaml": "x",
    "CHANGELOG.md": "x",
    LICENSE: "x",
    "pyproject.toml": "x",
    "vendored/x.json": "x",
    "AGENTS.md": "x",
    ".github/x.yml": "x",
  }
  for (const [path, text] of Object.entries(files)) await writeFile(join(root, path), text)
  await symlink("a.md", join(root, "plugin", "link.md"))
  await mkdir(join(root, "plugin/node_modules"))
  expect(Bun.spawnSync(["mkfifo", join(root, "plugin/node_modules/pipe")]).exitCode).toBe(0)
  await git(["add", "plugin/a.md", "plugin/gone.md"], root)
  await rm(join(root, "plugin/gone.md"))
  process.env.GIT_DIR = join(root, "nowhere")
  const tree = await readTree(root).finally(() => delete process.env.GIT_DIR)
  expect([...tree.keys()].sort()).toEqual([
    ".agents/skills/s/SKILL.md",
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/marketplace.json",
    ".gitattributes",
    ".github/workflows/ci.yml",
    ".pre-commit-config.yaml",
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "plugin/a.md",
    "plugin/link.md",
    "pyproject.toml",
    "tests/integration/a.test.ts",
    "tests/unit/a.test.ts",
    "vendored/x.json",
  ])
  expect(tree.get("plugin/link.md")).toBe("symlink")
})

test("stops on a listed name that is not UTF-8, which would read as no file", async () => {
  const root = await folders.make()
  await git(["init", "-q"], root)
  await writeFile(join(root, "a.md"), "a")
  const blob = (await git(["hash-object", "-w", "a.md"], root)).trim()
  const entry = Buffer.concat([
    Buffer.from(`100644 ${blob}\tplugin/x`),
    Buffer.from([0xff]),
    Buffer.from(".md\0"),
  ])
  const added = Bun.spawn(["git", "update-index", "-z", "--add", "--index-info"], {
    cwd: root,
    stdin: entry,
  })
  expect(await added.exited).toBe(0)
  await expect(readTree(root)).rejects.toThrow(
    "plugin/x\uFFFD.md: its name is not UTF-8; rename it",
  )
})

// Runs the check as a command in a checkout of the scripts, with the given plugin/package.json, or the repository's,
// and, when given, loader and mode, after arrange changes the checkout.
async function runCheck(
  packageJson?: string,
  loader?: string,
  mode?: string,
  arrange?: (root: string) => Promise<void>,
) {
  const [repository, root] = [join(import.meta.dir, "../../.."), await folders.make()]
  await git(["init", "-q"], root)
  await mkdir(join(root, "scripts"))
  await mkdir(join(root, "plugin"))
  for (const script of [
    "check.ts",
    "command.ts",
    "git.ts",
    "markdown.ts",
    "metadata.ts",
    "plugin.ts",
    "record.ts",
    "tree.ts",
    "workflows.ts",
  ])
    await copyFile(join(repository, "scripts", script), join(root, "scripts", script))
  await symlink(join(repository, "node_modules"), join(root, "node_modules"))
  if (loader === undefined)
    await copyFile(join(repository, "plugin/opencode.ts"), join(root, "plugin/opencode.ts"))
  else await writeFile(join(root, "plugin/opencode.ts"), loader)
  if (packageJson === undefined)
    await copyFile(join(repository, "plugin/package.json"), join(root, "plugin/package.json"))
  else await writeFile(join(root, "plugin/package.json"), packageJson)
  if (mode !== undefined) {
    await mkdir(join(root, "plugin/skills/nus-mode"), { recursive: true })
    await writeFile(join(root, "plugin/skills/nus-mode/SKILL.md"), mode)
  }
  await arrange?.(root)
  const run = Bun.spawnSync([process.execPath, join(root, "scripts/check.ts")], { cwd: root })
  Bun.spawnSync(["chmod", "-R", "u+rwx", root])
  return run
}

const SKILL = "plugin/skills/s/SKILL.md"

async function addSkill(root: string) {
  await mkdir(join(root, "plugin/skills/s"), { recursive: true })
  await writeFile(join(root, SKILL), "---\nname: s\ndescription: d\n---\n")
  await git(["add", SKILL], root)
}

function mkfifo(path: string) {
  expect(Bun.spawnSync(["mkfifo", path]).exitCode).toBe(0)
}

// Git tracks a file in the folder, as it does in each folder the check reads.
async function replaceTracked(root: string, folder: string, replace: (path: string) => unknown) {
  await mkdir(join(root, folder), { recursive: true })
  await writeFile(join(root, folder, "x"), "x")
  await git(["add", `${folder}/x`], root)
  await rm(join(root, folder), { recursive: true })
  await replace(join(root, folder))
}

test.each([
  [
    "a file it cannot read",
    (root: string) => chmod(join(root, SKILL), 0),
    `${SKILL}: cannot be read (Permission denied); make it readable`,
  ],
  [
    "a folder it cannot open",
    (root: string) => chmod(join(root, "plugin/skills/s"), 0),
    "plugin/skills/s: cannot be opened (Permission denied); give the folder read and execute permission",
  ],
  [
    "a file where a folder belongs",
    async (root: string) => {
      await rm(join(root, "plugin/skills/s"), { recursive: true })
      await writeFile(join(root, "plugin/skills/s"), "x")
    },
    "plugin/skills/s: is a file where a folder belongs; move the file, then add the folder",
  ],
  [
    "a fifo where a folder belongs",
    async (root: string) => {
      await rm(join(root, "plugin/skills"), { recursive: true })
      mkfifo(join(root, "plugin/skills"))
    },
    "plugin/skills: is neither a file nor a folder; remove it, then add the folder",
  ],
  [
    "a fifo in plugin's place",
    async (root: string) => {
      await rm(join(root, "plugin"), { recursive: true })
      mkfifo(join(root, "plugin"))
    },
    "plugin: is not a folder, so the check stops here; replace it with the plugin folder",
  ],
  [
    "a file in plugin's place",
    async (root: string) => {
      await rm(join(root, "plugin"), { recursive: true })
      await writeFile(join(root, "plugin"), "x")
    },
    "plugin: is not a folder, so the check stops here; replace it with the plugin folder",
  ],
  [
    "a fifo in .github/workflows's place",
    (root: string) => replaceTracked(root, ".github/workflows", mkfifo),
    ".github/workflows: is neither a file nor a folder; remove it, then add the folder",
  ],
  [
    "a file in .github/workflows's place",
    (root: string) => replaceTracked(root, ".github/workflows", (path) => writeFile(path, "x")),
    ".github/workflows: is a file where a folder belongs; move the file, then add the folder",
  ],
  [
    "a fifo in vendored's place",
    (root: string) => replaceTracked(root, "vendored", mkfifo),
    "vendored: is neither a file nor a folder; remove it, then add the folder",
  ],
  [
    "a file in vendored's place",
    (root: string) => replaceTracked(root, "vendored", (path) => writeFile(path, "x")),
    "vendored: is a file where a folder belongs; move the file, then add the folder",
  ],
  [
    "a fifo in .agents's place",
    (root: string) => replaceTracked(root, ".agents", mkfifo),
    ".agents: is neither a file nor a folder; remove it, then add the folder",
  ],
  [
    "a file in .agents's place",
    (root: string) => replaceTracked(root, ".agents", (path) => writeFile(path, "x")),
    ".agents: is a file where a folder belongs; move the file, then add the folder",
  ],
  [
    "a fifo in tests/unit's place",
    (root: string) => replaceTracked(root, "tests/unit", mkfifo),
    "tests/unit: is neither a file nor a folder; remove it, then add the folder",
  ],
  [
    "a file in tests/unit's place",
    (root: string) => replaceTracked(root, "tests/unit", (path) => writeFile(path, "x")),
    "tests/unit: is a file where a folder belongs; move the file, then add the folder",
  ],
  [
    "a fifo in tests/integration's place",
    (root: string) => replaceTracked(root, "tests/integration", mkfifo),
    "tests/integration: is neither a file nor a folder; remove it, then add the folder",
  ],
  [
    "a file in tests/integration's place",
    (root: string) => replaceTracked(root, "tests/integration", (path) => writeFile(path, "x")),
    "tests/integration: is a file where a folder belongs; move the file, then add the folder",
  ],
  [
    "a fifo in .github/workflows' place, with nothing tracked there",
    async (root: string) => {
      await mkdir(join(root, ".github/workflows", ".."), { recursive: true })
      mkfifo(join(root, ".github/workflows"))
    },
    ".github/workflows: is neither a file nor a folder; remove it, then add the folder",
  ],
  [
    "a file in .github/workflows' place, with nothing tracked there",
    async (root: string) => {
      await mkdir(join(root, ".github/workflows", ".."), { recursive: true })
      await writeFile(join(root, ".github/workflows"), "x")
    },
    ".github/workflows: is a file where a folder belongs; move the file, then add the folder",
  ],
  [
    "a fifo in tests/unit's place, with nothing tracked there",
    async (root: string) => {
      await mkdir(join(root, "tests/unit", ".."), { recursive: true })
      mkfifo(join(root, "tests/unit"))
    },
    "tests/unit: is neither a file nor a folder; remove it, then add the folder",
  ],
  [
    "a fifo in tests/integration's place, with nothing tracked there",
    async (root: string) => {
      await mkdir(join(root, "tests/integration", ".."), { recursive: true })
      mkfifo(join(root, "tests/integration"))
    },
    "tests/integration: is neither a file nor a folder; remove it, then add the folder",
  ],
  [
    "a file in tests/unit's place, with nothing tracked there",
    async (root: string) => {
      await mkdir(join(root, "tests/unit", ".."), { recursive: true })
      await writeFile(join(root, "tests/unit"), "x")
    },
    "tests/unit: is a file where a folder belongs; move the file, then add the folder",
  ],
  [
    "a file in tests/integration's place, with nothing tracked there",
    async (root: string) => {
      await mkdir(join(root, "tests/integration", ".."), { recursive: true })
      await writeFile(join(root, "tests/integration"), "x")
    },
    "tests/integration: is a file where a folder belongs; move the file, then add the folder",
  ],
  [
    "a listed name that is not UTF-8",
    async (root: string) => {
      const blob = (await git(["hash-object", "-w", SKILL], root)).trim()
      const entry = Buffer.from(`100644 ${blob}\tplugin/x\xff.md\0`, "latin1")
      const added = Bun.spawn(["git", "update-index", "-z", "--add", "--index-info"], {
        cwd: root,
        stdin: entry,
      })
      expect(await added.exited).toBe(0)
    },
    "plugin/x\uFFFD.md: its name is not UTF-8; rename it",
  ],
  [
    "a fifo Git would track",
    async (root: string) => mkfifo(join(root, "plugin/skills/pipe")),
    "plugin/skills/pipe: is neither a file nor a folder; remove it",
  ],
])(
  "stops on %s, naming its path and the fix, exiting 1 with no stack trace",
  async (_entry, arrange, fault) => {
    const checked = await runCheck(undefined, undefined, undefined, async (root) => {
      await addSkill(root)
      await arrange(root)
    })
    expect([checked.exitCode, checked.stderr.toString()]).toEqual([1, `${fault}\n`])
  },
)

test("reports a plugin/package.json that stops the OpenCode loader, naming the file", async () => {
  const checked = await runCheck("null")
  expect(checked.exitCode).toBe(1)
  expect(checked.stderr.toString()).toContain(
    "plugin/package.json: stops the OpenCode loader, so no skill is checked; fix it as the metadata rule in bun scripts/check.ts --help says\n",
  )
})

test("reads a mode as unchecked beside a plugin/package.json that stops the OpenCode loader, so its broken title goes unreported", async () => {
  const checked = await runCheck(
    "null",
    undefined,
    "---\nname: nus-mode\ndescription: m\n---\nNo title.\n",
  )
  expect(checked.stderr.toString()).toContain(
    "plugin/package.json: stops the OpenCode loader, so no skill is checked; fix it as the metadata rule in bun scripts/check.ts --help says\n",
  )
  expect(checked.stderr.toString()).not.toContain("plugin/skills/nus-mode/SKILL.md")
})

test("stops on a loader that fails to load beside the repository's plugin/package.json, with the loader's error", async () => {
  const checked = await runCheck(undefined, "export const broken = ;\n")
  expect(checked.exitCode).not.toBe(0)
  expect(checked.stderr.toString()).not.toContain("stops the OpenCode loader")
  expect(checked.stderr.toString()).toMatch(/error: Unexpected ;\n.*opencode\.ts/)
})

test("names a missing plugin/opencode.ts as its one problem beyond a checkout's, exiting 1 with no crash", async () => {
  const lines = (run: { stderr: Buffer }) => run.stderr.toString().split("\n").sort()
  const present = await runCheck()
  const missing = await runCheck(undefined, undefined, undefined, (root) =>
    rm(join(root, "plugin/opencode.ts")),
  )
  expect([missing.exitCode, lines(missing)]).toEqual([
    1,
    [...lines(present), "plugin/opencode.ts: is missing; restore it"].sort(),
  ])
})

test("passes the repository it sits in, run from another folder, exiting 0 with nothing printed", async () => {
  const repository = join(import.meta.dir, "../../..")
  const run = Bun.spawnSync([process.execPath, join(repository, "scripts/check.ts")], {
    cwd: await folders.make(),
  })
  expect([run.exitCode, run.stdout.toString(), run.stderr.toString()]).toEqual([0, "", ""])
})

test("prints its rules on --help, and its usage, exiting 1, on any other argument", () => {
  const script = join(import.meta.dir, "../../../scripts/check.ts")
  const help = Bun.spawnSync([process.execPath, script, "--help"])
  const [lead, ...rules] = help.stdout.toString().trimEnd().split("\n")
  expect([help.exitCode, lead]).toEqual([
    0,
    "bun scripts/check.ts holds the repository to these rules, skipping the files Git ignores:",
  ])
  expect(rules.map((rule) => /^- ([a-z]+): /.exec(rule)?.[1])).toEqual([
    "metadata",
    "workflows",
    "layout",
    "skills",
    "mode",
    "links",
    "readme",
    "vendored",
    "copies",
  ])
  for (const args of [["--fix"], ["--help", "--fix"]]) {
    const wrong = Bun.spawnSync([process.execPath, script, ...args])
    expect([wrong.exitCode, wrong.stderr.toString()]).toEqual([
      1,
      "usage: bun scripts/check.ts [--help]\n",
    ])
  }
})
