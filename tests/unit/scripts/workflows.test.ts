/** The release workflow's jobs and CI's release zip run in their order. */
import { expect, test } from "bun:test"
import { problem, type Tree } from "../../../scripts/tree.ts"
import { CI_WORKFLOW, RELEASE_WORKFLOW, workflowProblems } from "../../../scripts/workflows.ts"

const jobs = "jobs:\n  ci:\n    needs: tag\n  publish:\n    needs: ci\n"
const zip = "jobs:\n  release-zip:\n    needs: make-check\n"
const files = (releaseText: string, ciText: string): Tree =>
  new Map([
    [RELEASE_WORKFLOW, new TextEncoder().encode(releaseText)],
    [CI_WORKFLOW, new TextEncoder().encode(ciText)],
  ])
const tagged = problem(
  `${RELEASE_WORKFLOW}: jobs.ci.needs is not tag, so CI could run on a tag that names no version on main; set it to tag`,
)
const published = problem(
  `${RELEASE_WORKFLOW}: jobs.publish.needs is not ci, so a release could publish before CI passes; set it to ci`,
)
const zipped = problem(
  `${CI_WORKFLOW}: jobs.release-zip.needs is not make-check, so the release zip could build from a commit make check fails; set it to make-check`,
)

test.each([
  [jobs, zip, []],
  ["- on\n", zip, [tagged, published]],
  [jobs.replace("needs: tag", "needs: [tag]"), zip, [tagged]],
  [jobs.replace("needs: ci", "needs: tag"), zip, [published]],
  [jobs, "jobs:\n  release-zip:\n    runs-on: ubuntu-26.04\n", [zipped]],
  [jobs, "jobs:\n  release-zip:\n    needs: smoke\n", [zipped]],
  [jobs, "- jobs\n", [zipped]],
])("reads %p beside %p", (releaseText, ciText, problems) => {
  expect(workflowProblems(files(releaseText, ciText))).toEqual(problems)
})

test("gives a release and a CI workflow that do not parse only that problem each", () => {
  expect(workflowProblems(files("{", "{"))).toEqual(
    [RELEASE_WORKFLOW, CI_WORKFLOW].map((path) =>
      problem(`${path}: does not parse as its format; fix its syntax`),
    ),
  )
})

test.each([
  [
    `${jobs}#${"x".repeat(16384)}\n`,
    ".github/workflows/release.yml: holds more than 16384 characters, the most Bun's parser reads safely; shorten it",
  ],
  [
    `${jobs}a: ${"- ".repeat(200)}x\n`,
    ".github/workflows/release.yml: may nest more than 200 levels deep, the most Bun's parser reads safely; flatten it",
  ],
])(
  "gives a release workflow Bun's parser cannot read safely only that problem",
  (releaseText, fault) => {
    expect(workflowProblems(files(releaseText, zip))).toEqual([problem(fault)])
  },
)
