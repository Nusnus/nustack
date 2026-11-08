/**
 * Each target make help lists installs bun.lock before it runs a script, as make itself expands the target: through
 * its prerequisites and each recursive make. Each command make would run counts as a script run or an install as the
 * check's workflows rule counts one, through the command forms scripts/workflows.ts exports.
 */
import { expect, test } from "bun:test"
import { join } from "node:path"
import { commandsOf, INSTALL, RUNS_SCRIPT } from "../../scripts/workflows.ts"
import { finished } from "../fixtures/process.ts"

const root = join(import.meta.dir, "../..")
const runsScript = (command: string) => RUNS_SCRIPT.test(command)

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
      commands: (await make("--dry-run", "--always-make", target)).split("\n").flatMap(commandsOf),
    })),
  )
  const scripted = runs.filter(({ commands }) => commands.some(runsScript))
  expect(scripted.length).toBeGreaterThan(0)
  expect(
    scripted
      .filter(({ commands }) => {
        const install = commands.indexOf(INSTALL)
        return install < 0 || install > commands.findIndex(runsScript)
      })
      .map(({ target }) => target),
  ).toEqual([])
})
