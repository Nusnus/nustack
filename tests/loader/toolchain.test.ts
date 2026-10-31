/** package.json pins a plain Bun release, and the Bun that runs the checks is at least that version. */
import { expect, test } from "bun:test"
import { join } from "node:path"

const PIN = /^bun@((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))$/
const { packageManager } = await Bun.file(
  join(import.meta.dirname, "..", "..", "package.json"),
).json()
const pinned = pinnedVersion(packageManager)
const [major, minor, patch] = Bun.version.split(/[.+-]/).map(Number)

function meetsPin(value: unknown, version = Bun.version): boolean {
  const pin = pinnedVersion(value)
  return pin !== "" && Bun.semver.order(version, pin) >= 0
}

function pinnedVersion(value: unknown): string {
  return (typeof value === "string" && PIN.exec(value)?.[1]) || ""
}

test.each([
  ["1.4.3", false],
  ["1.4.4-canary.1", false],
  ["1.4.4", true],
  ["1.4.5", true],
  ["2.0.0", true],
])("Bun %s meets a bun@1.4.4 pin: %p", (version, expected) => {
  expect(meetsPin("bun@1.4.4", version)).toBe(expected)
})

test.each([
  ["bun@0.0.0", true],
  [`bun@${major}.${minor}.${Number(patch) + 1}`, false],
  ["bun@garbage", false],
])("the running Bun meets a %j pin: %p", (value, expected) => {
  expect(meetsPin(value)).toBe(expected)
})

test.each([
  "xbun@1.4.4",
  "BUN@1.4.4",
  "bun@1.4.4x",
  "bun@1.4.4\n",
  "bun@1.4",
  "bun@1-4-4",
  "bun@1-4.4",
  "bun@1.4-4",
  "bun@x.4.4",
  "bun@1x.4.4",
  "bun@1.x.4",
  "bun@1.4x.4",
  "bun@1.4.x",
  "bun@01.4.4",
  "bun@1.04.4",
  "bun@1.4.04",
  "bun@1.4.4-canary.1",
  "bun@1.4.4+sha512.abc",
  "npm@1.4.4",
  "bun@*",
  null,
  42,
  [["bun@1.4.4"]],
  { toString: "x" },
])("%j pins no plain Bun release", (value) => {
  expect(pinnedVersion(value)).toBe("")
})

test.each([
  ["bun@1.4.4", "1.4.4"],
  ["bun@0.0.0", "0.0.0"],
  ["bun@100.200.300", "100.200.300"],
])("%j pins %j", (value, version) => {
  expect(pinnedVersion(value)).toBe(version)
})

test("package.json's packageManager pins a plain Bun release, bun@MAJOR.MINOR.PATCH", () => {
  expect(packageManager).toMatch(PIN)
})

test.if(pinned !== "")(
  "Bun is at least the version package.json pins; install it from https://bun.sh/docs/installation",
  () => {
    expect({
      found: Bun.version,
      pinned,
      meetsPin: meetsPin(packageManager),
    }).toMatchObject({
      meetsPin: true,
    })
  },
)
