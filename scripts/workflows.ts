/** The check's workflows rule: the needs that order the release workflow's jobs and CI's release zip. */
import { decode, type Problem, parseYaml, problem, type Tree, valueAt } from "./tree.ts"

export const RELEASE_WORKFLOW = ".github/workflows/release.yml"
export const CI_WORKFLOW = ".github/workflows/ci.yml"
// The needs that order the release workflow's jobs and CI's release zip, each with what could happen without it.
const JOB_ORDER = Object.freeze([
  [RELEASE_WORKFLOW, "ci", "tag", "CI could run on a tag that names no version on main"],
  [RELEASE_WORKFLOW, "publish", "ci", "a release could publish before CI passes"],
  [
    CI_WORKFLOW,
    "release-zip",
    "make-check",
    "the release zip could build from a commit make check fails",
  ],
] as const)

export function workflowProblems(tree: Tree): Problem[] {
  return [RELEASE_WORKFLOW, CI_WORKFLOW].flatMap((path) => {
    const read = decode(tree, path, parseYaml)
    if (!Array.isArray(read)) return [read.problem]
    return JOB_ORDER.filter(
      ([at, job, needs]) => at === path && valueAt(read[0], ["jobs", job, "needs"]) !== needs,
    ).map(([, job, needs, unordered]) =>
      problem(`${path}: jobs.${job}.needs is not ${needs}, so ${unordered}; set it to ${needs}`),
    )
  })
}
