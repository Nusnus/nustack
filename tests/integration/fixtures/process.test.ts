/** A finished child process gives back its exit code and each stream it printed. */
import { describe, expect, test } from "bun:test"
import { finished } from "../../fixtures/process.ts"

/** A child that exits with a failing code still gives back that code and each stream's whole text. */
describe("finished", () => {
  test("gives the exit code and each stream's whole text", async () => {
    const child = Bun.spawn(["sh", "-c", "printf out; printf err >&2; exit 3"], { stderr: "pipe" })
    expect(await finished(child)).toEqual({ code: 3, stdout: "out", stderr: "err" })
  })
})
