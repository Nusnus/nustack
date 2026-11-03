/**
 * The release zip, unpacked into a temporary folder for the smoke tests; it fails, leaving no folder, when the zip
 * folder holds no single zip, unzip cannot unpack it or it holds no nus-mode, and passes through any other error
 * reading nus-mode.
 */
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { finished } from "./process.ts"

/** The unpacked release zip, and the nus-mode text and folder line a host sends once the reload works. */
export class Bundle {
  static readonly ZIP_FOLDER = join(import.meta.dirname, "..", "..", "dist")
  readonly root: string
  readonly body: string
  readonly needle: string
  readonly base: string

  constructor(root: string, body: string) {
    this.root = root
    this.body = body
    this.needle = JSON.stringify(body).slice(1, -1)
    this.base = JSON.stringify(
      `Base directory for this skill: ${join(root, "skills", "nus-mode")}`,
    ).slice(1, -1)
    Object.freeze(this)
  }

  // `make bundle` leaves the one zip in the zip folder; the unpacked folder goes in `parent`.
  static async unpacked(zipFolder = Bundle.ZIP_FOLDER, parent = tmpdir()): Promise<Bundle> {
    const [zip, ...others] = (await readdir(zipFolder)).filter((name) => name.endsWith(".zip"))
    if (zip === undefined || others.length > 0)
      throw new Error(
        `${zipFolder} holds ${others.length + (zip === undefined ? 0 : 1)} zips; run make clean and make bundle`,
      )
    const root = await mkdtemp(join(parent, "nustack-bundle-"))
    try {
      const unzip = await finished(
        Bun.spawn(["unzip", "-q", join(zipFolder, zip), "-d", root], { stderr: "pipe" }),
      )
      if (unzip.code !== 0) throw new Error(`unzip could not unpack ${zip}: ${unzip.stderr}`)
      const skill = await readFile(join(root, "skills", "nus-mode", "SKILL.md"), "utf8").catch(
        (error: unknown) => {
          if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error
          throw new Error(
            `${zip} holds no skills/nus-mode/SKILL.md; run make clean and make bundle`,
          )
        },
      )
      const body = skill.split(/^---$/m).slice(2).join("---").trim()
      return new Bundle(root, body)
    } catch (error) {
      await rm(root, { recursive: true })
      throw error
    }
  }

  async remove(): Promise<void> {
    await rm(this.root, { recursive: true })
  }
}
