/**
 * readTree reads what Git tracks or would track under the paths the rules cover, skipping what it ignores and reading a
 * symlink as one, and stops on a path that is not UTF-8. Run as a command, the check reports a plugin/package.json the loader cannot load, fails loudly on a
 * file too long to parse safely, prints its rules on --help, and prints its usage, exiting 1, on any other argument.
 */
import { afterEach, expect, test } from "bun:test"
import { copyFile, mkdir, rm, symlink, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { readTree } from "../../../scripts/check.ts"
import { git } from "../../../scripts/git.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"
import "../../fixtures/scripts/git.ts"

const folders = new TemporaryFolders()
afterEach(() => folders.clear())

test("reads tracked and untracked files under every path the rules cover, and nothing Git ignores or the working tree lacks", async () => {
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
    "LICENSE",
    "plugin/a.md",
    "plugin/link.md",
    "pyproject.toml",
    "vendored/x.json",
  ])
  expect(tree.get("plugin/link.md")).toBe("symlink")
})

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

test("stops on a loader that fails to load beside the repository's plugin/package.json, with the loader's error", async () => {
  const checked = await runCheck(undefined, "export const broken = ;\n")
  expect(checked.exitCode).not.toBe(0)
  expect(checked.stderr.toString()).toMatch(/error: Unexpected ;\n.*opencode\.ts/)
})

test("refuses a workflow nested too deep before Bun parses it, naming the fix", async () => {
  const checked = await runCheck(undefined, undefined, undefined, async (root) => {
    await mkdir(join(root, ".github/workflows"), { recursive: true })
    await writeFile(
      join(root, ".github/workflows/ci.yml"),
      `a: ${"[".repeat(200_000)}${"]".repeat(200_000)}\n`,
    )
  })
  expect(checked.exitCode).toBe(1)
  expect(checked.stderr.toString()).toContain(
    ".github/workflows/ci.yml: holds more than 16384 characters, the most Bun's parser reads safely; shorten it\n",
  )
})

test("stops on a path Git lists that is not UTF-8, rather than leaving its file unchecked", async () => {
  const root = await folders.make()
  await git(["init", "-q"], root)
  const blob = Bun.spawnSync(["git", "hash-object", "-w", "--stdin"], {
    cwd: root,
    stdin: Buffer.from("x"),
  })
  const entry = Buffer.concat([
    Buffer.from(`100644 ${blob.stdout.toString().trim()}\tplugin/`),
    Buffer.from([0xff]),
    Buffer.from(".md\0"),
  ])
  const added = Bun.spawnSync(["git", "update-index", "-z", "--index-info"], {
    cwd: root,
    stdin: entry,
  })
  expect(added.exitCode).toBe(0)
  await expect(readTree(root)).rejects.toThrow(
    "git ls-files lists a path that is not valid UTF-8; rename it in UTF-8, then rerun",
  )
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
    "vendored",
    "copies",
    "endings",
  ])
  for (const args of [["--fix"], ["--help", "--fix"]]) {
    const wrong = Bun.spawnSync([process.execPath, script, ...args])
    expect([wrong.exitCode, wrong.stderr.toString()]).toEqual([
      1,
      "usage: bun scripts/check.ts [--help]\n",
    ])
  }
})
