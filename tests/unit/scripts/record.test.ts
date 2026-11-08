/**
 * A record in vendored/ parses into its frozen model or into its problems, and a file's blob is Git's. Each clause of a
 * record's shape is tested through the check, in tests/unit/scripts/check.test.ts, and here where the check holds only
 * one record of each kind.
 */
import { expect, test } from "bun:test"
import { blobOf, type CopyRecord, parseRecord } from "../../../scripts/record.ts"
import { problem } from "../../../scripts/tree.ts"

const bytes = (value: unknown) => new TextEncoder().encode(`${JSON.stringify(value, null, 2)}\n`)
const record = {
  upstream: "https://h/o/n",
  source: "skills",
  folder: "plugin/skills" as const,
  skills: ["s"],
  commit: "a".repeat(40),
  files: { "s/LICENSE": "b".repeat(40), "s/SKILL.md": "c".repeat(40) },
}

test("gives a file the blob Git gives it", () => {
  expect(blobOf(new TextEncoder().encode("x\n"))).toBe("587be6b4c3f93f93c489c0111bba5596147a26cb")
})

test("parses a record into a frozen model", () => {
  const parsed = parseRecord("vendored/x.json", bytes(record))
  expect(parsed).toEqual(record)
  const { skills, files } = parsed as CopyRecord
  expect([parsed, skills, files].map(Object.isFrozen)).toEqual([true, true, true])
})

test("parses a new record, with commit null, files {} and a skill name of 64 characters", () => {
  const fresh = { ...record, skills: ["a".repeat(64)], commit: null, files: {} }
  expect(parseRecord("vendored/x.json", bytes(fresh))).toEqual(fresh)
})

test("refuses a record that is not JSON", () => {
  expect(parseRecord("vendored/x.json", new TextEncoder().encode("{"))).toEqual([
    problem("vendored/x.json: does not parse as its format; fix its syntax"),
  ])
})

// vendored/x.json parses in the tests above; check.test.ts refuses vendored/Bad.json, and
// tests/integration/scripts/sync.test.ts refuses vendored/sub/x.json.
test.each([
  ["vendored/x.json.bak", "vendored/x.json.bak: is not named <copy>.json in kebab case; rename it"],
  ["r.json", "r.json: is not named <copy>.json in kebab case; rename it"],
  ["vendored/r.JSON", "vendored/r.JSON: is not named <copy>.json in kebab case; rename it"],
  [
    "vendored/.hidden.json",
    "vendored/.hidden.json: is not named <copy>.json in kebab case; rename it",
  ],
  [
    "vendored/Foo Bar.json",
    "vendored/Foo Bar.json: is not named <copy>.json in kebab case; rename it",
  ],
  ["vendored/r s.json", "vendored/r s.json: is not named <copy>.json in kebab case; rename it"],
  ["vendored/r_s.json", "vendored/r_s.json: is not named <copy>.json in kebab case; rename it"],
  ["vendored/r-.json", "vendored/r-.json: is not named <copy>.json in kebab case; rename it"],
])("refuses a record named %p", (path, fix) => {
  expect(parseRecord(path, bytes(record))).toEqual([problem(fix)])
})

test("refuses a source that climbs out of upstream", () => {
  expect(parseRecord("vendored/x.json", bytes({ ...record, source: ".." }))).toEqual([
    problem("vendored/x.json: is not a record; make sure source is a folder path in upstream"),
  ])
})

// A source of .. is refused by the test above.
test.each([".", "skills/./knap", "skills/", "/skills", "", "skills//knap"])(
  "refuses the source %p, which is no folder path in upstream",
  (source) => {
    expect(parseRecord("vendored/x.json", bytes({ ...record, source }))).toEqual([
      problem("vendored/x.json: is not a record; make sure source is a folder path in upstream"),
    ])
  },
)

test("refuses an upstream that does not start with https://", () => {
  expect(
    parseRecord("vendored/x.json", bytes({ ...record, upstream: "git+https://h/o/n" })),
  ).toEqual([
    problem(
      "vendored/x.json: is not a record; make sure upstream is https://<host>/<owner>/<name>",
    ),
  ])
})

test.each([
  "https://github.com/Nusnus/nustack",
  "https://www.github.com/o/n",
  "https://github.com/o/.github",
  "https://github.com/a/n",
  "https://git-hub.x--y.example/o-p_q/n.x_y-z",
])("takes the upstream %p, a host, an owner and a name GitHub takes", (upstream) => {
  expect(parseRecord("vendored/x.json", bytes({ ...record, upstream }))).toEqual({
    ...record,
    upstream,
  })
})

test.each([
  "https://github.com/-bad/x",
  "https://github.com/bad-/x",
  "https://github.com/a--b/x",
  "https://a..b/o/n",
  "https://-h/o/n",
  "https://h-/o/n",
  "https://h:443/o/n",
  "https://h/o/n?x=1",
  "https://h/o/n#x",
  "https://h/../n",
  "https://h/o/..",
  "https://h/./n",
  "https://github.com/o/n/",
  "https://git hub.com/o/n",
  "https://github.com/o/n/x",
])("refuses the upstream %p, which names more than a host, an owner and a name", (upstream) => {
  expect(parseRecord("vendored/x.json", bytes({ ...record, upstream }))).toEqual([
    problem(
      "vendored/x.json: is not a record; make sure upstream is https://<host>/<owner>/<name>",
    ),
  ])
})

test("refuses a record that lists a skill's SKILL.md but not its LICENSE", () => {
  const files = { "s/SKILL.md": "c".repeat(40) }
  expect(parseRecord("vendored/x.json", bytes({ ...record, files }))).toEqual([
    problem(
      "vendored/x.json: is not a record; make sure files gives each skill its SKILL.md and LICENSE",
    ),
  ])
})

test("refuses a record with any skill named out of kebab case", () => {
  const fresh = { ...record, skills: ["s", "Bad"], commit: null, files: {} }
  expect(parseRecord("vendored/x.json", bytes(fresh))).toEqual([
    problem(
      "vendored/x.json: is not a record; make sure skills lists distinct skill names in kebab case",
    ),
  ])
})
