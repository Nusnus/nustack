/**
 * The release workflow's jobs and CI's release zip run in their order, and each job of each workflow that runs a bun
 * script installs bun.lock first, from the repository's root.
 */
import { describe, expect, test } from "bun:test"
import { problem, type Tree } from "../../../scripts/tree.ts"
import { jobOrderProblems, workflowInstallProblems } from "../../../scripts/workflows.ts"
import { tree } from "../../fixtures/metadata.ts"

describe("jobOrderProblems", () => {
  const release = ".github/workflows/release.yml"
  const ci = ".github/workflows/ci.yml"
  const jobs = "jobs:\n  ci:\n    needs: tag\n  publish:\n    needs: ci\n"
  const zip = "jobs:\n  release-zip:\n    needs: make-check\n"
  const files = (releaseText: string, ciText: string): Tree =>
    new Map([
      [release, new TextEncoder().encode(releaseText)],
      [ci, new TextEncoder().encode(ciText)],
    ])
  const tagged = problem(
    `${release}: jobs.ci.needs is not tag, so CI could run on a tag that names no version on main; set it to tag`,
  )
  const published = problem(
    `${release}: jobs.publish.needs is not ci, so a release could publish before CI passes; set it to ci`,
  )
  const zipped = problem(
    `${ci}: jobs.release-zip.needs is not make-check, so the release zip could build from a commit make check fails; set it to make-check`,
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
    expect(jobOrderProblems(files(releaseText, ciText))).toEqual(problems)
  })

  test("gives a release and a CI workflow that do not parse only that problem each", () => {
    expect(jobOrderProblems(files("{", "{"))).toEqual(
      [release, ci].map((path) => problem(`${path}: does not parse as its format; fix its syntax`)),
    )
  })
})

describe("workflowInstallProblems", () => {
  const path = ".github/workflows/sync.yml"
  const install = "      - run: bun install --frozen-lockfile\n"
  const script = "      - run: bun scripts/sync.ts list\n"
  const fix = (job: string) =>
    problem(
      `${path}: ${job} runs bun scripts/ before installing bun.lock; run bun install --frozen-lockfile in that job first, after setup-bun`,
    )

  test.each([
    [`jobs:\n  records:\n    steps:\n${install}${script}`, []],
    [
      "jobs:\n  records:\n    steps:\n      - run: make bundle && bun scripts/release.ts notes\n",
      [fix("jobs.records")],
    ],
    ["jobs:\n  records:\n    steps:\n      - uses: oven-sh/setup-bun@v2\n", []],
    [`jobs:\n  records:\n    steps:\n${script}`, [fix("jobs.records")]],
    [`jobs:\n  records:\n    steps:\n${script}${install}`, [fix("jobs.records")]],
    [
      `jobs:\n  records:\n    steps:\n${install}\n  sync:\n    steps:\n${script}`,
      [fix("jobs.sync")],
    ],
    [`jobs:\n  "a b":\n    steps:\n${script}`, [fix("a job")]],
    [`jobs:\n  _x:\n    steps:\n${script}`, [fix("jobs._x")]],
    [`jobs:\n  "1x":\n    steps:\n${script}`, [fix("a job")]],
    ["jobs:\n  records:\n    steps:\n      - run: bun scripts.ts\n", []],
    [
      "jobs:\n  records:\n    steps:\n      - run: CI= bun scripts/sync.ts list\n",
      [fix("jobs.records")],
    ],
    ["jobs:\n  records:\n    steps:\n      - run: 1X= bun scripts/sync.ts list\n", []],
    [
      "jobs:\n  records:\n    steps:\n      - run: A=1 B=2 bun scripts/sync.ts list\n",
      [fix("jobs.records")],
    ],
    [
      'jobs:\n  records:\n    steps:\n      - run: "env\\tCI=1\\tbun scripts/sync.ts list"\n',
      [fix("jobs.records")],
    ],
    ["- jobs\n", []],
  ])("reads %p", (text, problems) => {
    expect(workflowInstallProblems(tree(path, text))).toEqual(problems)
  })

  // jobOrderProblems reports a release or CI workflow that does not parse.
  test.each([
    [".github/workflows/sub/x.yml", `jobs:\n  records:\n    steps:\n${script}`, []],
    ["x/.github/workflows/a.yml", `jobs:\n  records:\n    steps:\n${script}`, []],
    [".github/workflows/a.yml.orig", `jobs:\n  records:\n    steps:\n${script}`, []],
    [
      ".github/workflows/other.yml",
      "jobs: [",
      [problem(".github/workflows/other.yml: does not parse as its format; fix its syntax")],
    ],
    [".github/workflows/release.yml", "jobs: [", []],
    [".github/workflows/ci.yml", "jobs: [", []],
  ])("reads %s holding %p", (at, text, problems) => {
    expect(workflowInstallProblems(tree(at, text))).toEqual(problems)
  })
})
