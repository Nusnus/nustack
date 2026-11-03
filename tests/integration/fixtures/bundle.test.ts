/**
 * Bundle unpacks the one zip a folder holds and reads nus-mode's body from it as a request's JSON holds it, and fails
 * on a folder with no single zip or a zip unzip cannot unpack.
 */
import { afterEach, describe, expect, test } from "bun:test"
import { existsSync } from "node:fs"
import { mkdir, writeFile } from "node:fs/promises"
import { join } from "node:path"
import { Bundle } from "../../fixtures/bundle.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"

/**
 * The one zip a folder holds gives nus-mode's body as JSON escapes it, and leaves nothing unpacked once removed. A
 * folder holding no zip or two, or a zip unzip cannot unpack, fails naming the fix.
 */
describe("Bundle.unpacked", () => {
  const folders = new TemporaryFolders()

  afterEach(() => folders.clear())

  test("reads nus-mode's body from the zip, escaped as JSON escapes it, and removes what it unpacked", async () => {
    const dist = await folders.make()
    const source = await folders.make()
    await mkdir(join(source, "skills", "nus-mode"), { recursive: true })
    await writeFile(
      join(source, "skills", "nus-mode", "SKILL.md"),
      '---\nname: nus-mode\n---\n# nus-mode\n\nSay "hi".\n',
    )
    const zip = Bun.spawn(["zip", "-qr", join(dist, "nustack.zip"), "skills"], { cwd: source })
    expect(await zip.exited).toBe(0)
    const bundle = await Bundle.unpacked(dist)
    const unpacked = existsSync(bundle.root)
    await bundle.remove()
    expect([bundle.body, bundle.needle, unpacked, existsSync(bundle.root)]).toEqual([
      '# nus-mode\n\nSay "hi".',
      '# nus-mode\\n\\nSay \\"hi\\".',
      true,
      false,
    ])
  })

  test.each([
    [[], "holds 0 zips; run make clean and make bundle"],
    [["a.zip", "b.zip"], "holds 2 zips; run make clean and make bundle"],
    [["notes.zip.md"], "holds 0 zips; run make clean and make bundle"],
  ])("fails on a folder holding %j", async (names, message) => {
    const dist = await folders.make()
    await Promise.all(names.map((name) => writeFile(join(dist, name), "")))
    await expect(Bundle.unpacked(dist)).rejects.toThrow(`${dist} ${message}`)
  })

  test("fails on a zip unzip cannot unpack", async () => {
    const dist = await folders.make()
    await writeFile(join(dist, "nustack.zip"), "not a zip")
    await expect(Bundle.unpacked(dist)).rejects.toThrow("unzip could not unpack nustack.zip:")
  })
})
