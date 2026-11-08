/**
 * Runs Git for the scripts. Each run is bounded: Git reaches a remote only over HTTPS, whose stall limits stop a transfer
 * that stops moving, and a backstop timer stops any other wait, such as a connection that opens and never answers. The
 * timer kills git's whole process group, so a helper such as git-remote-https ends with it, and the run returns at the
 * timer even where a pipe stays open. Git never prompts, so a missing credential fails at once.
 */

import { constants } from "node:os"

/** A Git command that failed: its exit code, and a message naming the command and what Git printed on stderr. */
export class GitError extends Error {
  override name = "GitError"
  readonly code: number

  constructor(message: string, code: number) {
    super(message)
    this.code = code
  }
}

// Git aborts a transfer slower than 1,000 bytes per second for 30 seconds:
// https://git-scm.com/docs/git-config#Documentation/git-config.txt-httplowSpeedLimit
const STALL_LIMITS = Object.freeze(["-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=30"])
// Four minutes, under the five-minute timeout of the sync and release workflows' jobs, the shortest of any job that
// runs a script, so a stalled run fails with its own problem before the job is cancelled.
export const BACKSTOP_MS = 240_000

/**
 * How a run may differ from the scripts' default. `transport` is the one Git may use, which the environment cannot
 * widen: https://git-scm.com/docs/git#Documentation/git.txt-GITALLOWPROTOCOL. Only a test passes `file`, to reach a
 * local repository, and a shorter `backstop`, in milliseconds.
 */
export type GitOptions = Readonly<{ transport?: "https" | "file"; backstop?: number }>
// Read at the first run, so loading this module starts no process.
let localKeys: readonly string[] | undefined

// Each running Git's process group. Each sits outside the caller's, so a Ctrl-C or a SIGTERM to the script reaches
// none of them, and the script kills each before it exits.
const live = new Set<number>()
let handling = false

export async function git(
  args: readonly string[],
  cwd: string,
  options: GitOptions = {},
): Promise<string> {
  return new TextDecoder().decode(await gitBytes(args, cwd, options))
}

export async function gitBytes(
  args: readonly string[],
  cwd: string,
  { transport = "https", backstop = BACKSTOP_MS }: GitOptions = {},
): Promise<Uint8Array> {
  const env: Record<string, string | undefined> = {
    ...process.env,
    GIT_ALLOW_PROTOCOL: transport,
    GIT_TERMINAL_PROMPT: "0",
  }
  localKeys ??= localEnvVars(env)
  // A hook exports variables such as GIT_INDEX_FILE, which would point each run at the hook's repository.
  for (const key of localKeys) delete env[key]
  killGroupsOnSignal()
  // A process group of its own, so the backstop kills each helper Git starts along with git.
  const child = Bun.spawn(["git", ...STALL_LIMITS, ...args], {
    cwd,
    env,
    stderr: "pipe",
    detached: true,
  })
  live.add(child.pid)
  void child.exited.then(() => live.delete(child.pid))
  // A timer of its own, so only its kill reads as the limit, never a signal from elsewhere. Its kill ends the wait even
  // where a process outside the group still holds a pipe.
  let timer: Timer | undefined
  const limit = new Promise<undefined>((resolve) => {
    timer = setTimeout(() => {
      killGroup(child.pid)
      resolve(undefined)
    }, backstop)
  })
  const output = Promise.all([
    new Response(child.stdout).bytes(),
    new Response(child.stderr).text(),
    child.exited,
  ])
  const ran = await Promise.race([output, limit]).finally(() => clearTimeout(timer))
  const command = `git ${args.join(" ")}`
  if (ran === undefined)
    throw new GitError(
      `${command} ran past its ${backstop / 1000} s limit; check the network and the remote, then rerun`,
      await child.exited,
    )
  const [out, err, code] = ran
  if (child.signalCode !== null)
    throw new GitError(`${command} was stopped by ${child.signalCode}; rerun it`, code)
  if (code !== 0) throw new GitError(`${command} exited ${code}: ${err.trim()}`, code)
  return out
}

function killGroupsOnSignal(): void {
  if (handling) return
  handling = true
  for (const signal of ["SIGINT", "SIGTERM"] as const)
    process.on(signal, () => {
      for (const pid of live) killGroup(pid)
      process.exit(128 + constants.signals[signal])
    })
}

export function killGroup(pid: number): void {
  try {
    process.kill(-pid, "SIGKILL")
  } catch (error) {
    // A group whose processes have all exited is already ended, which the system reports as ESRCH once they are
    // reaped, and on macOS as EPERM before.
    const code = (error as NodeJS.ErrnoException).code
    if (code !== "ESRCH" && code !== "EPERM") throw error
  }
}

function localEnvVars(env: Record<string, string | undefined>): string[] {
  const probe = Bun.spawnSync(["git", "rev-parse", "--local-env-vars"], { env })
  if (probe.exitCode !== 0)
    throw new Error(
      `git rev-parse --local-env-vars exited ${probe.exitCode}, so the hook's repository variables stay unknown; install a working Git, then rerun`,
    )
  return probe.stdout.toString().split("\n").filter(Boolean)
}
