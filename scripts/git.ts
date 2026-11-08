/**
 * Runs Git for the scripts. Each run is bounded: Git reaches a remote only over HTTPS, whose stall limits stop a transfer
 * that stops moving, and a backstop timer stops any other wait, such as a connection that opens and never answers. The
 * timer ends git's whole process group, so a helper such as git-remote-https ends with it, and the run returns at the
 * timer even where a pipe stays open. Git never prompts, so a missing credential fails at once.
 */

import { constants } from "node:os"
import { requireTool } from "./command.ts"

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
// none of them, and the script ends each before it exits.
// The scripts run Git one call at a time, so the handler's snapshot holds every live group.
const live = new Set<number>()
let stopping = false
let interrupted = false

// SIGTERM first, since Git removes its lock files when a signal it can catch ends it, and SIGKILL cannot be caught
// (https://github.com/git/git/blob/v2.51.0/lockfile.h#L18-L25); then up to GRACE_MS for the whole group to end, then
// SIGKILL. Two seconds leaves a process room to clean up on a loaded machine.
export const GRACE_MS = 2000

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
  requireTool("git", "install Git")
  if (localKeys === undefined) {
    const args = ["rev-parse", "--local-env-vars"]
    const listed = Bun.spawnSync(["git", ...args], { env, timeout: backstop })
    if (listed.exitedDueToTimeout)
      throw new GitError(
        `git ${args.join(" ")} ran past its ${backstop / 1000} s limit; check what Git waits on, such as its disk, then rerun`,
        listed.exitCode ?? 1,
      )
    if (!listed.success) {
      const exit = listed.exitCode ?? listed.signalCode
      throw new GitError(
        `git ${args.join(" ")} exited ${exit}: ${listed.stderr.toString().trim()}`,
        listed.exitCode ?? 1,
      )
    }
    localKeys = Object.freeze(listed.stdout.toString().split("\n").filter(Boolean))
  }
  // A hook exports variables such as GIT_INDEX_FILE, which would point each run at the hook's repository.
  for (const key of localKeys) delete env[key]
  stopGroupsOnSignal()
  // A process group of its own, so the backstop ends each helper Git starts along with git.
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
  // Set once the limit passes; git can exit on its SIGTERM before the rest of its group ends.
  let ending: Promise<void> | undefined
  const limit = new Promise<undefined>((resolve) => {
    timer = setTimeout(() => {
      ending = endGroup(child.pid)
      void ending.then(() => resolve(undefined))
    }, backstop)
  })
  const output = Promise.all([
    new Response(child.stdout).bytes(),
    new Response(child.stderr).text(),
    child.exited,
  ])
  const ran = await Promise.race([output, limit]).finally(() => clearTimeout(timer))
  // The caller's signal ended this group, and its handler exits with the signal's code, so this run reports nothing.
  if (interrupted) await new Promise<never>(() => {})
  const command = `git ${args.join(" ")}`
  if (ran === undefined || ending !== undefined) {
    await ending
    throw new GitError(
      `${command} ran past its ${backstop / 1000} s limit; check the network and the remote, then rerun`,
      await child.exited,
    )
  }
  const [out, err, code] = ran
  if (child.signalCode !== null)
    throw new GitError(`${command} was stopped by ${child.signalCode}; rerun it`, code)
  if (code !== 0) throw new GitError(`${command} exited ${code}: ${err.trim()}`, code)
  return out
}

// A second signal during the grace gives each live group SIGKILL at once.
function stopGroupsOnSignal(): void {
  if (stopping) return
  stopping = true
  for (const signal of ["SIGINT", "SIGTERM"] as const)
    process.on(signal, () => {
      const code = 128 + constants.signals[signal]
      if (interrupted) {
        for (const pid of live) signalGroup(pid, "SIGKILL")
        process.exit(code)
      }
      interrupted = true
      void Promise.all([...live].map(endGroup)).then(() => process.exit(code))
    })
}

export async function endGroup(pid: number): Promise<void> {
  const deadline = performance.now() + GRACE_MS
  let alive = signalGroup(pid, "SIGTERM")
  while (alive && performance.now() < deadline) {
    await Bun.sleep(GRACE_MS / 10)
    alive = signalGroup(pid, 0)
  }
  if (alive) signalGroup(pid, "SIGKILL")
}

// Whether the group still had a process to signal.
function signalGroup(pid: number, signal: NodeJS.Signals | 0): boolean {
  try {
    process.kill(-pid, signal)
    return true
  } catch (error) {
    // A group whose processes have all exited is already ended, which the system reports as ESRCH once they are
    // reaped, and on macOS as EPERM before.
    const code = (error as NodeJS.ErrnoException).code
    if (code !== "ESRCH" && code !== "EPERM") throw error
    return false
  }
}
