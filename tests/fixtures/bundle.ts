/**
 * The release zip, unpacked into a temporary folder for the smoke tests; it fails, leaving no folder, when the zip
 * folder is missing or holds no single zip, unzip cannot unpack it or it holds no nus-mode, and passes through any
 * other error reading the zip folder or nus-mode.
 */
import { mkdtemp, readdir, readFile, realpath, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { rethrowUnlessMissing } from "../../scripts/tree.ts"
import { finished } from "./process.ts"

/** A release zip folder the smoke tests cannot unpack nus-mode from. */
export class BundleError extends Error {
  override name = "BundleError"
}

/** The unpacked release zip, and the nus-mode text and folder line a host sends once the reload works. */
export class Bundle {
  static readonly ZIP_FOLDER = join(import.meta.dirname, "..", "..", "dist")
  readonly root: string
  readonly body: string
  readonly escapedBody: string
  readonly base: string

  constructor(root: string, body: string) {
    this.root = root
    this.body = body
    this.escapedBody = JSON.stringify(body).slice(1, -1)
    this.base = JSON.stringify(
      `Base directory for this skill: ${join(root, "skills", "nus-mode")}`,
    ).slice(1, -1)
    Object.freeze(this)
  }

  // `make bundle` leaves the one zip in the zip folder; the unpacked folder goes in `parent`.
  static async unpacked(zipFolder = Bundle.ZIP_FOLDER, parent = tmpdir()): Promise<Bundle> {
    const names = await readdir(zipFolder).catch((error: unknown) => {
      rethrowUnlessMissing(error)
      throw new BundleError(`${zipFolder} does not exist; run make clean and make bundle`)
    })
    const [zip, ...others] = names.filter((name) => name.endsWith(".zip"))
    if (zip === undefined || others.length > 0)
      throw new BundleError(
        `${zipFolder} holds ${others.length + (zip === undefined ? 0 : 1)} zips; run make clean and make bundle`,
      )
    // A host names the folder by its real path, which on macOS leads through /private, since /var, which holds
    // tmpdir(), is a symlink.
    const root = await realpath(await mkdtemp(join(parent, "nustack-bundle-")))
    try {
      const unzip = await finished(
        Bun.spawn(["unzip", "-q", join(zipFolder, zip), "-d", root], { stderr: "pipe" }),
      )
      if (unzip.code !== 0) {
        throw new BundleError(
          `unzip could not unpack ${zip} (${unzip.stderr.trim()}); run make clean and make bundle`,
        )
      }
      const skill = await readFile(join(root, "skills", "nus-mode", "SKILL.md"), "utf8").catch(
        (error: unknown) => {
          rethrowUnlessMissing(error)
          throw new BundleError(
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
