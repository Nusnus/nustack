/**
 * Bundle unpacks the one zip a folder holds and reads nus-mode's body from it as a request's JSON holds it, and fails
 * on a folder with no single zip, a zip unzip cannot unpack or one without nus-mode, leaving no folder behind; any
 * other error reading nus-mode passes through.
 */
import { afterEach, describe, expect, test } from "bun:test"
import { existsSync } from "node:fs"
import { mkdir, readdir, writeFile } from "node:fs/promises"
import { dirname, join } from "node:path"
import { Bundle } from "../../fixtures/bundle.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"

/** A bundle's folder line names its root as a request's JSON escapes it. */
describe("Bundle", () => {
  test("gives the base of a root holding a backslash and a quote as JSON escapes it", () => {
    expect(new Bundle('/t/a\\b"c', "").base).toBe(
      'Base directory for this skill: /t/a\\\\b\\"c/skills/nus-mode',
    )
  })
})

/**
 * The one zip a folder holds gives nus-mode's body and folder line as JSON escapes them, and leaves nothing unpacked
 * once removed. A folder holding no zip or two, a zip unzip cannot unpack or one without nus-mode fails naming the fix
 * and leaves no folder, and any other error reading nus-mode passes through.
 */
describe("Bundle.unpacked", () => {
  const folders = new TemporaryFolders()

  afterEach(() => folders.clear())

  test("reads nus-mode's body from the zip, escaped as JSON escapes it, and removes what it unpacked", async () => {
    const zipFolder = await folders.make()
    const source = await folders.make()
    await mkdir(join(source, "skills", "nus-mode"), { recursive: true })
    await writeFile(
      join(source, "skills", "nus-mode", "SKILL.md"),
      '---\nname: nus-mode\n---\n# nus-mode\n\nSay "hi".\n',
    )
    const zip = Bun.spawn(["zip", "-qr", join(zipFolder, "nustack.zip"), "skills"], { cwd: source })
    expect(await zip.exited).toBe(0)
    const parent = await folders.make()
    const bundle = await Bundle.unpacked(zipFolder, parent)
    const existed = existsSync(bundle.root)
    await bundle.remove()
    expect([
      dirname(bundle.root),
      bundle.body,
      bundle.needle,
      bundle.base,
      existed,
      existsSync(bundle.root),
    ]).toEqual([
      parent,
      '# nus-mode\n\nSay "hi".',
      '# nus-mode\\n\\nSay \\"hi\\".',
      `Base directory for this skill: ${bundle.root}/skills/nus-mode`,
      true,
      false,
    ])
  })

  test.each([
    [[], "holds 0 zips; run make clean and make bundle"],
    [["a.zip", "b.zip"], "holds 2 zips; run make clean and make bundle"],
    [["notes.zip.md"], "holds 0 zips; run make clean and make bundle"],
  ])("fails on a folder holding %j", async (names, message) => {
    const zipFolder = await folders.make()
    await Promise.all(names.map((name) => writeFile(join(zipFolder, name), "")))
    await expect(Bundle.unpacked(zipFolder)).rejects.toThrow(`${zipFolder} ${message}`)
  })

  test("fails on a zip unzip cannot unpack, and leaves no folder behind", async () => {
    const zipFolder = await folders.make()
    const parent = await folders.make()
    await writeFile(join(zipFolder, "nustack.zip"), "not a zip")
    await expect(Bundle.unpacked(zipFolder, parent)).rejects.toThrow(
      "unzip could not unpack nustack.zip:",
    )
    expect(await readdir(parent)).toEqual([])
  })

  test("fails on a zip holding no nus-mode, and leaves no folder behind", async () => {
    const zipFolder = await folders.make()
    const source = await folders.make()
    await writeFile(join(source, "README.md"), "")
    const zip = Bun.spawn(["zip", "-q", join(zipFolder, "nustack.zip"), "README.md"], {
      cwd: source,
    })
    expect(await zip.exited).toBe(0)
    const parent = await folders.make()
    await expect(Bundle.unpacked(zipFolder, parent)).rejects.toThrow(
      "nustack.zip holds no skills/nus-mode/SKILL.md; run make clean and make bundle",
    )
    expect(await readdir(parent)).toEqual([])
  })

  test("passes through another error reading nus-mode, and leaves no folder behind", async () => {
    const zipFolder = await folders.make()
    const source = await folders.make()
    await mkdir(join(source, "skills", "nus-mode", "SKILL.md"), { recursive: true })
    const zip = Bun.spawn(["zip", "-qr", join(zipFolder, "nustack.zip"), "skills"], { cwd: source })
    expect(await zip.exited).toBe(0)
    const parent = await folders.make()
    await expect(Bundle.unpacked(zipFolder, parent)).rejects.toThrow("EISDIR")
    expect(await readdir(parent)).toEqual([])
  })
})
