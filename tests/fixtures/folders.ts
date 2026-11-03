/** Temporary folders a test makes, removed together once it ends. */
import { mkdtemp, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"

/** The temporary folders a test made, which clear removes. */
export class TemporaryFolders {
  readonly made: string[] = []

  async make(): Promise<string> {
    const folder = await mkdtemp(join(tmpdir(), "nustack-"))
    this.made.push(folder)
    return folder
  }

  async clear(): Promise<void> {
    await Promise.all(this.made.splice(0).map((folder) => rm(folder, { recursive: true })))
  }
}
