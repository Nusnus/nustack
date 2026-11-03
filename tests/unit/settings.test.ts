/**
 * Bun's settings hold the loader's suite to the Python suite's rules, and a Bun older than package.json pins stops a
 * contributor at once.
 */
import { describe, expect, test } from "bun:test"
import { join } from "node:path"

/** A packageManager value, read as the plain Bun release it pins, if any. */
class Pin {
  static readonly PLAIN = /^bun@((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))$/
  readonly value: unknown

  constructor(value: unknown) {
    this.value = value
    Object.freeze(this)
  }

  static of(manifest: unknown): Pin {
    return new Pin(
      typeof manifest === "object" && manifest !== null && "packageManager" in manifest
        ? manifest.packageManager
        : undefined,
    )
  }

  get version(): string | undefined {
    return typeof this.value === "string" ? Pin.PLAIN.exec(this.value)?.[1] : undefined
  }

  metBy(version: string): boolean {
    return this.version !== undefined && Bun.semver.order(version, this.version) >= 0
  }
}

/** A file at the repository's root, which the settings tests read as the value its loader gives. */
class RootFile {
  static readonly ROOT = join(import.meta.dirname, "..", "..")
  readonly path: string

  constructor(name: string) {
    this.path = join(RootFile.ROOT, name)
    Object.freeze(this)
  }

  async read(): Promise<unknown> {
    const file = Bun.file(this.path)
    return this.path.endsWith(".toml") ? Bun.TOML.parse(await file.text()) : file.json()
  }
}

/** A pin counts only as a plain Bun release, met by that release or a newer one. */
describe("Pin", () => {
  test.each([
    ["1.4.3", false],
    ["1.4.4-canary.1", false],
    ["1.4.4", true],
    ["1.4.5", true],
    ["2.0.0", true],
  ])("lets Bun %s meet a bun@1.4.4 pin: %p", (version, met) => {
    expect(new Pin("bun@1.4.4").metBy(version)).toBe(met)
  })

  test.each([
    ["bun@1.4.4", "1.4.4"],
    ["bun@0.0.0", "0.0.0"],
    ["bun@100.200.300", "100.200.300"],
  ])("reads %j as a pin of %j", (value, version) => {
    expect(new Pin(value).version).toBe(version)
  })

  test.each([
    "xbun@1.4.4",
    "BUN@1.4.4",
    "bun@1.4.4x",
    "bun@1.4.4\n",
    "bun@1.4",
    "bun@1-4-4",
    "bun@x.4.4",
    "bun@01.4.4",
    "bun@1.04.4",
    "bun@1.4.04",
    "bun@1.4.4-canary.1",
    "bun@1.4.4+sha512.abc",
    "npm@1.4.4",
    null,
    42,
    [["bun@1.4.4"]],
  ])("reads %j as no plain Bun release, which no Bun meets", (value) => {
    expect([new Pin(value).version, new Pin(value).metBy("99.0.0")]).toEqual([undefined, false])
  })
})

/** A pin reads from package.json's packageManager, whatever shape the manifest has. */
describe("Pin.of", () => {
  test.each([
    [{ packageManager: "bun@1.4.4" }, "bun@1.4.4"],
    [{}, undefined],
    [null, undefined],
    ["bun@1.4.4", undefined],
  ])("reads the packageManager of %j as %j", (manifest, value) => {
    expect(Pin.of(manifest).value).toBe(value)
  })
})

/** A contributor learns at once when their Bun is too old for the suite. */
describe("package.json", () => {
  test("pins a Bun that the running Bun meets; install it from https://bun.sh/docs/installation", async () => {
    const pin = Pin.of(await new RootFile("package.json").read())
    expect({
      found: Bun.version,
      pinned: pin.value,
      met: pin.metBy(Bun.version),
    }).toMatchObject({ met: true })
  })
})

/** Bun runs the loader's suite as the Python suite runs: shuffled, strict and fully covered. */
describe("bunfig.toml", () => {
  test("runs every tier but smoke in random order, fails on warnings and on any uncovered line", async () => {
    expect(await new RootFile("bunfig.toml").read()).toEqual({
      test: {
        root: "tests",
        preload: ["./tests/fixtures/warnings.ts"],
        pathIgnorePatterns: ["tests/smoke/**"],
        coverage: true,
        coverageThreshold: 1.0,
        coverageSkipTestFiles: false,
        coveragePathIgnorePatterns: ["tests/fixtures/warnings.ts"],
        randomize: true,
      },
    })
  })

  test("runs the smoke tier alone, in random order, failing on warnings", async () => {
    expect(await new RootFile("tests/fixtures/smoke/bunfig.toml").read()).toEqual({
      test: {
        root: "tests/smoke",
        preload: ["./tests/fixtures/warnings.ts"],
        randomize: true,
      },
    })
  })
})
