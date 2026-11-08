/**
 * Each target make help lists installs bun.lock before it runs a Bun script, as make itself expands the target: through
 * its prerequisites and each recursive make. The test reads each command by its own pattern, apart from the check's
 * workflows rule, so a script form that rule misses still counts here. make check stops at once without zip or unzip,
 * and make smoke without unzip, each naming the fix. bunfig.toml turns off Bun's auto-install, so a script that runs
 * before bun install --frozen-lockfile fails on the package it lacks instead of fetching a version bun.lock does not
 * lock.
 */
import { afterEach, expect, test } from "bun:test"
import { copyFile, symlink, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { TemporaryFolders } from "../fixtures/folders.ts"
import { type Finished, finished } from "../fixtures/process.ts"

const root = join(import.meta.dir, "../..")
const folders = new TemporaryFolders()
// bun runs the file its command line names, with run or flags before it or not.
const RUNS_FILE = /(?:^|\s)bun\s+(?:-\S+\s+)*(?:run\s+)?\S+\.[cm]?[jt]sx?(?:\s|$)/
const INSTALL = "bun install --frozen-lockfile"
const runsFile = (command: string) => RUNS_FILE.test(command)

afterEach(() => folders.clear())

// A make that runs these tests passes its flags down; the commands each target would run come from a make of its own.
async function make(...args: string[]): Promise<string> {
  const { MAKEFLAGS, MAKELEVEL, MFLAGS, ...env } = process.env
  const run = await finished(
    Bun.spawn(["make", "--no-print-directory", ...args], {
      cwd: root,
      env,
      stdout: "pipe",
      stderr: "pipe",
    }),
  )
  expect(run.code).toBe(0)
  return run.stdout
}

test("installs bun.lock before each target that runs a script", async () => {
  const targets = (await make("help"))
    .split("\n")
    .flatMap((line) => line.trim().split(/\s+/, 1).filter(Boolean))
  const runs = await Promise.all(
    targets.map(async (target) => ({
      target,
      commands: (await make("--dry-run", "--always-make", target))
        .split(/&&|\|\||[;|\n]/)
        .map((command) => command.trim()),
    })),
  )
  const scripted = runs.filter(({ commands }) => commands.some(runsFile))
  expect(scripted.length).toBeGreaterThan(0)
  expect(
    scripted
      .filter(({ commands }) => {
        const install = commands.indexOf(INSTALL)
        return install < 0 || install > commands.findIndex(runsFile)
      })
      .map(({ target }) => target),
  ).toEqual([])
})

// make with a PATH that holds only the tools named, each a stand-in that does nothing and succeeds.
async function makeWithOnly(tools: string[], target: string): Promise<Finished> {
  const path = await folders.make()
  const standIn = Bun.which("true")
  const maker = Bun.which("make")
  if (standIn === null || maker === null)
    throw new Error("true or make is not on the PATH; install coreutils and make, then rerun")
  await Promise.all(tools.map((tool) => symlink(standIn, join(path, tool))))
  const { MAKEFLAGS, MAKELEVEL, MFLAGS, ...env } = process.env
  return finished(
    Bun.spawn([maker, "--no-print-directory", target], {
      cwd: root,
      env: { ...env, PATH: path },
      stdout: "pipe",
      stderr: "pipe",
    }),
  )
}

test.each([
  [
    "check",
    ["bun", "uv", "unzip"],
    "zip is missing; install it with your system package manager, such as apt-get install zip, then rerun the command that stopped\n",
  ],
  [
    "check",
    ["bun", "uv", "zip"],
    "unzip is missing; install it with your system package manager, such as apt-get install unzip, then rerun the command that stopped\n",
  ],
  [
    "smoke",
    [],
    "unzip is missing; install it with your system package manager, such as apt-get install unzip, then rerun the command that stopped\n",
  ],
  [
    "smoke",
    ["unzip"],
    "Bun is missing; install it from https://bun.sh/docs/installation, then rerun the command that stopped\n",
  ],
])(
  "stops make %s at once with only %j on the PATH, naming the missing tool's fix",
  async (target, tools, fix) => {
    const run = await makeWithOnly(tools, target)
    expect(run.code).toBe(2)
    expect(run.stderr).toStartWith(fix)
  },
)

test("turns off auto-install", async () => {
  expect(Bun.TOML.parse(await Bun.file(join(root, "bunfig.toml")).text())).toMatchObject({
    install: { auto: "disable" },
  })
})

test("fails a script whose package is not installed", async () => {
  const folder = await folders.make()
  await copyFile(join(root, "bunfig.toml"), join(folder, "bunfig.toml"))
  await writeFile(join(folder, "script.ts"), 'import "is-odd"\n')
  const run = await finished(
    Bun.spawn([process.execPath, "script.ts"], { cwd: folder, stdout: "pipe", stderr: "pipe" }),
  )
  expect(run.code).not.toBe(0)
  expect(run.stderr).toContain("Cannot find package 'is-odd'")
})
