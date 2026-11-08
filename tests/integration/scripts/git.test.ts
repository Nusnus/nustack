/**
 * git runs Git with its stall limits, over HTTPS alone, under a backstop timeout, with no prompt and none of a hook's
 * repository variables, and fails naming the command, its exit code and what Git printed.
 */
import { afterEach, expect, spyOn, test } from "bun:test"
import { closeSync, openSync, readSync } from "node:fs"
import { chmod } from "node:fs/promises"
import { constants } from "node:os"
import { join } from "node:path"
import type { Subprocess } from "bun"
import { git, gitBytes, killGroup } from "../../../scripts/git.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"
import "../../fixtures/scripts/git.ts"

const folders = new TemporaryFolders()
afterEach(() => folders.clear())

// Gives the environment back each variable as it was, unset where it was unset.
function restoring(keys: readonly string[]): () => void {
  const saved = keys.map((key) => [key, process.env[key]] as const)
  return () => {
    for (const [key, value] of saved)
      if (value === undefined) delete process.env[key]
      else process.env[key] = value
  }
}

test("runs Git with its stall limits, no prompt and none of a hook's repository variables", async () => {
  const root = await folders.make()
  const restore = restoring(["GIT_INDEX_FILE", "GIT_TERMINAL_PROMPT"])
  // A machine may set no prompt itself, so the run is given one that would prompt.
  Object.assign(process.env, { GIT_INDEX_FILE: join(root, "index"), GIT_TERMINAL_PROMPT: "1" })
  const env = await git(["-c", "alias.env=!env", "env"], root).finally(restore)
  expect(env).toContain("GIT_TERMINAL_PROMPT=0\n")
  expect(env).not.toContain("GIT_INDEX_FILE=")
  expect(await git(["config", "http.lowSpeedLimit"], root)).toBe("1000\n")
  expect(await git(["config", "http.lowSpeedTime"], root)).toBe("30\n")
})

test("fails naming the command, its exit code and what Git printed", async () => {
  const root = await folders.make()
  const failure = git(["rev-parse", "HEAD"], root)
  await expect(failure).rejects.toThrow(/^git rev-parse HEAD exited 128: \S/)
  await expect(failure).rejects.toMatchObject({ name: "GitError", code: 128 })
})

test("sets each run's backstop at four minutes", async () => {
  const root = await folders.make()
  const timer = spyOn(globalThis, "setTimeout")
  await git(["--version"], root)
  const delays = timer.mock.calls.map(([, delay]) => delay)
  timer.mockRestore()
  expect(delays).toEqual([240_000])
})

test("reaches a remote over HTTPS alone, whatever the environment allows", async () => {
  const root = await folders.make()
  const restore = restoring(["GIT_ALLOW_PROTOCOL"])
  const reach = (allowed: string, url: string) => {
    process.env.GIT_ALLOW_PROTOCOL = allowed
    return git(["ls-remote", url], root).catch((error) => error.message)
  }
  // Nothing listens on port 1, so an HTTPS run Git allows fails only at the connection.
  const messages = [
    await reach("ssh:file", "ssh://h/o/n"),
    await reach("ssh:file", root),
    await reach("none", "https://127.0.0.1:1/o/n"),
  ]
  restore()
  expect(messages[0]).toContain("transport 'ssh' not allowed")
  expect(messages[1]).toContain("transport 'file' not allowed")
  expect(messages[2]).toContain("Failed to connect to 127.0.0.1 port 1")
})

// A run that lasts until it is stopped, and binds no port: Git waits on the alias's sleep, which holds none of its pipes.
const HANG = Object.freeze(["-c", "alias.hang=!exec sleep 10 >/dev/null 2>&1", "hang"])

test("names the limit a run passed, and the fix", async () => {
  const root = await folders.make()
  await expect(gitBytes(HANG, root, { backstop: 200 })).rejects.toThrow(
    new Error(
      `git ${HANG.join(" ")} ran past its 0.2 s limit; check the network and the remote, then rerun`,
    ),
  )
})

// This row and the next wait out their backstop by design, so their timeouts count it.
test(
  "returns at the limit when a remote accepts the connection and never answers",
  async () => {
    const root = await folders.make()
    const server = Bun.listen({ hostname: "127.0.0.1", port: 0, socket: { data() {} } })
    const url = `https://127.0.0.1:${server.port}/o/n`
    const started = performance.now()
    const ran = gitBytes(["ls-remote", url], root, { backstop: 1000 }).finally(() =>
      server.stop(true),
    )
    await expect(ran).rejects.toThrow(
      new Error(
        `git ls-remote ${url} ran past its 1 s limit; check the network and the remote, then rerun`,
      ),
    )
    // The server holds the connection until it stops, so a run that waits on git-remote-https never returns.
    expect(performance.now() - started).toBeLessThan(5000)
  },
  1000 + 5000,
)

test("fails when Git cannot list a hook's repository variables, rather than keeping them", async () => {
  const bin = await folders.make()
  await Bun.write(join(bin, "git"), "#!/bin/sh\nexit 3\n")
  await chmod(join(bin, "git"), 0o755)
  const script = `import { git } from ${JSON.stringify(join(import.meta.dir, "../../../scripts/git.ts"))}
await git(["status"], "/").catch((error) => console.log(error.message))`
  const run = Bun.spawn([process.execPath, "-e", script], {
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}` },
  })
  expect(await new Response(run.stdout).text()).toBe(
    "git rev-parse --local-env-vars exited 3, so the hook's repository variables stay unknown; install a working Git, then rerun\n",
  )
})

test(
  "ends at its backstop each process the run started, though one holds none of its pipes",
  async () => {
    const bin = await folders.make()
    const fifo = join(bin, "held")
    Bun.spawnSync(["mkfifo", fifo])
    // The fake git opens the FIFO, starts a process that holds it and none of the run's pipes, then waits without it.
    await Bun.write(
      join(bin, "git"),
      `#!/bin/sh\ncase "$*" in *--local-env-vars*) exit 0 ;; esac\nexec 3>"${fifo}"\nsleep 1000 </dev/null >/dev/null 2>&1 &\nexec sleep 1000 3>&-\n`,
    )
    await chmod(join(bin, "git"), 0o755)
    // cat reads the FIFO until its last writer, the process git started, ends.
    const held = Bun.spawn(["cat", fifo])
    const script = `import { gitBytes } from ${JSON.stringify(join(import.meta.dir, "../../../scripts/git.ts"))}
await gitBytes(["fetch"], "/", { backstop: 1000 }).catch((error) => console.log(error.message))`
    try {
      const run = Bun.spawn([process.execPath, "-e", script], {
        env: { ...process.env, PATH: `${bin}:${process.env.PATH}` },
      })
      expect(await new Response(run.stdout).text()).toBe(
        "git fetch ran past its 1 s limit; check the network and the remote, then rerun\n",
      )
      expect(await held.exited).toBe(0)
    } finally {
      // A run that leaves the process alive leaves cat waiting on it, which would hold the test run open.
      held.kill()
    }
  },
  1000 + 5000,
)

// The longest a row waits for the script to exit, and then for its sleep to be reaped.
const EXIT_MS = 5000
const REAP_MS = 5000

// The script kills each running Git's group and exits with the signal's code.
test.each(["SIGINT", "SIGTERM"] as const)(
  "kills each running Git's process group when the script gets %s",
  async (signal) => {
    const root = await folders.make()
    const pid = join(root, "pid")
    const alias = "alias.y=!echo $$ >pid.new && mv pid.new pid && exec sleep 60"
    const script = `import { gitBytes } from ${JSON.stringify(join(import.meta.dir, "../../../scripts/git.ts"))}
await gitBytes(["-c", ${JSON.stringify(alias)}, "y"], ${JSON.stringify(root)})`
    const run = Bun.spawn([process.execPath, "-e", script])
    while (!(await Bun.file(pid).exists())) await Bun.sleep(20)
    const sleep = Number(await Bun.file(pid).text())
    const started = performance.now()
    run.kill(signal)
    // Once its group ends, sleep waits for its new parent to reap it.
    const gone = async () => {
      for (
        const deadline = performance.now() + REAP_MS;
        performance.now() < deadline;
        await Bun.sleep(20)
      )
        try {
          process.kill(sleep, 0)
        } catch {
          return true
        }
      return false
    }
    try {
      expect(await Promise.race([run.exited, Bun.sleep(EXIT_MS)])).toBe(
        128 + constants.signals[signal],
      )
      expect(performance.now() - started).toBeLessThan(EXIT_MS)
      expect(await gone()).toBe(true)
    } finally {
      // A run that leaves sleep alive would hold it past the test run.
      try {
        process.kill(sleep, "SIGKILL")
      } catch {}
      run.kill("SIGKILL")
    }
  },
  EXIT_MS + REAP_MS + 5000,
)

test("names a signal from elsewhere as one, not as the limit", async () => {
  const root = await folders.make()
  const spawn = spyOn(Bun, "spawn")
  const ran = gitBytes(HANG, root)
  const child = spawn.mock.results[0]?.value as Subprocess
  spawn.mockRestore()
  child.kill("SIGTERM")
  await expect(ran).rejects.toThrow(
    new Error(`git ${HANG.join(" ")} was stopped by SIGTERM; rerun it`),
  )
})

test("kills a run's process group once it has exited, reaped or not", async () => {
  const reaped = Bun.spawn(["true"], { detached: true })
  await reaped.exited
  expect(() => killGroup(reaped.pid)).not.toThrow()
  const fifo = join(await folders.make(), "output")
  Bun.spawnSync(["mkfifo", fifo])
  const exited = Bun.spawn(["sh", "-c", 'exec >"$0"', fifo], { detached: true })
  // Reading the child's output to its end blocks the event loop until the child exits, which keeps Bun from reaping it.
  const output = openSync(fifo, "r")
  expect(readSync(output, Buffer.alloc(1))).toBe(0)
  closeSync(output)
  expect(() => killGroup(exited.pid)).not.toThrow()
  await exited.exited
})

test("reaches a local repository only when a run passes the file transport", async () => {
  const root = await folders.make()
  await git(["init", "-q", "--bare", "r.git"], root)
  expect(await git(["ls-remote", join(root, "r.git")], root, { transport: "file" })).toBe("")
})
