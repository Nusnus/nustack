/**
 * The preload fails each Bun test during which the runtime warns and passes one that stays quiet, and a failing run
 * prints the seed that replays it. Bun's output holds timings and a random seed, so each test checks what it holds.
 */
import { afterEach, describe, expect, test } from "bun:test"
import { writeFile } from "node:fs/promises"
import { join } from "node:path"
import { TemporaryFolders } from "../../fixtures/folders.ts"

/** No warning goes unnoticed, and a failing order can be replayed. */
describe("warnings.ts", () => {
  const folders = new TemporaryFolders()

  afterEach(() => folders.clear())

  const run = async (source: string) => {
    const folder = await folders.make()
    await writeFile(join(folder, "a.test.ts"), `import { test } from "bun:test"\n${source}\n`)
    const spawned = Bun.spawnSync(
      [
        process.execPath,
        "test",
        "--randomize",
        "--preload",
        join(import.meta.dirname, "..", "..", "fixtures", "warnings.ts"),
        "./a.test.ts",
      ],
      // Bun's agent mode, which CLAUDECODE=1 turns on, prints only failing tests, so the run gets only
      // what Bun needs: https://bun.com/docs/cli/test
      { cwd: folder, env: { PATH: process.env.PATH, HOME: process.env.HOME, NO_COLOR: "1" } },
    )
    return {
      code: spawned.exitCode,
      output: spawned.stdout.toString() + spawned.stderr.toString(),
    }
  }

  test("fails a test during which the runtime warns, and the run prints its seed", async () => {
    const { code, output } = await run('test("warns", () => { process.emitWarning("canary") })')
    expect([code, output.includes("(fail) warns"), /--seed=\d+/.test(output)]).toEqual([
      1,
      true,
      true,
    ])
  })

  test("passes a test during which the runtime stays quiet", async () => {
    const { code, output } = await run('test("quiet", () => {})')
    expect([code, output.includes("(pass) quiet")]).toEqual([0, true])
  })
})
