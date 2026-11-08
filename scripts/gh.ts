/**
 * Runs gh for the release and sync scripts. gh takes the repository and host from GH_REPO and GH_HOST
 * (https://cli.github.com/manual/gh_help_environment), as each workflow step that runs it names them. A gh that runs past
 * its time limit is killed, and a gh that fails stops the script with what it printed to stderr.
 */

/** What a gh command printed and its exit code. */
export type GhResult = Readonly<{ code: number; stdout: string; stderr: string }>

/** Runs gh with the given arguments. */
export type Gh = (args: readonly string[]) => Promise<GhResult>

const GH_LIMIT_MS = 60_000

export async function ghOutput(gh: Gh, args: readonly string[], ran?: GhResult): Promise<string> {
  const { code, stdout, stderr } = ran ?? (await gh(args))
  if (code !== 0)
    throw new Error(`gh ${args.join(" ")} exited ${code}: ${stderr.trim()}; fix that, then rerun`)
  return stdout
}

export async function runGh(args: readonly string[], limit = GH_LIMIT_MS): Promise<GhResult> {
  const child = Bun.spawn(["gh", ...args], { stdout: "pipe", stderr: "pipe" })
  let stalled = false
  const timer = setTimeout(() => {
    stalled = true
    child.kill("SIGKILL")
  }, limit)
  try {
    const [stdout, stderr, code] = await Promise.all([
      new Response(child.stdout).text(),
      new Response(child.stderr).text(),
      child.exited,
    ])
    if (stalled)
      throw new Error(
        `gh ${args.join(" ")} took over ${limit / 1000} seconds; rerun once GitHub answers`,
      )
    return { code, stdout, stderr }
  } finally {
    clearTimeout(timer)
  }
}
