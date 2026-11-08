/** A sync's file changes and the pull request body that lists them. */
import { describe, expect, spyOn, test } from "bun:test"
import { readFileSync } from "node:fs"
import { join } from "node:path"
import * as parser from "../../../scripts/markdown.ts"
import { body, change, checkTemplate, linksOf, type Proposal } from "../../../scripts/sync.ts"

const [a, b, c] = ["a".repeat(40), "b".repeat(40), "c".repeat(40)] as const
// The repository's own PR template, so a test fails once body() and it drift apart.
const written = readFileSync(
  join(import.meta.dir, "../../../.github/pull_request_template.md"),
  "utf8",
)
const template = checkTemplate(written)

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

describe("checkTemplate", () => {
  test("refuses a template whose parts or placeholders it does not know", () => {
    expect(() => checkTemplate(written.replace("#### Review first", "#### Review"))).toThrow(
      new Error(
        ".github/pull_request_template.md: its #### parts are not What changed, Risk, Review first, After merge, Checks, Files, Decisions; update body() in scripts/sync.ts to match",
      ),
    )
    expect(() => checkTemplate(written.replace("<!-- Review -->", "<!-- Notes -->"))).toThrow(
      new Error(
        ".github/pull_request_template.md: holds a placeholder body() in scripts/sync.ts cannot fill; fill it there",
      ),
    )
  })

  test("reads the comment that opens the template as guidance, not as a placeholder", () => {
    const guidance = written.slice(0, written.indexOf("-->") + "-->".length)
    expect(() => checkTemplate(written.replace(guidance, "<!-- Notes -->"))).not.toThrow()
  })

  test("reads each placeholder of a template that opens with no guidance comment", () => {
    const unguided = written.slice(written.indexOf("-->") + "-->".length).trimStart()
    expect(() => checkTemplate(`Notes: <!-- Notes -->\n\n${unguided}`)).toThrow(
      new Error(
        ".github/pull_request_template.md: holds a placeholder body() in scripts/sync.ts cannot fill; fill it there",
      ),
    )
  })
})

describe("body", () => {
  const copy = {
    upstream: "https://h/o/n",
    source: "s",
    folder: "plugin/skills",
    skills: ["s"],
    commit: a,
    files: {},
  } as const
  const changes = { changed: ["s/edit"], added: [], removed: ["s/gone"] }
  const proposal: Proposal = {
    path: "vendored/x.json",
    copy,
    changes,
    unlisted: [],
    recordChanges: true,
    links: {},
  }

  test("fills the PR template's parts a sync has, listing only the kinds of change it holds", () => {
    expect(body(template, proposal)).toBe(
      [
        '<div align="center">',
        "",
        "### Copy x from upstream",
        "",
        `Copies s from https://h/o/n at ${a}, and updates vendored/x.json to match.`,
        "",
        "![Risk: medium](https://img.shields.io/badge/risk-medium-9a6700?style=flat-square) ![Checks: CI not run](https://img.shields.io/badge/checks-CI%20not%20run-9a6700?style=flat-square) ![Size: 3 files](https://img.shields.io/badge/size-3%20files-6e7781?style=flat-square)",
        "",
        "</div>",
        "",
        "#### What changed",
        "",
        "- Changes 1 file of the copy.",
        "- Removes 1 file of the copy.",
        "- Sets the record's commit and blobs to upstream's.",
        "",
        "#### Risk",
        "",
        "Medium. The copy's text reaches every plugin user's agent and steers it. Close this pull request to keep the current copy.",
        "",
        "#### Review first",
        "",
        "- Read the copy as untrusted text, as REVIEW.md says, starting from the files in the fold.",
        "- Before the merge, add the copy's CHANGELOG.md entry, as AGENTS.md › Pull requests says, and set the checks badge to the checks' state.",
        "",
        "<details>",
        "<summary>Checks and files</summary>",
        "",
        "#### Checks",
        "",
        "- CI had not run when the sync wrote this description.",
        "",
        "#### Files",
        "",
        "- `s/edit`, changed",
        "- `s/gone`, removed",
        "- `vendored/x.json`, the record",
        "",
        "</details>",
        "",
      ].join("\n"),
    )
  })

  test("gives a copy outside the plugin low risk with no risk part, and names each unlisted upstream skill", () => {
    const outside = { ...copy, folder: ".agents/skills" } as const
    const text = body(template, { ...proposal, copy: outside, unlisted: ["t", "u"] })
    expect(text).toContain(
      "![Risk: low](https://img.shields.io/badge/risk-low-1f883d?style=flat-square)",
    )
    expect(text).not.toContain("#### Risk")
    expect(text).toContain(
      "- Upstream also holds t, u, which the record does not list; add a skill to the record to copy it.\n",
    )
  })

  test("counts and lists only the copy's files when the record stays as it was", () => {
    const text = body(template, { ...proposal, recordChanges: false })
    expect(text).toContain(`Copies s from https://h/o/n at ${a}.\n`)
    expect(text).toContain(
      "![Size: 2 files](https://img.shields.io/badge/size-2%20files-6e7781?style=flat-square)",
    )
    expect(text).toContain("- Removes 1 file of the copy.\n\n#### Risk")
    expect(text).toContain("- `s/gone`, removed\n\n</details>")
  })

  test("counts the changed and the added files, and names each skill the copy holds", () => {
    const text = body(template, {
      ...proposal,
      copy: { ...copy, skills: ["s", "t"] },
      changes: { changed: ["s/edit"], added: ["t/new"], removed: [] },
      recordChanges: false,
    })
    expect(text).toContain(`Copies s, t from https://h/o/n at ${a}.\n`)
    expect(text).toContain(
      "![Size: 2 files](https://img.shields.io/badge/size-2%20files-6e7781?style=flat-square)",
    )
    expect(text).toContain("- Changes 1 file of the copy.\n- Adds 1 file of the copy.\n")
  })

  test("keeps a template's first block when no guidance comment opens it", () => {
    const unguided = checkTemplate(written.slice(written.indexOf("-->") + "-->".length).trimStart())
    expect(body(unguided, proposal)).toBe(body(template, proposal))
  })

  test("drops the template's last part with its heading when the sync leaves it empty", () => {
    const open = written.replace(/\n<\/details>\n$/, "\n")
    expect(open).not.toBe(written)
    expect(body(checkTemplate(open), proposal)).toEndWith("- `vendored/x.json`, the record\n")
  })

  test("leaves out a block whose only placeholder fills to nothing, with no blank block in its place", () => {
    const none = { changed: [], added: [], removed: [] }
    const text = body(template, { ...proposal, changes: none, recordChanges: false })
    expect(text).not.toContain("\n\n\n")
    expect(text).toEndWith("- CI had not run when the sync wrote this description.\n\n</details>\n")
  })

  test("fills each of a block's placeholders where it stands", () => {
    const both = written.replace(
      "### <!-- Headline -->",
      "### <!-- Headline -->: <!-- What the change does for its reader -->",
    )
    expect(both).not.toBe(written)
    expect(body(checkTemplate(both), proposal)).toContain(
      `### Copy x from upstream: Copies s from https://h/o/n at ${a}, and updates vendored/x.json to match.\n`,
    )
  })

  test("keeps a heading of another depth than a part's when a heading follows it", () => {
    const notes = written.replace("#### What changed", "### Notes\n\n#### What changed")
    expect(notes).not.toBe(written)
    expect(body(checkTemplate(notes), proposal)).toContain("### Notes\n\n#### What changed\n")
  })

  test("fills the template from checkTemplate's parse, parsing no Markdown itself", () => {
    const parse = spyOn(parser, "markdown")
    try {
      body(template, proposal)
      expect(parse).not.toHaveBeenCalled()
    } finally {
      parse.mockRestore()
    }
  })
})

describe("linksOf", () => {
  const copy = {
    upstream: "https://github.com/o/n",
    source: "s",
    folder: "plugin/skills",
    skills: ["s"],
    commit: a,
    files: {},
  } as const
  const env = {
    GITHUB_SERVER_URL: "https://github.com",
    GITHUB_REPOSITORY: "o/r",
    GITHUB_RUN_ID: "7",
  }

  test("links the Actions run and GitHub's compare page from the recorded commit", () => {
    expect(linksOf(copy, b, env)).toEqual({
      run: "https://github.com/o/r/actions/runs/7",
      compare: `https://github.com/o/n/compare/${a}...${b}`,
    })
  })

  test("leaves out the run outside Actions, and the compare page for a first copy, the same commit or another host", () => {
    expect(linksOf({ ...copy, commit: null }, b, {})).toEqual({})
    expect(linksOf(copy, a, {})).toEqual({})
    expect(linksOf({ ...copy, upstream: "https://h/o/n" }, b, {})).toEqual({})
  })

  test("gives no run link without the repository the run belongs to", () => {
    const env = { GITHUB_SERVER_URL: "https://github.com", GITHUB_RUN_ID: "7" }
    expect(linksOf({ ...copy, commit: null }, b, env)).toEqual({})
  })
})

test("body gives the compare page under the changes and the run under the checks", () => {
  const copy = {
    upstream: "https://h/o/n",
    source: "s",
    folder: ".agents/skills",
    skills: ["s"],
    commit: a,
    files: {},
  } as const
  const text = body(template, {
    path: "vendored/x.json",
    copy,
    changes: { changed: [], added: [], removed: [] },
    unlisted: [],
    recordChanges: true,
    links: { run: "https://run", compare: "https://compare" },
  })
  expect(text).toContain(
    "- Sets the record's commit and blobs to upstream's.\n- Upstream's commits since the last sync: https://compare\n",
  )
  expect(text).toContain(
    "- CI had not run when the sync wrote this description.\n- The sync run that wrote it: https://run\n",
  )
})
