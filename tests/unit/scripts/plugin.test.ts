/** The plugin's version form and the README steps its release page copies. */
import { describe, expect, test } from "bun:test"
import { PAGE_STEPS, VERSION } from "../../../scripts/plugin.ts"

describe("VERSION", () => {
  test.each(["0.0.0", "0.0.3", "0.1.0", "1.20.300", "10.0.0"])("takes %s", (version) => {
    expect(VERSION.test(version)).toBe(true)
  })

  test.each(["0.2", "01.0.0", "0.0.3-rc.1", "0.0.3+build", "v0.0.3", " 0.0.3"])(
    "refuses %s",
    (version) => {
      expect(VERSION.test(version)).toBe(false)
    },
  )
})

describe("PAGE_STEPS", () => {
  test("names the install and use steps, in README's order", () => {
    expect(PAGE_STEPS).toEqual(["### 1️⃣ Install", "### 2️⃣ Use"])
  })
})
