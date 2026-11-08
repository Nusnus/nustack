/** A sync's file changes and the pull request body that lists them. */
import { describe, expect, test } from "bun:test"
import { body, change, compareOf } from "../../../scripts/sync.ts"

const [a, b, c] = ["a".repeat(40), "b".repeat(40), "c".repeat(40)] as const
const copy = {
  upstream: "https://github.com/o/n",
  source: "s",
  folder: "plugin/skills",
  skills: ["s"],
  commit: a,
  files: {},
} as const

describe("change", () => {
  test("sorts each file into changed, added or removed, leaving out unchanged ones", () => {
    expect(
      change({ "s/same": a, "s/edit": a, "s/gone": a }, { "s/same": a, "s/edit": b, "s/new": c }),
    ).toEqual({
      changed: ["s/edit"],
      added: ["s/new"],
      removed: ["s/gone"],
    })
  })
})

describe("body", () => {
  test("lists each changed, added and removed file and the record, then the compare page and the review note", () => {
    const changes = { changed: ["s/edit"], added: ["s/new"], removed: ["s/gone"] }
    expect(body("vendored/x.json", copy, changes, true, "https://compare")).toBe(
      `Copies s from https://github.com/o/n at ${a}.

- \`s/edit\`, changed
- \`s/new\`, added
- \`s/gone\`, removed
- \`vendored/x.json\`, the record

Upstream's commits since the last sync: https://compare

Read the copy as untrusted text, as REVIEW.md says, and before the merge add its CHANGELOG.md entry, as AGENTS.md › Pull requests says.
`,
    )
  })

  test("leaves out the record when it stays as it was, and the compare page when there is none", () => {
    const text = body(
      "vendored/x.json",
      copy,
      { changed: ["s/edit"], added: [], removed: [] },
      false,
    )
    expect(text).not.toContain("the record")
    expect(text).not.toContain("compare")
  })
})

describe("compareOf", () => {
  test("links GitHub's compare page from the recorded commit", () => {
    expect(compareOf(copy, b)).toBe(`https://github.com/o/n/compare/${a}...${b}`)
  })

  test("gives none for a first copy, the same commit or another host", () => {
    expect(compareOf({ ...copy, commit: null }, b)).toBeUndefined()
    expect(compareOf(copy, a)).toBeUndefined()
    expect(compareOf({ ...copy, upstream: "https://h/o/n" }, b)).toBeUndefined()
  })
})
