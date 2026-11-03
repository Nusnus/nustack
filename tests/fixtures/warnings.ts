/**
 * Fails each Bun test during which the runtime warns, since `bun test` has no setting that does it; bunfig.toml
 * preloads this file.
 */
import { afterEach, expect } from "bun:test"

/** The warnings the runtime emitted during the running test. */
class Warnings {
  readonly seen: Error[] = []

  register(): void {
    process.on("warning", (warning) => {
      this.seen.push(warning)
    })
    afterEach(() => {
      expect(this.seen.splice(0)).toEqual([])
    })
  }
}

new Warnings().register()
