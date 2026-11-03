/**
 * The release zip, unpacked into a temporary folder for the smoke tests; it fails when dist holds no single zip or
 * unzip cannot unpack it.
 */
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { finished } from "./process.ts"

/** The unpacked release zip and the nus-mode text a host sends once the reload works. */
export class Bundle {
  static readonly DIST = join(import.meta.dirname, "..", "..", "dist")
  readonly root: string
  readonly body: string
  readonly needle: string

  constructor(root: string, body: string) {
    this.root = root
    this.body = body
    this.needle = JSON.stringify(body).slice(1, -1)
  }

  // `make bundle` leaves the one zip in `dist`.
  static async unpacked(dist = Bundle.DIST): Promise<Bundle> {
    const [zip, ...others] = (await readdir(dist)).filter((name) => name.endsWith(".zip"))
    if (zip === undefined || others.length > 0)
      throw new Error(
        `${dist} holds ${others.length + (zip === undefined ? 0 : 1)} zips; run make clean and make bundle`,
      )
    const root = await mkdtemp(join(tmpdir(), "nustack-bundle-"))
    const unzip = await finished(
      Bun.spawn(["unzip", "-q", join(dist, zip), "-d", root], { stderr: "pipe" }),
    )
    if (unzip.code !== 0) throw new Error(`unzip could not unpack ${zip}: ${unzip.stderr}`)
    const skill = await readFile(join(root, "skills", "nus-mode", "SKILL.md"), "utf8")
    const body = skill.split(/^---$/m).slice(2).join("---").trim()
    return new Bundle(root, body)
  }

  async remove(): Promise<void> {
    await rm(this.root, { recursive: true })
  }
}
