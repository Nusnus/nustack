/**
 * The plugin, loaded by Bun from a folder of its own as OpenCode loads it, takes its id from the package.json beside
 * it.
 */
import { afterEach, describe, expect, test } from "bun:test"
import { copyFile, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { TemporaryFolders } from "../../fixtures/folders.ts"

/** OpenCode knows the plugin by its package's name, so the two never disagree. */
describe("plugin", () => {
  const folders = new TemporaryFolders()

  afterEach(() => folders.clear())

  test("takes its id from package.json's name", async () => {
    const folder = await folders.make()
    await copyFile(
      join(import.meta.dirname, "..", "..", "..", "plugin", "opencode.ts"),
      join(folder, "opencode.ts"),
    )
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
})
