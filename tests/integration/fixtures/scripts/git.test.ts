/** The script tests' Git reads each repository's own config and the gitconfig beside the fixture, whatever HOME holds, and commits as a fixed author. */
import { afterEach, expect, test } from "bun:test"
import { writeFile } from "node:fs/promises"
import { join } from "node:path"
import { git } from "../../../../scripts/git.ts"
import { TemporaryFolders } from "../../../fixtures/folders.ts"
import { commit } from "../../../fixtures/scripts/git.ts"

const folders = new TemporaryFolders()
afterEach(() => folders.clear())

test("reads config files only from the repository and the fixture's gitconfig, not the machine's", async () => {
  const root = await folders.make()
  const home = await folders.make()
  await writeFile(join(home, ".gitconfig"), "[user]\n\tname = Machine\n")
  const saved = process.env.HOME
  process.env.HOME = home
  try {
    await git(["init", "-q", root], root)
    const listed = await git(["config", "--list", "--show-origin", "--name-only"], root)
    const origins = new Set(
      listed
        .split("\n")
        .map((line) => line.split("\t")[0])
        .filter((origin) => origin?.startsWith("file:")),
    )
    const fixture = join(import.meta.dir, "../../../fixtures/scripts/gitconfig")
    expect(origins).toEqual(new Set([`file:${fixture}`, "file:.git/config"]))
  } finally {
    process.env.HOME = saved
  }
})

test("commits as its fixed author", async () => {
  const root = await folders.make()
  await git(["init", "-q", root], root)
  await writeFile(join(root, "f"), "x\n")
  await commit(root)
  expect(await git(["log", "-1", "--format=%an <%ae>"], root)).toBe("T <t@t>\n")
})
