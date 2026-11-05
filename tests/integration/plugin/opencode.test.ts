/**
 * The plugin, loaded by Bun from a folder of its own as OpenCode loads it, takes its id from the package.json beside
 * it, and fails to set up without the mode, naming the mode's SKILL.md in the skills folder beside it.
 */
import { afterEach, describe, expect, test } from "bun:test"
import { copyFile, cp, realpath, rm, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { TemporaryFolders } from "../../fixtures/folders.ts"

const plugin = join(import.meta.dirname, "..", "..", "..", "plugin")

/**
 * OpenCode knows the plugin by its package's name, so the two never disagree, and a plugin whose skills leave out the
 * mode tells its user which file to restore.
 */
describe("plugin", () => {
  const folders = new TemporaryFolders()

  afterEach(() => folders.clear())

  test("takes its id from package.json's name", async () => {
    const folder = await folders.make()
    await copyFile(join(plugin, "opencode.ts"), join(folder, "opencode.ts"))
    await writeFile(join(folder, "package.json"), '{"name": "renamed"}')
    const spawned = Bun.spawnSync(
      [process.execPath, "-e", 'import plugin from "./opencode.ts"; console.log(plugin.id)'],
      { cwd: folder },
    )
    expect([spawned.exitCode, spawned.stdout.toString(), spawned.stderr.toString()]).toEqual([
      0,
      "renamed\n",
      "",
    ])
  })

  test("fails to set up without the mode, naming its SKILL.md in its own skills folder and the fix", async () => {
    // No positive pair runs here: setting up with the mode needs OpenCode's skill, session and storage, which the unit
    // tests in tests/unit/plugin/opencode.test.ts fake to set the plugin up with its mode; this test runs the copied file,
    // which reaches the missing mode before it reads any of them.
    // Bun resolves the plugin's path, and so its skills folder, through any symlink in the temporary folder's path.
    const folder = await realpath(await folders.make())
    await cp(plugin, folder, { recursive: true })
    await rm(join(folder, "skills", "nus-mode"), { recursive: true })
    const spawned = Bun.spawnSync(
      [
        process.execPath,
        "-e",
        'import plugin from "./opencode.ts"; await plugin.setup({}).catch((error) => console.log(String(error)))',
      ],
      { cwd: folder },
    )
    expect([spawned.exitCode, spawned.stdout.toString(), spawned.stderr.toString()]).toEqual([
      0,
      `SkillError: ${folder}/skills/nus-mode/SKILL.md is missing; restore the mode, or reinstall the nustack plugin\n`,
      "",
    ])
  })
})
