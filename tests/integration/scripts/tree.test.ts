/**
 * readEntry stops on a folder it cannot open and on a fifo, naming its path and the fix; the rows make the fifo with
 * mkfifo and write to it with sh.
 */
import { afterEach, expect, test } from "bun:test"
import { chmod, mkdir, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { readEntry, UnreadableEntry } from "../../../scripts/tree.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"

const folders = new TemporaryFolders()
afterEach(() => folders.clear())

test.each([
  ["d/f", "d: cannot be opened (Permission denied); give the folder read and execute permission"],
  ["p/f", "p: is neither a file nor a folder; remove it, then add the folder"],
  ["p", "p: is neither a file nor a folder; remove it"],
])("stops on reading %p with %p", async (path, fault) => {
  const root = await folders.make()
  await mkdir(join(root, "d"))
  await writeFile(join(root, "d/f"), "x")
  expect(Bun.spawnSync(["mkfifo", join(root, "p")]).exitCode).toBe(0)
  // A writer ends any read of the fifo at once, so a check that opens it fails here instead of hanging.
  const writer = Bun.spawn(["sh", "-c", ": > p"], { cwd: root })
  await chmod(join(root, "d"), 0)
  const read = readEntry(root, path).finally(() => chmod(join(root, "d"), 0o755))
  await expect(read.finally(() => writer.kill())).rejects.toThrow(new UnreadableEntry(fault))
})
