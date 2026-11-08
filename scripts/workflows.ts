/**
 * The check's workflows rule: the needs that order the release workflow's jobs and CI's release zip, and each job of
 * each workflow that runs a bun script installing bun.lock first, from the repository's root. A problem repeats no value
 * read from a file, apart from a workflow's job id.
 */
import { decode, isObject, type Problem, parseYaml, problem, type Tree, valueAt } from "./tree.ts"

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
// The scripts import packages bun.lock pins. With no node_modules, Bun resolves each import through auto-install into
// its global cache (https://bun.com/docs/runtime/auto-install), not from an install that checked bun.lock, so a job
// installs from bun.lock before it runs one. A step's commands split at each line break, &&, ;, |, ( and `, a |
// splitting || too, and each counts by how it starts, so an install only echoed or quoted installs nothing. An install
// counts only where no working-directory, of its step or of its job's or the workflow's defaults.run, moves it from the
// repository's root, which holds bun.lock:
// https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#defaultsrunworking-directory
// The rule catches a job that forgot to install; one that defeats it on purpose, such as with if: false on the install
// or true || before it, is out of its scope.
const COMMAND_BREAK = /\n|&&|[;|(`]/
// bun runs a script by its path, with or without run and ./, after env and any variables the command sets first.
export const RUNS_SCRIPT = /^(?:env\s+)?(?:[A-Za-z_]\w*=\S*\s+)*bun (?:run )?(?:\.\/)?scripts\//
export const INSTALL = "bun install --frozen-lockfile"
// GitHub runs each .yml or .yaml file directly in .github/workflows:
// https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
const WORKFLOW = /^\.github\/workflows\/[^/]+\.ya?ml$/
// GitHub limits a job id to letters, digits, - and _, starting with a letter or _:
// https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_id
const JOB_ID = /^[A-Za-z_][\w-]*$/

export function workflowProblems(tree: Tree): Problem[] {
  return [...jobOrderProblems(tree), ...workflowInstallProblems(tree)]
}

// The release and CI workflows each report here once that they do not parse.
export function jobOrderProblems(tree: Tree): Problem[] {
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

// jobOrderProblems reports a release or CI workflow that does not parse.
export function workflowInstallProblems(tree: Tree): Problem[] {
  return [...tree.keys()]
    .filter((path) => WORKFLOW.test(path))
    .flatMap((path) => {
      const read = decode(tree, path, parseYaml)
      if (Array.isArray(read)) return installProblems(path, read[0])
      return path === RELEASE_WORKFLOW || path === CI_WORKFLOW ? [] : [read.problem]
    })
}

function installProblems(path: string, workflow: unknown): Problem[] {
  const jobs = valueAt(workflow, ["jobs"])
  if (!isObject(jobs)) return []
  return Object.entries(jobs).flatMap(([id, job]) => {
    const steps = valueAt(job, ["steps"])
    const moved = [workflow, job].some(
      (at) => valueAt(at, ["defaults", "run", "working-directory"]) !== undefined,
    )
    const commands = (Array.isArray(steps) ? steps : []).flatMap((step) => {
      const run = valueAt(step, ["run"])
      const atRoot = !moved && valueAt(step, ["working-directory"]) === undefined
      return typeof run === "string" ? commandsOf(run).map((command) => ({ command, atRoot })) : []
    })
    const script = commands.findIndex(({ command }) => RUNS_SCRIPT.test(command))
    const install = commands.findIndex(({ command, atRoot }) => atRoot && command === INSTALL)
    if (script < 0 || (install >= 0 && install < script)) return []
    const name = JOB_ID.test(id) ? `jobs.${id}` : "a job"
    return [
      problem(
        `${path}: ${name} runs bun scripts/ before installing bun.lock; run bun install --frozen-lockfile in that job first, after setup-bun`,
      ),
    ]
  })
}

export function commandsOf(run: string): string[] {
  return run.split(COMMAND_BREAK).map((command) => command.trim())
}
