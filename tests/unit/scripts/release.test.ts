/** The changelog's title, the release page, and the release published through a gh that replays gh's replies. */
import { afterEach, describe, expect, test } from "bun:test"
import { mkdir, rm, writeFile } from "node:fs/promises"
import { join } from "node:path"
import type { GhResult } from "../../../scripts/gh.ts"
import { notes, publish, title } from "../../../scripts/release.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"

const plugin = { name: "nustack", version: "0.0.3", description: "d", repository: "https://h/o/n" }
const changelog = [
  "# Changelog\n",
  "[Unreleased]: https://h/o/n/compare/v0.0.2...HEAD",
  "[0.0.2]: https://h/o/n/releases/tag/v0.0.2",
  "[0.0.1]: https://h/o/n/releases/tag/v0.0.1\n",
  "## [Unreleased]\n\n### Added\n\n- New.\n",
  "## [0.0.2] - 2026-11-04\n\nThe lead.\n\n### Fixed\n\n- A fix.\n",
  "## [0.0.1] - 2026-11-03\n\n### Added\n\n- First.\n",
].join("\n")
const readme = "# n\n\n### 1️⃣ Install\n\nInstall it.\n\n### 2️⃣ Use\n\nUse it.\n\n### 3️⃣ More\n\nNo.\n"

describe("title", () => {
  const titled = [
    "# Changelog\n",
    "[Unreleased]: https://h/o/n/compare/v0.0.3...HEAD",
    "[0.0.3]: https://h/o/n/releases/tag/v0.0.3",
    "[0.0.2]: https://h/o/n/releases/tag/v0.0.2",
    "[0.0.1]: https://h/o/n/releases/tag/v0.0.1\n",
    "## [Unreleased]\n\n## [0.0.3] - 2026-11-07\n\n### Added\n\n- New.\n",
    "## [0.0.2] - 2026-11-04\n\nThe lead.\n\n### Fixed\n\n- A fix.\n",
    "## [0.0.1] - 2026-11-03\n\n### Added\n\n- First.\n",
  ].join("\n")

  test("titles [Unreleased] below an empty one and links both", () => {
    expect(title(changelog, "2026-11-07", plugin)).toBe(titled)
  })

  test("relinks an [Unreleased] link defined in another case", () => {
    const lower = changelog.replace("[Unreleased]: ", "[unreleased]: ")
    expect(title(lower, "2026-11-07", plugin)).toBe(titled)
  })

  test("writes what it inserts with a CRLF changelog's own line ending", () => {
    expect(title(changelog.replaceAll("\n", "\r\n"), "2026-11-07", plugin)).toBe(
      titled.replaceAll("\n", "\r\n"),
    )
  })

  test.each([
    ["2026-11-07", "CHANGELOG.md has no ## [Unreleased]; add one", "# Changelog\n"],
    [
      "2026-11-07",
      "CHANGELOG.md's [Unreleased] lists no change; merge the changes to release first",
      changelog.replace("### Added\n\n- New.\n", "### Added\n"),
    ],
    [
      "2026-11-07",
      "CHANGELOG.md has no [Unreleased] link; add one",
      changelog.replace(/^\[Unreleased\]: .*$/m, ""),
    ],
    [
      "2026-11-07",
      "CHANGELOG.md already holds [0.0.3]; bump to the next version",
      changelog.replace("## [0.0.2]", "## [0.0.3]"),
    ],
  ])("refuses to title on %s: %s", (date, message, text) => {
    expect(() => title(text, date, plugin)).toThrow(message)
  })
})

describe("notes", () => {
  const page = [
    "> **[nustack](https://h/o/n)** · d",
    "The lead.",
    "## 🆕 What's new",
    "### Fixed\n\n- A fix.",
    "## 🚀 Quick start",
    "### 1️⃣ Install\n\nInstall it.",
    "### 2️⃣ Use\n\nUse it.",
    "**Full changelog:** [`v0.0.1...v0.0.2`](https://h/o/n/compare/v0.0.1...v0.0.2)",
  ].join("\n\n")

  test("gives the plugin, the lead, the changes, README's first two steps and the comparison", () => {
    expect(notes(changelog, readme, "0.0.2", plugin)).toBe(page)
  })

  test("gives a CRLF changelog's and README's page with no carriage return", () => {
    const crlf = (text: string) => text.replaceAll("\n", "\r\n")
    expect(notes(crlf(changelog), crlf(readme), "0.0.2", plugin)).toBe(page)
  })

  test("gives a lone-CR changelog's and README's page with no carriage return", () => {
    const cr = (text: string) => text.replaceAll("\n", "\r")
    expect(notes(cr(changelog), cr(readme), "0.0.2", plugin)).toBe(page)
  })

  // Copies of README.md and CHANGELOG.md as they stood when Markdown came to be read by one parser, beside the page the
  // line scan it replaced wrote from them, so a change of parser changes no released page's text.
  test.each(["0.0.2", "0.0.1"])(
    "writes %s's page from the copied README and CHANGELOG byte for byte as before",
    async (version) => {
      const fixture = (name: string) =>
        Bun.file(join(import.meta.dir, "../../fixtures/release", name)).text()
      const page = notes(
        await fixture("CHANGELOG.txt"),
        await fixture("README.txt"),
        version,
        plugin,
      )
      expect(`${page}\n`).toBe(await fixture(`notes-${version}.txt`))
    },
  )

  test("refuses a version whose next heading links no version", () => {
    expect(() =>
      notes("## [0.0.2] - d\n\n- a\n\n## [0.0.1] - d\n", readme, "0.0.2", plugin),
    ).toThrow("CHANGELOG.md: the heading after [0.0.2] links no version; define its label")
  })

  test("cuts a version's lead at its first heading, not at a ### line in fenced code", () => {
    const text = "## [0.0.1] - d\n\nLead.\n\n```\n### x\n```\n\n### Added\n\n- a\n"
    expect(notes(text, readme, "0.0.1", plugin)).toContain(
      "Lead.\n\n```\n### x\n```\n\n## 🆕 What's new\n\n### Added",
    )
  })

  test("leaves out the comparison for the first release", () => {
    expect(notes(changelog, readme, "0.0.1", plugin)).not.toContain("Full changelog")
  })

  test.each([
    ["0.0.9", "CHANGELOG.md has no ## [0.0.9] heading; add it", readme],
    ["0.0.2", "README.md has no ### 2️⃣ Use heading; add it", "# n\n\n### 1️⃣ Install\n\nx\n"],
    ["0.2", "pass the version as <major>.<minor>.<patch>", readme],
  ])("refuses the version %s: %s", (version, message, text) => {
    expect(() => notes(changelog, text, version, plugin)).toThrow(message)
  })
})

describe("publish", () => {
  const folders = new TemporaryFolders()
  afterEach(() => folders.clear())
  const recorded = async (path: string): Promise<GhResult> => {
    const { code, stdout, stderr } = await Bun.file(
      join(import.meta.dir, "../../fixtures/github", path),
    ).json()
    return { code, stdout, stderr }
  }
  // gh 2.78.0's replies, off a terminal and unredacted, to create, upload and edit run with GH_REPO set to
  // Nusnus-Private/nustack on a draft release for the tag record-fixture-1794075633, which no tag held, deleted once
  // recorded. Each ran with publish's flags but one: create's lacks --verify-tag, which only refuses a tag the
  // repository lacks before anything is created and changes no output (pkg/cmd/release/create/create.go:268-274), and
  // edit's sets --draft=true in place of --draft=false, so nothing was published, which leaves its URL in a draft's
  // untagged- form where a published release's takes the tag's. publish reads only each reply's exit code.
  const succeeded = new Map([
    ["create", recorded("release-create/created.json")],
    ["upload", recorded("upload/uploaded.json")],
    ["edit", recorded("release-edit/draft.json")],
  ])
  // The commit tests/fixtures/github/tag-commit/found.json records a tag naming.
  const built = "81c986c0e0a7c511f2941ed3cec09f7975687f80"

  const moved =
    "v0.0.3 names a commit other than 81c986c0e0a7c511f2941ed3cec09f7975687f80, which CI passed on; the tag's own run publishes from its commit"
  // A gh that answers gh api and gh release view from their queues of replies, and gh release create, upload and edit
  // with the success replies recorded above; it fails on any other command, and on a queue left empty.
  function fakeGh(replies: Record<"api" | "view", GhResult[]>) {
    const calls: string[][] = []
    const gh = async (args: readonly string[]) => {
      calls.push([...args])
      const queue = args[0] === "api" ? replies.api : args[1] === "view" ? replies.view : undefined
      const reply = queue
        ? queue.shift()
        : args[0] === "release"
          ? succeeded.get(args[1] ?? "")
          : undefined
      return (await reply) ?? { code: 1, stdout: "", stderr: `no reply to gh ${args.join(" ")}` }
    }
    return { gh, calls }
  }

  async function dist(version = "0.0.3"): Promise<string> {
    const root = await folders.make()
    await mkdir(join(root, "dist"))
    await writeFile(join(root, `dist/nustack-${version}.zip`), "zip")
    await writeFile(join(root, "dist/notes.md"), "page")
    return root
  }

  test("drafts a missing release, uploads the zip and publishes a pre-release before v0.1.0", async () => {
    const root = await dist()
    const found = await recorded("tag-commit/found.json")
    const { gh, calls } = fakeGh({
      api: [found, found],
      view: [await recorded("release-state/missing.json")],
    })
    expect(await publish(root, "v0.0.3", built, gh)).toBe("Published v0.0.3")
    const api = ["api", "repos/{owner}/{repo}/commits/tags/v0.0.3", "--jq", ".sha"]
    expect(calls).toEqual([
      api,
      ["release", "view", "v0.0.3", "--json", "isDraft", "--jq", ".isDraft"],
      ["release", "create", "v0.0.3", "--draft", "--verify-tag", "--notes", ""],
      ["release", "upload", "v0.0.3", `${root}/dist/nustack-0.0.3.zip`, "--clobber"],
      api,
      [
        "release",
        "edit",
        "v0.0.3",
        "--draft=false",
        "--title",
        "nustack 0.0.3",
        "--notes-file",
        `${root}/dist/notes.md`,
        "--prerelease=true",
      ],
    ])
  })

  test("finishes a draft an earlier run left, as a full release from v0.1.0", async () => {
    const root = await dist("0.1.0")
    const found = await recorded("tag-commit/found.json")
    const { gh, calls } = fakeGh({
      api: [found, found],
      view: [await recorded("release-state/draft.json")],
    })
    expect(await publish(root, "v0.1.0", built, gh)).toBe("Published v0.1.0")
    expect(calls.map((args) => args.slice(0, 2).join(" "))).toEqual([
      "api repos/{owner}/{repo}/commits/tags/v0.1.0",
      "release view",
      "release upload",
      "api repos/{owner}/{repo}/commits/tags/v0.1.0",
      "release edit",
    ])
    expect(calls[4]?.at(-1)).toBe("--prerelease=false")
  })

  test("publishes nothing when the zip's upload fails, as on a release GitHub cannot find", async () => {
    const root = await dist()
    const found = await recorded("tag-commit/found.json")
    const { gh, calls } = fakeGh({
      api: [found, found],
      view: [await recorded("release-state/draft.json")],
    })
    const missing = await recorded("upload/missing.json")
    const failing = async (args: readonly string[]) => (args[1] === "upload" ? missing : gh(args))
    await expect(publish(root, "v0.0.3", built, failing)).rejects.toThrow(
      `gh release upload v0.0.3 ${root}/dist/nustack-0.0.3.zip --clobber exited 1: release not found; fix that, then rerun`,
    )
    expect(calls.map((args) => args[1])).toEqual([
      "repos/{owner}/{repo}/commits/tags/v0.0.3",
      "view",
    ])
  })

  // release-edit/missing.json is gh 2.78.0's reply, off a terminal and unredacted, to publish's own edit command run with
  // GH_REPO set to Nusnus-Private/nustack on record-fixture-1794075916, a tag with no release, so gh stopped before it
  // wrote anything.
  test("stops when gh cannot finish the release, publishing nothing", async () => {
    const root = await dist()
    const found = await recorded("tag-commit/found.json")
    const { gh, calls } = fakeGh({
      api: [found, found],
      view: [await recorded("release-state/draft.json")],
    })
    const refused = await recorded("release-edit/missing.json")
    const failing = async (args: readonly string[]) => (args[1] === "edit" ? refused : gh(args))
    await expect(publish(root, "v0.0.3", built, failing)).rejects.toThrow(
      `gh release edit v0.0.3 --draft=false --title nustack 0.0.3 --notes-file ${root}/dist/notes.md --prerelease=true exited 1: release not found; fix that, then rerun`,
    )
    expect(calls.map((args) => args[1])).toEqual([
      "repos/{owner}/{repo}/commits/tags/v0.0.3",
      "view",
      "upload",
      "repos/{owner}/{repo}/commits/tags/v0.0.3",
    ])
  })

  test("leaves a published release as it is", async () => {
    const root = await dist()
    const { gh, calls } = fakeGh({
      api: [await recorded("tag-commit/found.json")],
      view: [await recorded("release-state/published.json")],
    })
    expect(await publish(root, "v0.0.3", built, gh)).toBe(
      "v0.0.3 is already published, so it stays as it is, with the zip it was published with",
    )
    expect(calls).toEqual([
      ["api", "repos/{owner}/{repo}/commits/tags/v0.0.3", "--jq", ".sha"],
      ["release", "view", "v0.0.3", "--json", "isDraft", "--jq", ".isDraft"],
    ])
  })

  test("publishes nothing once the tag names another commit, before the draft or after the upload", async () => {
    const root = await dist()
    const found = await recorded("tag-commit/found.json")
    const other = { ...found, stdout: "0000000000000000000000000000000000000001\n" }
    const before = fakeGh({ api: [other], view: [] })
    await expect(publish(root, "v0.0.3", built, before.gh)).rejects.toThrow(moved)
    expect(before.calls).toEqual([
      ["api", "repos/{owner}/{repo}/commits/tags/v0.0.3", "--jq", ".sha"],
    ])
    const after = fakeGh({
      api: [found, other],
      view: [await recorded("release-state/draft.json")],
    })
    await expect(publish(root, "v0.0.3", built, after.gh)).rejects.toThrow(moved)
    expect(after.calls.map((args) => args[1])).toEqual([
      "repos/{owner}/{repo}/commits/tags/v0.0.3",
      "view",
      "upload",
      "repos/{owner}/{repo}/commits/tags/v0.0.3",
    ])
  })

  // release-create/missing-tag.json is gh 2.78.0's reply, off a terminal and unredacted, to publish's own create command
  // run with GH_REPO set to Nusnus-Private/nustack on record-fixture-1794075711, a tag the repository did not hold, so
  // --verify-tag stopped gh before it created anything.
  test("publishes nothing when gh cannot create the release, uploading no zip", async () => {
    const root = await dist()
    const { gh, calls } = fakeGh({
      api: [await recorded("tag-commit/found.json")],
      view: [await recorded("release-state/missing.json")],
    })
    const refused = await recorded("release-create/missing-tag.json")
    const failing = async (args: readonly string[]) => (args[1] === "create" ? refused : gh(args))
    await expect(publish(root, "v0.0.3", built, failing)).rejects.toThrow(
      "gh release create v0.0.3 --draft --verify-tag --notes  exited 1: tag record-fixture-1794075711 doesn't exist in the repo Nusnus-Private/nustack, aborting due to --verify-tag flag; fix that, then rerun",
    )
    expect(calls.map((args) => args[1])).toEqual([
      "repos/{owner}/{repo}/commits/tags/v0.0.3",
      "view",
    ])
  })

  test("publishes nothing on a tag GitHub cannot find, before the draft or after the upload", async () => {
    const root = await dist()
    const [found, missing] = [
      await recorded("tag-commit/found.json"),
      await recorded("tag-commit/missing.json"),
    ]
    const gone =
      "v0.0.3 names no commit GitHub can find; push it again if it was deleted, then rerun"
    const before = fakeGh({ api: [missing], view: [] })
    await expect(publish(root, "v0.0.3", built, before.gh)).rejects.toThrow(gone)
    expect(before.calls.map((args) => args[1])).toEqual([
      "repos/{owner}/{repo}/commits/tags/v0.0.3",
    ])
    const after = fakeGh({
      api: [found, missing],
      view: [await recorded("release-state/draft.json")],
    })
    await expect(publish(root, "v0.0.3", built, after.gh)).rejects.toThrow(gone)
    expect(after.calls.map((args) => args[1])).toEqual([
      "repos/{owner}/{repo}/commits/tags/v0.0.3",
      "view",
      "upload",
      "repos/{owner}/{repo}/commits/tags/v0.0.3",
    ])
  })

  test("stops on a release gh cannot read, naming what gh printed", async () => {
    const root = await dist()
    const { gh } = fakeGh({
      api: [await recorded("tag-commit/found.json")],
      view: [await recorded("release-state/unauthorized.json")],
    })
    await expect(publish(root, "v0.0.3", built, gh)).rejects.toThrow(
      "gh release view v0.0.3 --json isDraft --jq .isDraft exited 1: HTTP 401: Bad credentials (https://api.github.com/repos/microsoft/bioemu/releases/tags/v1.4.0)\nTry authenticating with:  gh auth login; fix that, then rerun",
    )
  })

  test.each([
    ["0.0.3", built, "pass the tag as v<major>.<minor>.<patch>"],
    ["v0.3", built, "pass the tag as v<major>.<minor>.<patch>"],
    ["x0.0.3", built, "pass the tag as v<major>.<minor>.<patch>"],
    ["v0.0.3", "81c986c", "pass the commit CI passed on as its full SHA"],
    ["v0.0.3", "", "pass the commit CI passed on as its full SHA"],
    ["v0.0.3", "a".repeat(39), "pass the commit CI passed on as its full SHA"],
  ])("refuses the tag %p with the commit %p: %s", async (name, commit, message) => {
    const { gh, calls } = fakeGh({ api: [], view: [] })
    await expect(publish(await dist(), name, commit, gh)).rejects.toThrow(message)
    expect(calls).toEqual([])
  })

  test("stops on a release state gh gives as neither true nor false", async () => {
    const found = await recorded("tag-commit/found.json")
    const { gh } = fakeGh({ api: [found], view: [{ ...found, stdout: "null\n" }] })
    await expect(publish(await dist(), "v0.0.3", built, gh)).rejects.toThrow(
      "gh release view v0.0.3 --json isDraft --jq .isDraft printed neither true nor false; rerun once GitHub answers",
    )
  })

  test.each([
    [
      "dist/nustack-0.0.3.zip",
      "dist/ holds no nustack-0.0.3.zip; download the release artifact CI built, then rerun",
    ],
    [
      "dist/notes.md",
      "dist/ holds no notes.md; download the release artifact CI built, then rerun",
    ],
    [
      "dist",
      "dist/ holds no nustack-0.0.3.zip; download the release artifact CI built, then rerun",
    ],
  ])("refuses a release artifact without %s", async (missing, message) => {
    const root = await dist()
    await rm(join(root, missing), { recursive: true })
    const { gh, calls } = fakeGh({ api: [], view: [] })
    await expect(publish(root, "v0.0.3", built, gh)).rejects.toThrow(message)
    expect(calls).toEqual([])
  })
})
