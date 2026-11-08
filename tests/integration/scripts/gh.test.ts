/**
 * runGh runs the gh on the PATH, giving what it printed and its exit code, kills a gh that runs past its time limit,
 * naming the command and the limit, and names the fix when no gh is on the PATH.
 */
import { afterEach, expect, test } from "bun:test"
import { chmod } from "node:fs/promises"
import { join } from "node:path"
import { TemporaryFolders } from "../../fixtures/folders.ts"

const folders = new TemporaryFolders()
afterEach(() => folders.clear())

// Runs runGh in a Bun whose PATH finds the fake gh first, since a spawn reads the PATH Bun started with.
async function ranGh(
  bin: string,
  limit: number,
  args: readonly string[] = ["pr", "list"],
  path = `${bin}:${process.env.PATH}`,
): Promise<string> {
  const script = `import { runGh } from ${JSON.stringify(join(import.meta.dir, "../../../scripts/gh.ts"))}
await runGh(${JSON.stringify(args)}, ${limit}).then(
  (ran) => console.log(JSON.stringify(ran)),
  (error) => console.log(error.message),
)`
  const run = Bun.spawn([process.execPath, "-e", script], {
    env: { ...process.env, PATH: path },
  })
  return await new Response(run.stdout).text()
}

test("kills a gh that runs past its time limit and stops, naming the command", async () => {
  const bin = await folders.make()
  const fifo = join(bin, "held")
  Bun.spawnSync(["mkfifo", fifo])
  // Nothing ever writes the FIFO, so the fake gh blocks on opening it until it is killed.
  await Bun.write(join(bin, "gh"), `#!/bin/sh\nexec cat "${fifo}"\n`)
  await chmod(join(bin, "gh"), 0o755)
  const started = performance.now()
  expect(await ranGh(bin, 200)).toBe(
    "gh pr list took over 0.2 seconds; rerun once GitHub answers\n",
  )
  expect(performance.now() - started).toBeLessThan(5000)
})

// A fake gh that logs its arguments and replays the reply recorded in tests/fixtures/github/<path>: its output, its
// errors and its exit code.
async function replaying(path: string): Promise<[string, string]> {
  const bin = await folders.make()
  const { stdout, stderr, code } = await Bun.file(
    join(import.meta.dir, "../../fixtures/github", path),
  ).json()
  await Bun.write(join(bin, "out"), stdout)
  await Bun.write(join(bin, "err"), stderr)
  const log = join(bin, "log")
  await Bun.write(
    join(bin, "gh"),
    `#!/bin/sh\necho "$*" >> '${log}'\ncat '${bin}/out'\ncat '${bin}/err' >&2\nexit ${code}\n`,
  )
  await chmod(join(bin, "gh"), 0o755)
  return [bin, log]
}

test.each([
  ["tag-commit/found.json", ["api", "repos/{owner}/{repo}/commits/tags/v0.1.0", "--jq", ".sha"]],
  [
    "release-state/missing.json",
    ["release", "view", "v0.1.0", "--json", "isDraft", "--jq", ".isDraft"],
  ],
])(
  "gives what gh printed and its exit code when it ends within its limit, replaying %s",
  async (path, args) => {
    const [bin, log] = await replaying(path)
    const { stdout, stderr, code } = await Bun.file(
      join(import.meta.dir, "../../fixtures/github", path),
    ).json()
    expect(JSON.parse(await ranGh(bin, 5000, args))).toEqual({ code, stdout, stderr })
    expect(await Bun.file(log).text()).toBe(`${args.join(" ")}\n`)
  },
)
