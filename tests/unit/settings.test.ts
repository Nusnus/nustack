/**
 * Bun's settings hold the suite to shuffled, strict runs, make smoke stops a stalled host, the sync workflow opens or
 * resets a copy's pull request only once no open one proposes the copy, each setting a promise of AGENTS.md or make
 * check rests on holds its value, and a Bun older than package.json pins stops a contributor at once, in a test the
 * blueprint's message for a failed Bun check points to.
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

  get version(): string | undefined {
    return typeof this.value === "string" ? Pin.PLAIN.exec(this.value)?.[1] : undefined
  }

  static of(manifest: unknown): Pin {
    return new Pin(
      typeof manifest === "object" && manifest !== null && "packageManager" in manifest
        ? manifest.packageManager
        : undefined,
    )
  }

  metBy(version: string): boolean {
    return this.version !== undefined && Bun.semver.order(version, this.version) >= 0
  }
}

/** A file at the repository's root, which the settings tests read as its text or as the value its loader gives. */
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

/** Bun runs the suite shuffled and strict. */
describe("bunfig.toml", () => {
  test("runs every tier but smoke in random order, failing on warnings, with auto-install off", async () => {
    expect(await new RootFile("bunfig.toml").read()).toEqual({
      install: { auto: "disable" },
      test: {
        root: "tests",
        preload: ["./tests/fixtures/warnings.ts"],
        pathIgnorePatterns: ["tests/smoke/**"],
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

/** make smoke stops a host that stalls, so a hung host fails the run instead of holding it. */
describe("Makefile", () => {
  test("stops a stalled host in make smoke after two minutes", async () => {
    const makefile = await Bun.file(join(import.meta.dirname, "../../Makefile")).text()
    // The smoke target's recipe: the tab-indented lines right after its rule line.
    const recipe = /^smoke:.*\n((?:\t.*\n)*)/m.exec(makefile)?.[1]?.split("\n") ?? []
    expect(recipe).toContain(
      "\tbun --config=tests/fixtures/smoke/bunfig.toml test --timeout=120000",
    )
  })
})

/** The sync workflow commits as github-actions[bot] and leaves an open pull request that already proposes the copy, with its reviewer's commits, as it is. */
describe("sync.yml", () => {
  test("runs create-pull-request as github-actions[bot] only when the proposed step finds no open pull request proposing the copy", async () => {
    const text = await Bun.file(
      join(import.meta.dirname, "../../.github/workflows/sync.yml"),
    ).text()
    type Step = { id?: string; if?: string; uses?: string; with?: { author?: string } }
    const steps = (Bun.YAML.parse(text) as { jobs: { sync: { steps: Step[] } } }).jobs.sync.steps
    const proposing = steps.findIndex((step) => step.id === "proposed")
    const creating = steps.findIndex((step) =>
      step.uses?.startsWith("peter-evans/create-pull-request@"),
    )
    expect(proposing).toBeGreaterThan(-1)
    expect(creating).toBeGreaterThan(proposing)
    expect(steps[creating]?.if).toBe("steps.proposed.outputs.proposed != 'true'")
    expect(steps[creating]?.with?.author).toBe(
      "github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>",
    )
  })
})

type Hook = { id: string; entry?: string; args?: string[]; fail_fast?: boolean }
type Step = { if?: string; run?: string }

async function yamlOf(name: string): Promise<unknown> {
  return Bun.YAML.parse(await Bun.file(join(RootFile.ROOT, name)).text())
}

async function hooks(): Promise<Hook[]> {
  const config = (await yamlOf(".pre-commit-config.yaml")) as { repos: { hooks: Hook[] }[] }
  return config.repos.flatMap((repo) => repo.hooks)
}

async function hook(id: string): Promise<Hook | undefined> {
  return (await hooks()).find((each) => each.id === id)
}

// The commands that install a tool, each as far as its fallback's ||, with the limit bounded gives it.
async function installs(): Promise<string[]> {
  const blueprint = (await yamlOf(".devin/blueprint.yaml")) as { maintenance: Step[] }
  const install =
    /^(?:bounded \d+ )?(?:(?:sh|bash) "\$installer"|make install|uv run --locked pre-commit install-hooks)(?=\s|$)/
  return blueprint.maintenance
    .flatMap((step) => (step.run ?? "").split("\n"))
    .map((line) => line.trim().split(" || ")[0] ?? "")
    .filter((command) => install.test(command))
}

/** Each setting a promise of AGENTS.md or make check rests on holds the value that keeps it. */
describe("the settings the promises rest on", () => {
  test.each([
    [
      "a missing or stale bun.lock stops the run before the Bun hooks",
      async () => {
        const ids = (await hooks()).map((each) => each.id)
        const first = ["biome", "tsc", "bun-test", "check"].map((id) => ids.indexOf(id))
        return {
          failFast: (await hook("bun-lock"))?.fail_fast,
          before: Math.min(...first) > ids.indexOf("bun-lock"),
        }
      },
      { failFast: true, before: true },
    ],
    [
      "each commit runs the check",
      async () => (await hook("check"))?.entry,
      "bun scripts/check.ts",
    ],
    [
      "make check fixes what markdownlint can fix",
      async () => (await hook("markdownlint-cli2"))?.args,
      ["--fix"],
    ],
    [
      "CI checks every commit on main with no exemptions",
      async () => {
        const ci = (await yamlOf(".github/workflows/ci.yml")) as {
          jobs: Record<string, { steps?: Step[] }>
        }
        return Object.values(ci.jobs)
          .flatMap((job) => job.steps ?? [])
          .find(
            (step) => step.if === "github.event_name == 'push'" && step.run?.includes("cz check"),
          )?.run
      },
      'uv run --locked cz check --allowed-prefixes --rev-range "$GITHUB_SHA"',
    ],
    [
      "each CI job gets only the token rights its own permissions grant",
      async () =>
        ((await yamlOf(".github/workflows/ci.yml")) as { permissions?: unknown }).permissions,
      {},
    ],
    [
      "each install in the blueprint stops after its limit",
      installs,
      [
        'bounded 600 sh "$installer"',
        'bounded 600 bash "$installer"',
        "bounded 1200 make install",
        "bounded 1200 uv run --locked pre-commit install-hooks",
      ],
    ],
  ] as const)("%s", async (_promise, read, kept) => {
    expect(await read()).toEqual(kept)
  })
})
