/** Each test's temporary folders are new and empty, and gone once it clears them. */
import { describe, expect, test } from "bun:test"
import { existsSync } from "node:fs"
import { readdir } from "node:fs/promises"
import { TemporaryFolders } from "../../fixtures/folders.ts"

/** A folder made for one test stays apart from every other and leaves nothing behind. */
describe("TemporaryFolders", () => {
  test("makes distinct empty folders and removes each on clear", async () => {
    const folders = new TemporaryFolders()
    const made = [await folders.make(), await folders.make()]
    const contents = await Promise.all(made.map((folder) => readdir(folder)))
    await folders.clear()
    expect([
      made[0] === made[1],
      contents,
      made.map((folder) => existsSync(folder)),
      folders.made,
    ]).toEqual([false, [[], []], [false, false], []])
  })
})
