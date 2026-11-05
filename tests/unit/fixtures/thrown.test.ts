/** A call's throw or rejection comes back as the value it threw, and a call that returns gives its value back. */
import { describe, expect, test } from "bun:test"
import { thrown } from "../../fixtures/thrown.ts"

/** Whatever a call throws, at once or as a rejection, is the value a test compares. */
describe("thrown", () => {
  test("gives what a call threw, rejected with or returned", async () => {
    expect([
      await thrown(() => {
        throw new TypeError("at once")
      }),
      await thrown(() => Promise.reject(new RangeError("later"))),
      await thrown(() => "returned"),
    ]).toEqual([new TypeError("at once"), new RangeError("later"), "returned"])
  })
})
