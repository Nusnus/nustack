/**
 * The release script's commands on a clone of a local origin: run passes each its arguments, bump sets the version and
 * titles the changelog, bundle zips the committed plugin, tag pushes the version on the commit of main that set it once
 * checks pass, verify-tag holds a pushed tag to it, publish runs the gh on the PATH, and readPlugin refuses a broken
 * manifest.
 */
import { afterEach, describe, expect, setSystemTime, test } from "bun:test"
import {
  chmod,
  mkdir,
  readdir,
  readFile,
  realpath,
  rename,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises"
import { join } from "node:path"
import { GitError, git } from "../../../scripts/git.ts"
import { bump, bundle, readPlugin, run, tag, verifyTag } from "../../../scripts/release.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"
import { commit, LOCAL } from "../../fixtures/scripts/git.ts"

const folders = new TemporaryFolders()
afterEach(() => folders.clear())
const passes = async () => {}
const script = join(import.meta.dir, "../../../scripts/release.ts")
const fixture = join(import.meta.dir, "../../fixtures/scripts/git.ts")
const usage =
  "usage: bun scripts/release.ts bump [version] | notes [version] | bundle | tag | verify-tag <tag> | publish <tag> <commit>\n"
const changelog =
  "# Changelog\n\n## [Unreleased]\n\n### Added\n\n- New.\n\n[Unreleased]: https://h/o/n/compare/v0.0.1...HEAD\n"

// plugin/package.json at a version, as OpenCode loads it; a name other than n makes a change that keeps the version.
const pkg = (version: string, name = "n") =>
  JSON.stringify({ name, version, type: "module", exports: { ".": "./opencode.ts" } })

// A clone of a bare origin whose main holds a plugin at version 0.1.0 and a changelog with one unreleased change.
async function checkout(): Promise<string> {
  const [origin, root] = [await folders.make(), await folders.make()]
  await git(["init", "-q", "--bare", "--initial-branch=main", origin], origin)
  await git(["clone", "-q", origin, root], root, LOCAL)
  await mkdir(join(root, "plugin", ".claude-plugin"), { recursive: true })
  const manifest = {
    name: "n",
    version: "0.1.0",
    description: "d",
    author: { name: "a" },
    homepage: "https://h/o/n",
    repository: "https://h/o/n",
    license: "MIT",
  }
  await writeFile(join(root, "plugin/.claude-plugin/plugin.json"), JSON.stringify(manifest))
  await writeFile(join(root, "plugin/package.json"), pkg("0.1.0"))
  await writeFile(join(root, "CHANGELOG.md"), changelog)
  await writeFile(join(root, "README.md"), "# n\n\n### 1️⃣ Install\n\nI.\n\n### 2️⃣ Use\n\nU.\n")
  await commit(root)
  await git(["push", "-q", "origin", "main"], root, LOCAL)
  // tag reaches the manifest's repository, which Git finds at the bare origin.
  await git(["config", `url.file://${origin}.insteadOf`, "https://h/o/n.git"], root)
  // A child's $PWD and Git's paths resolve symlinks, such as macOS's /var to /private/var, so the tests compare paths
  // against the resolved folder.
  return realpath(root)
}

const origin = async (root: string) => (await git(["remote", "get-url", "origin"], root)).trim()
const head = async (root: string) => (await git(["rev-parse", "HEAD"], root)).trim()

async function push(root: string, file: string, content: string, message = "c"): Promise<string> {
  await writeFile(join(root, file), content)
  const made = await commit(root, message)
  await git(["push", "-q", "origin", "HEAD:main"], root, LOCAL)
  return made
}

// A folder holding one executable command, for a child Bun to find on its PATH.
async function command(name: string, body: string): Promise<string> {
  const bin = await folders.make()
  await writeFile(join(bin, name), `#!/bin/sh\n${body}`)
  await chmod(join(bin, name), 0o755)
  return bin
}

// A git that lets only fetch and ls-remote reach the local repository, which stands in for the plugin's.
const fileReads = () =>
  command(
    "git",
    `for arg do case "$arg" in fetch|ls-remote) export GIT_ALLOW_PROTOCOL=file; break ;; esac; done\nexec ${Bun.which("git")} "$@"\n`,
  )

// A child Bun that imports the Git fixture first, since Bun.spawn finds a command on the PATH this process started with.
function child(code: string, bin: string, path = `${bin}:${process.env.PATH}`) {
  const env = { ...process.env, PATH: path }
  const body = `import ${JSON.stringify(fixture)}; import * as release from ${JSON.stringify(script)}
try { console.log(await ${code}) } catch (error) { console.error(error.message); process.exitCode = 1 }`
  const ran = Bun.spawnSync([process.execPath, "-e", body], { env })
  return [ran.exitCode, ran.stdout.toString(), ran.stderr.toString()]
}

describe("run", () => {
  test("gives the notes of the plugin's version by default", async () => {
    const root = await checkout()
    await writeFile(
      join(root, "CHANGELOG.md"),
      changelog
        .replace("\n### Added", "\n## [0.1.0] - 2026-11-07\n\n### Added")
        .replace("\n[Unreleased]", "\n## [0.0.1] - 2026-11-01\n\n- First.\n\n[Unreleased]")
        .concat("[0.0.1]: https://h/o/n/releases/tag/v0.0.1\n"),
    )
    expect(await run(root, ["notes"])).toBe(
      "> **[n](https://h/o/n)** · d\n\n## 🆕 What's new\n\n### Added\n\n- New.\n\n## 🚀 Quick start\n\n### 1️⃣ Install\n\nI.\n\n### 2️⃣ Use\n\nU.\n\n**Full changelog:** [`v0.0.1...v0.1.0`](https://h/o/n/compare/v0.0.1...v0.1.0)",
    )
  })

  test.each(["bump", "notes", "bundle", "tag", "verify-tag", "publish"])(
    "prints the usage for %s --help, reading nothing",
    async (command) => {
      expect(await run(await folders.make(), [command, "--help"])).toBe(
        "usage: bun scripts/release.ts bump [version] | notes [version] | bundle | tag | verify-tag <tag> | publish <tag> <commit>",
      )
    },
  )

  test("passes each command its arguments", async () => {
    const root = await checkout()
    await expect(run(root, ["bump", "1.0"])).rejects.toThrow(
      "pass the version as <major>.<minor>.<patch>",
    )
    expect(await run(root, ["bundle"])).toBe("Built dist/nustack-0.1.0.zip")
    await expect(run(root, ["notes", "0.0.9"])).rejects.toThrow(
      "CHANGELOG.md has no ## [0.0.9] heading; add it",
    )
    await expect(run(root, ["notes"])).rejects.toThrow(
      "CHANGELOG.md has no ## [0.1.0] heading; add it",
    )
    await expect(run(root, ["verify-tag", "v0.2.0"])).rejects.toThrow(
      "v0.2.0 is not the plugin's version; push v0.1.0",
    )
    await git(["tag", "v0.1.0"], root)
    expect(await run(root, ["verify-tag", "v0.1.0"])).toBe(
      `v0.1.0 names the plugin's version, on main at ${await head(root)}`,
    )
    await expect(
      run(root, ["publish", "v0.1.0", "81c986c0e0a7c511f2941ed3cec09f7975687f80"]),
    ).rejects.toThrow("dist/ holds no notes.md; download the release artifact CI built, then rerun")
    await expect(
      run(root, ["publish", "81c986c0e0a7c511f2941ed3cec09f7975687f80", "v0.1.0"]),
    ).rejects.toThrow("pass the tag as v<major>.<minor>.<patch>")
  })

  test.each([
    ["bump", "pass the version as <major>.<minor>.<patch>"],
    ["notes", "pass the version as <major>.<minor>.<patch>"],
    ["verify-tag", "pass the tag as v<major>.<minor>.<patch>"],
  ])("refuses %s with an empty argument, naming its form", async (command, message) => {
    const root = await checkout()
    await expect(run(root, [command, ""])).rejects.toThrow(message)
    expect(await git(["status", "--porcelain"], root)).toBe("")
  })

  test.each(["CHANGELOG.md", "README.md"])(
    "refuses notes from a %s that is not UTF-8",
    async (file) => {
      const root = await checkout()
      const path = join(root, file)
      await writeFile(path, Buffer.concat([await readFile(path), Buffer.from([0xff])]))
      await expect(run(root, ["notes"])).rejects.toThrow(
        `${file}: is not valid UTF-8; save it as UTF-8, then rerun`,
      )
    },
  )

  test("prints its usage on --help", () => {
    const help = Bun.spawnSync([process.execPath, script, "--help"])
    expect([help.exitCode, help.stdout.toString()]).toEqual([0, usage])
  })

  test.each([
    [[]],
    [["title"]],
    [["toString"]],
    [["version"]],
    [["--help", "tag"]],
    [["bump", "0.2.0", "x"]],
    [["notes", "0.1.0", "x"]],
    [["bundle", "x"]],
    [["tag", "x"]],
    [["verify-tag"]],
    [["verify-tag", "v0.1.0", "x"]],
    [["publish", "v0.1.0"]],
    [["publish", "v0.1.0", "c", "x"]],
  ])("exits 1 with its usage on %j", (args) => {
    const release = Bun.spawnSync([process.execPath, script, ...args])
    expect([release.exitCode, release.stdout.toString(), release.stderr.toString()]).toEqual([
      1,
      "",
      usage,
    ])
  })
})

test("runs bump and tag through run, each refusing a working tree with changes", async () => {
  const root = await checkout()
  await writeFile(join(root, "README.md"), "changed\n")
  await expect(run(root, ["bump"])).rejects.toThrow(
    "the working tree has changes, which would ride into the release's commit",
  )
  await expect(run(root, ["tag"])).rejects.toThrow(
    "the working tree has changes, which the checks would read in place of the commit they tag",
  )
})

test("prints the notes of the repository it sits in, run from another folder", async () => {
  const ran = Bun.spawnSync([process.execPath, script, "notes"], { cwd: await folders.make() })
  expect([ran.exitCode, ran.stderr.toString()]).toEqual([0, ""])
  expect(ran.stdout.toString()).not.toBe("")
})

describe("bump", () => {
  const sets = (version: string) => async (root: string) =>
    writeFile(join(root, "plugin/package.json"), pkg(version))

  // A cz bump that would set 1.0.0, and records that it ran.
  const tracked = () => {
    const ran: string[] = []
    const setVersion = async (at: string) => {
      ran.push(at)
      await sets("1.0.0")(at)
    }
    return { ran, setVersion }
  }

  test("sets the next patch by default and titles the changelog with today's date in UTC", async () => {
    const root = await checkout()
    // Late on 7 November in New York is 8 November in UTC, so a bump dated by the machine's zone fails here.
    const zone = process.env.TZ
    process.env.TZ = "America/New_York"
    setSystemTime(new Date("2026-11-07T23:30:00-05:00"))
    const bumped = await bump(root, undefined, sets("0.1.1")).finally(() => {
      setSystemTime()
      if (zone === undefined) delete process.env.TZ
      else process.env.TZ = zone
    })
    expect(bumped).toBe("Set version 0.1.1 and titled [Unreleased] as [0.1.1] - 2026-11-08")
    expect(await readFile(join(root, "CHANGELOG.md"), "utf8")).toBe(
      "# Changelog\n\n## [Unreleased]\n\n## [0.1.1] - 2026-11-08\n\n### Added\n\n- New.\n\n[Unreleased]: https://h/o/n/compare/v0.1.1...HEAD\n[0.1.1]: https://h/o/n/releases/tag/v0.1.1\n",
    )
  })

  test("sets the next patch of a two-digit patch by default", async () => {
    const root = await checkout()
    const manifest = join(root, "plugin/.claude-plugin/plugin.json")
    await writeFile(manifest, (await readFile(manifest, "utf8")).replace("0.1.0", "0.1.19"))
    await writeFile(join(root, "plugin/package.json"), pkg("0.1.19"))
    await commit(root)
    const given: string[] = []
    const setVersion = async (at: string, version: string) => {
      given.push(version)
      await sets(version)(at)
    }
    await bump(root, undefined, setVersion)
    expect(given).toEqual(["0.1.20"])
  })

  test("runs cz bump with the version given, from the checkout", async () => {
    const root = await checkout()
    const log = join(await folders.make(), "log")
    const bin = await command(
      "uv",
      `echo "$PWD $*" > '${log}'\nprintf '{"name":"n","version":"1.0.0","type":"module","exports":{".":"./opencode.ts"}}' > plugin/package.json\n`,
    )
    const code = `release.bump(${JSON.stringify(root)}, "1.0.0")`
    // The child's clock is the machine's, so the in-process test above checks the date.
    const [exit, , errors] = child(code, bin)
    expect([exit, errors]).toEqual([0, ""])
    expect(await readFile(log, "utf8")).toBe(
      `${root} run cz bump --version-files-only --yes 1.0.0\n`,
    )
  })

  test("stops a cz bump that outlasts its time limit", async () => {
    const root = await checkout()
    const code = `release.czBump(${JSON.stringify(root)}, "1.0.0", 200)`
    expect(child(code, await command("uv", "exec sleep 30\n"))).toEqual([
      1,
      "",
      "cz bump took over 0.2 seconds; check what it waits on, such as its disk, then rerun\n",
    ])
  })

  test("stops when cz bump fails or leaves the version unset", async () => {
    const root = await checkout()
    const code = `release.bump(${JSON.stringify(root)})`
    expect(child(code, await command("uv", "exit 1\n"))).toEqual([
      1,
      "",
      "cz bump failed; fix the cause it printed, then rerun\n",
    ])
    // A cz bump that sets every version file but plugin/package.json, stages one, and leaves a file of its own.
    const partial = async (at: string) => {
      await writeFile(join(at, "README.md"), "set")
      await git(["add", "README.md"], at)
      await writeFile(join(at, "left.txt"), "x")
    }
    await expect(bump(root, undefined, partial)).rejects.toThrow(
      "cz bump left plugin/package.json off 0.1.1; list it in [tool.commitizen] version_files, then rerun",
    )
    expect(await git(["status", "--porcelain"], root)).toBe("")
  })

  test("restores HEAD when CHANGELOG.md cannot be written", async () => {
    const root = await checkout()
    const readOnly = async (at: string) => {
      await sets("0.1.1")(at)
      await chmod(join(at, "CHANGELOG.md"), 0o444)
    }
    await expect(bump(root, undefined, readOnly)).rejects.toThrow("EACCES")
    expect(await git(["status", "--porcelain"], root)).toBe("")
  })

  test("changes nothing when [Unreleased] lists no change", async () => {
    const root = await checkout()
    await writeFile(join(root, "CHANGELOG.md"), changelog.replace("### Added\n\n- New.\n", ""))
    await commit(root)
    const { ran, setVersion } = tracked()
    await expect(bump(root, undefined, setVersion)).rejects.toThrow(
      "CHANGELOG.md's [Unreleased] lists no change; merge the changes to release first",
    )
    expect(ran).toEqual([])
    expect(await git(["status", "--porcelain"], root)).toBe("")
  })

  test("changes nothing when the working tree has changes", async () => {
    const root = await checkout()
    await writeFile(join(root, "new.txt"), "x")
    const { ran, setVersion } = tracked()
    await expect(bump(root, undefined, setVersion)).rejects.toThrow(
      "the working tree has changes, which would ride into the release's commit; commit or stash them, then rerun",
    )
    expect(ran).toEqual([])
    expect(await git(["status", "--porcelain"], root)).toBe("?? new.txt\n")
  })

  test("changes nothing, keeping an untracked file, when the clone sets status.showUntrackedFiles to no", async () => {
    const root = await checkout()
    await git(["config", "status.showUntrackedFiles", "no"], root)
    await writeFile(join(root, "new.txt"), "x")
    const { ran, setVersion } = tracked()
    await expect(bump(root, undefined, setVersion)).rejects.toThrow(
      "the working tree has changes, which would ride into the release's commit; commit or stash them, then rerun",
    )
    expect(ran).toEqual([])
    expect(await readFile(join(root, "new.txt"), "utf8")).toBe("x")
  })

  test.each(["0.1.0", "0.0.5"])(
    "refuses the version %s, not above the plugin's 0.1.0",
    async (version) => {
      const root = await checkout()
      const { ran, setVersion } = tracked()
      await expect(bump(root, version, setVersion)).rejects.toThrow(
        "pass a version above 0.1.0, the plugin's version",
      )
      expect(ran).toEqual([])
    },
  )

  test("takes 0.10.0 as above the plugin's 0.9.0", async () => {
    const root = await checkout()
    await writeFile(join(root, "plugin/package.json"), pkg("0.9.0"))
    await commit(root)
    setSystemTime(new Date("2026-11-07T12:00:00Z"))
    const bumped = await bump(root, "0.10.0", sets("0.10.0")).finally(() => setSystemTime())
    expect(bumped).toBe("Set version 0.10.0 and titled [Unreleased] as [0.10.0] - 2026-11-07")
  })

  test("names the fix when uv is not on PATH", async () => {
    const root = await checkout()
    const bin = await folders.make()
    await symlink(`${Bun.which("git")}`, join(bin, "git"))
    expect(child(`release.bump(${JSON.stringify(root)})`, bin, bin)).toEqual([
      1,
      "",
      "uv is not on PATH; install uv, as https://docs.astral.sh/uv/getting-started/installation/ says, then rerun\n",
    ])
  })
})

describe("bundle", () => {
  const listed = async (root: string) => (await readdir(join(root, "dist"))).sort()
  // Each entry's MS-DOS date and time from its central directory header, which unzip -Z -T passes over for the UTC time
  // an extra field holds: https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT, 4.3.12, 4.3.16 and 4.4.6.
  const dosTimes = (zip: Uint8Array) => {
    const view = new DataView(zip.buffer, zip.byteOffset, zip.byteLength)
    let end = zip.byteLength - 22
    while (view.getUint32(end, true) !== 0x06054b50) end -= 1
    const two = (n: number) => String(n).padStart(2, "0")
    const times: string[] = []
    for (let at = view.getUint32(end + 16, true); view.getUint32(at, true) === 0x02014b50; ) {
      const [time, date] = [view.getUint16(at + 12, true), view.getUint16(at + 14, true)]
      times.push(
        `${1980 + (date >> 9)}-${two((date >> 5) & 15)}-${two(date & 31)} ${two(time >> 11)}:${two((time >> 5) & 63)}`,
      )
      at +=
        46 +
        view.getUint16(at + 28, true) +
        view.getUint16(at + 30, true) +
        view.getUint16(at + 32, true)
    }
    return times
  }
  // unzip -Z -T lists each entry's mode, version, host, size, kind, method, time and path.
  const entries = (zip: string) =>
    Bun.spawnSync(["unzip", "-Z", "-T", zip], { env: { ...process.env, TZ: "UTC" } }) // unzip shows times in its own zone
      .stdout.toString()
      .split("\n")
      .filter((line) => /^[-d]r/.test(line))
      .map((line) => {
        const fields = line.split(/\s+/)
        return `${fields[0]} ${fields.at(-2)} ${fields.at(-1)}`
      })
  // The system unzip reads each entry's mode by, the third field of unzip -Z.
  const hosts = (zip: string) => [
    ...new Set(
      Bun.spawnSync(["unzip", "-Z", zip])
        .stdout.toString()
        .split("\n")
        .filter((line) => /^[-d]r/.test(line))
        .map((line) => line.split(/\s+/)[2]),
    ),
  ]

  test("zips plugin/ as HEAD holds it, with each file's mode, the same on every run", async () => {
    const root = await checkout()
    await mkdir(join(root, "plugin/skills/a"), { recursive: true })
    await writeFile(join(root, "plugin/skills/a/SKILL.md"), "# A\n")
    await chmod(join(root, "plugin/skills/a/SKILL.md"), 0o755)
    await commit(root)
    await writeFile(join(root, "plugin/package.json"), pkg("9.9.9"))
    await writeFile(join(root, "plugin/uncommitted.txt"), "x")
    // A zone 14 hours from UTC, so a zip whose MS-DOS times follow the machine's zone fails here on any runner.
    const zone = process.env.TZ
    process.env.TZ = "Pacific/Kiritimati"
    try {
      expect(await bundle(root)).toBe("Built dist/nustack-0.1.0.zip")
      expect(process.env.TZ).toBe("Pacific/Kiritimati")
    } finally {
      if (zone === undefined) delete process.env.TZ
      else process.env.TZ = zone
    }
    const zip = join(root, "dist/nustack-0.1.0.zip")
    const first = await Bun.file(zip).bytes()
    expect(hosts(zip)).toEqual(["unx"])
    expect(entries(zip)).toEqual([
      "drwxr-xr-x 19800101.000000 .claude-plugin/",
      "-rw-r--r-- 19800101.000000 .claude-plugin/plugin.json",
      "-rw-r--r-- 19800101.000000 package.json",
      "drwxr-xr-x 19800101.000000 skills/",
      "drwxr-xr-x 19800101.000000 skills/a/",
      "-rwxr-xr-x 19800101.000000 skills/a/SKILL.md",
    ])
    expect(dosTimes(first)).toEqual(Array(6).fill("1980-01-01 00:00"))
    await bundle(root)
    expect(await Bun.file(zip).bytes()).toEqual(first)
  })

  test("zips each file's committed line endings when the clone sets core.autocrlf", async () => {
    const root = await checkout()
    await writeFile(join(root, "plugin/notes.md"), "a\nb\n")
    await commit(root)
    await git(["config", "core.autocrlf", "true"], root)
    await bundle(root)
    const zip = join(root, "dist/nustack-0.1.0.zip")
    expect(Bun.spawnSync(["unzip", "-p", zip, "notes.md"]).stdout.toString()).toBe("a\nb\n")
  })

  test("zips the same bytes from two commits that hold the same plugin/", async () => {
    const root = await checkout()
    await bundle(root)
    const zip = join(root, "dist/nustack-0.1.0.zip")
    const first = await Bun.file(zip).bytes()
    process.env.GIT_COMMITTER_DATE = "2030-06-07T08:09:10Z"
    await git(
      ["-c", "user.name=T", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "c"],
      root,
    ).finally(() => delete process.env.GIT_COMMITTER_DATE)
    await bundle(root)
    expect(await Bun.file(zip).bytes()).toEqual(first)
  })

  test("replaces an older zip once the new one is whole, and keeps it when the build fails", async () => {
    const root = await checkout()
    await mkdir(join(root, "dist"))
    await writeFile(join(root, "dist/nustack-0.0.9.zip"), "old")
    await writeFile(join(root, "dist/notes.md"), "page")
    const code = `release.bundle(${JSON.stringify(root)})`
    const real = Bun.which("git")
    const bin = await command(
      "git",
      `case " $* " in *" archive "*)\n  for arg; do [ "$out" = 1 ] && echo partial > "$arg"; [ "$arg" = -o ] && out=1 || out=; done\n  ls '${root}/dist' > '${root}/archiving'\n  exit 1\nesac\nexec '${real}' "$@"\n`,
    )
    expect(child(code, bin)[0]).toBe(1)
    // While git archive writes, the zip's own name stays free, so make smoke never unpacks a half-written zip.
    expect(await readFile(join(root, "archiving"), "utf8")).toBe(
      "notes.md\nnustack-0.0.9.zip\nnustack-0.1.0.zip.partial\n",
    )
    await rm(join(root, "archiving"))
    expect(await listed(root)).toEqual(["notes.md", "nustack-0.0.9.zip"])
    expect(await bundle(root)).toBe("Built dist/nustack-0.1.0.zip")
    expect(await listed(root)).toEqual(["notes.md", "nustack-0.1.0.zip"])
  })

  // Bundles under a git that reports the version given and is the machine's git for every other command.
  const bundleUnder = async (root: string, version: string) => {
    const bin = await folders.make()
    await writeFile(
      join(bin, "git"),
      `#!/bin/sh\ncase " $* " in *" --version "*) echo "git version ${version}"; exit 0 ;; esac\nexec ${Bun.which("git")} "$@"\n`,
    )
    await chmod(join(bin, "git"), 0o755)
    const code = `import { bundle } from ${JSON.stringify(script)}
await bundle(${JSON.stringify(root)}).then(console.log, (error) => console.log(error.message))`
    const child = Bun.spawnSync([process.execPath, "-e", code], {
      env: { ...process.env, PATH: `${bin}:${process.env.PATH}` },
    })
    return child.stdout.toString()
  }

  test.each(["2.39.5 (Apple Git-154)", "dev"])(
    "stops on git version %s, whose archive may not date the zip's entries, and builds no zip",
    async (version) => {
      const root = await checkout()
      expect(await bundleUnder(root, version)).toBe(
        "git archive dates the zip's entries only from Git 2.40.0 on; install Git 2.40.0 or later, then rerun\n",
      )
      expect(await listed(root)).toEqual([])
    },
  )

  test("builds the zip with Git 2.40.0, the first whose archive dates the entries", async () => {
    const root = await checkout()
    expect(await bundleUnder(root, "2.40.0")).toBe("Built dist/nustack-0.1.0.zip\n")
  })

  test("leaves TZ unset where it was unset", async () => {
    const root = await checkout()
    const zone = process.env.TZ
    delete process.env.TZ
    try {
      await bundle(root)
      expect(Object.hasOwn(process.env, "TZ")).toBe(false)
    } finally {
      if (zone !== undefined) process.env.TZ = zone
    }
  })

  test("keeps the older zip when the new one cannot take its name", async () => {
    const root = await checkout()
    await mkdir(join(root, "dist/nustack-0.1.0.zip"), { recursive: true })
    await writeFile(join(root, "dist/nustack-0.1.0.zip/x"), "")
    await writeFile(join(root, "dist/nustack-0.0.9.zip"), "old")
    await expect(bundle(root)).rejects.toThrow("rename")
    expect(await listed(root)).toEqual(["nustack-0.0.9.zip", "nustack-0.1.0.zip"])
  })

  test.each(['{"version":"1.0"}', '{"name":"n"}', "{"])(
    "stops on HEAD's package.json %s, building nothing",
    async (packageJson) => {
      const root = await checkout()
      await writeFile(join(root, "plugin/package.json"), packageJson)
      await commit(root)
      await expect(bundle(root)).rejects.toThrow(
        "plugin/package.json at HEAD holds no <major>.<minor>.<patch> version; commit one, then rerun",
      )
      await expect(readdir(join(root, "dist"))).rejects.toThrow("ENOENT")
    },
  )
})

describe("tag", () => {
  test("refuses a checkout whose version main does not hold yet, though main's is tagged", async () => {
    const root = await checkout()
    await tag(root, passes, "file")
    await writeFile(join(root, "plugin/package.json"), pkg("0.2.0"))
    await commit(root)
    await expect(tag(root, passes, "file")).rejects.toThrow(
      "main at https://h/o/n holds 0.1.0, below HEAD's 0.2.0; merge the release pull request, then rerun",
    )
  })

  test("pushes v<version> on main's head, which verify-tag accepts, and a rerun leaves it", async () => {
    const root = await checkout()
    const tagged = await head(root)
    expect(await tag(root, passes, "file")).toBe(
      `Pushed v0.1.0, on ${tagged}, which the clone has checked out detached`,
    )
    expect(await git(["ls-remote", "--tags", "origin"], root, LOCAL)).toBe(
      `${tagged}\trefs/tags/v0.1.0\n`,
    )
    await git(["fetch", "-q", "--tags", "origin"], root, LOCAL)
    expect(await verifyTag(root, "v0.1.0")).toBe(
      `v0.1.0 names the plugin's version, on main at ${tagged}`,
    )
    expect(await tag(root, passes, "file")).toBe(
      `https://h/o/n already holds v0.1.0 on ${tagged}; the release workflow publishes from it`,
    )
  })

  test("tags the commit that set the version once main moves on, from any checkout of the clone", async () => {
    const root = await checkout()
    await push(root, "plugin/package.json", pkg("0.1.0", "n1"))
    const release = await push(root, "plugin/package.json", pkg("0.2.0"), "release")
    await push(root, "next.txt", "x")
    await push(root, "plugin/package.json", pkg("0.2.0", "n2"))
    await git(["checkout", "-q", "--detach", "HEAD~3"], root)
    const ran: string[] = []
    const records = async (at: string) => void ran.push(await head(at))
    expect(await tag(root, records, "file")).toBe(
      `Pushed v0.2.0, on ${release}, which the clone has checked out detached`,
    )
    expect(ran).toEqual([release])
    expect(await git(["ls-remote", "--tags", "origin"], root, LOCAL)).toBe(
      `${release}\trefs/tags/v0.2.0\n`,
    )
  })

  test("tags the merge commit of a branch that set the version, not the branch's own commit", async () => {
    const root = await checkout()
    await git(["checkout", "-q", "-b", "release"], root)
    await writeFile(join(root, "plugin/package.json"), pkg("0.2.0"))
    await commit(root, "bump")
    await git(["checkout", "-q", "main"], root)
    const merged = [
      "-c",
      "user.name=T",
      "-c",
      "user.email=t@t",
      "merge",
      "-q",
      "--no-ff",
      "-m",
      "m",
      "release",
    ]
    await git(merged, root)
    await git(["push", "-q", "origin", "main"], root, LOCAL)
    const merge = await head(root)
    expect(await tag(root, passes, "file")).toBe(
      `Pushed v0.2.0, on ${merge}, which the clone has checked out detached`,
    )
  })

  test("takes the newest commit that set the version when an older one broke plugin/package.json", async () => {
    const root = await checkout()
    await push(root, "plugin/package.json", "{")
    const set = await push(root, "plugin/package.json", pkg("0.1.0"))
    expect(await tag(root, passes, "file")).toBe(
      `Pushed v0.1.0, on ${set}, which the clone has checked out detached`,
    )
  })

  test("stops on a commit whose plugin/package.json git cannot read, rather than tagging a later one", async () => {
    const root = await checkout()
    const blob = (await git(["rev-parse", "HEAD:plugin/package.json"], root)).trim()
    await push(root, "plugin/package.json", pkg("0.1.0", "m"))
    await rm(join(root, ".git/objects", blob.slice(0, 2), blob.slice(2)))
    await expect(tag(root, passes, "file")).rejects.toBeInstanceOf(GitError)
  })

  test("takes the commit that added plugin/package.json back after one removed it", async () => {
    const root = await checkout()
    await rm(join(root, "plugin/package.json"))
    await commit(root)
    await git(["push", "-q", "origin", "main"], root, LOCAL)
    const set = await push(root, "plugin/package.json", pkg("0.1.0"))
    expect(await tag(root, passes, "file")).toBe(
      `Pushed v0.1.0, on ${set}, which the clone has checked out detached`,
    )
  })

  test.each([
    ["the same version", "0.2.0"],
    ["another version", "0.3.0"],
  ])(
    "tags main's release commit though another fetch in the clone points FETCH_HEAD at a branch that sets %s",
    async (_, version) => {
      const root = await checkout()
      await git(["checkout", "-q", "-b", "side"], root)
      await writeFile(join(root, "plugin/package.json"), pkg(version, "s"))
      const side = await commit(root, "side")
      await git(["checkout", "-q", "main"], root)
      const release = await push(root, "plugin/package.json", pkg("0.2.0"), "release")
      // Another fetch in the clone, run as tag's own fetch ends, points FETCH_HEAD at the branch's commit.
      const bin = await command(
        "git",
        `case "$*" in *"fetch --no-tags"*) ${Bun.which("git")} "$@" || exit; echo ${side} > '${root}/.git/FETCH_HEAD'; exit 0 ;; esac\nexec ${Bun.which("git")} "$@"\n`,
      )
      expect(child(`release.tag(${JSON.stringify(root)}, async () => {}, "file")`, bin)).toEqual([
        0,
        `Pushed v0.2.0, on ${release}, which the clone has checked out detached\n`,
        "",
      ])
    },
  )

  test("fetches main from and pushes the tag to the manifest's https repository, not to origin", async () => {
    const root = await checkout()
    const repository = await origin(root)
    const decoy = await folders.make()
    await git(["init", "-q", "--bare", "--initial-branch=main", decoy], decoy)
    await git(["remote", "set-url", "origin", decoy], root)
    expect(await tag(root, passes, "file")).toBe(
      `Pushed v0.1.0, on ${await head(root)}, which the clone has checked out detached`,
    )
    expect(await git(["ls-remote", "--tags", repository], root, LOCAL)).toBe(
      `${await head(root)}\trefs/tags/v0.1.0\n`,
    )
    expect(await git(["ls-remote", decoy], root, LOCAL)).toBe("")
  })

  test("reaches the repository over https alone by default", async () => {
    const root = await checkout()
    await expect(tag(root, passes)).rejects.toThrow(
      "git fetch --no-tags https://h/o/n.git +main:refs/nustack/fetched-main exited 128: fatal: transport 'file' not allowed",
    )
    expect(await git(["ls-remote", "--tags", await origin(root)], root, LOCAL)).toBe("")
  })

  test("pushes the tag over https alone by default, though the fetch and ls-remote reached the repository", async () => {
    const root = await checkout()
    const [exit, , stderr] = child(
      `release.tag(${JSON.stringify(root)}, async () => {})`,
      await fileReads(),
    )
    expect([exit, stderr]).toEqual([
      1,
      expect.stringContaining(
        "exited 128: fatal: transport 'file' not allowed); fix that, then rerun",
      ),
    ])
    expect(await git(["ls-remote", "--tags", await origin(root)], root, LOCAL)).toBe("")
  })

  test("reads main as the repository holds it, not as the clone last fetched it", async () => {
    const root = await checkout()
    const other = await folders.make()
    await git(["clone", "-q", await origin(root), other], other, LOCAL)
    const release = await push(other, "plugin/package.json", pkg("0.2.0"))
    expect(await tag(root, passes, "file")).toBe(
      `Pushed v0.2.0, on ${release}, which the clone has checked out detached`,
    )
  })

  test("finds an annotated tag the repository holds on the commit", async () => {
    const root = await checkout()
    const annotated = [
      "-c",
      "user.name=T",
      "-c",
      "user.email=t@t",
      "tag",
      "-a",
      "-m",
      "t",
      "v0.1.0",
    ]
    await git(annotated, root)
    await git(["push", "-q", "origin", "refs/tags/v0.1.0"], root, LOCAL)
    expect(await tag(root, passes, "file")).toBe(
      `https://h/o/n already holds v0.1.0 on ${await head(root)}; the release workflow publishes from it`,
    )
  })

  test("names the fix when make is not on PATH, and pushes nothing", async () => {
    const root = await checkout()
    const bin = await folders.make()
    await symlink(`${Bun.which("git")}`, join(bin, "git"))
    expect(
      child(`release.tag(${JSON.stringify(root)}, release.makeChecks, "file")`, bin, bin),
    ).toEqual([
      1,
      "",
      "make is not on PATH; install make with your system package manager, then rerun\n",
    ])
    expect(await git(["ls-remote", "--tags", "origin"], root, LOCAL)).toBe("")
  })

  test("refuses a tag the repository holds on another commit", async () => {
    const root = await checkout()
    await git(["push", "-q", "origin", "HEAD:refs/tags/v0.2.0"], root, LOCAL)
    await push(root, "plugin/package.json", pkg("0.2.0"))
    await expect(tag(root, passes, "file")).rejects.toThrow(
      "https://h/o/n holds v0.2.0 on another commit; bump to the next version, then rerun",
    )
  })

  test("refuses changes and a shallow clone, and pushes nothing when the checks fail", async () => {
    const root = await checkout()
    await writeFile(join(root, "new.txt"), "x")
    await expect(tag(root, passes, "file")).rejects.toThrow(
      "the working tree has changes, which the checks would read in place of the commit they tag; commit or stash them, then rerun",
    )
    await rm(join(root, "new.txt"))
    const fails = () => Promise.reject(new Error("make check or smoke failed"))
    await expect(tag(root, fails, "file")).rejects.toThrow("make check or smoke failed")
    expect(await git(["ls-remote", "--tags", "origin"], root, LOCAL)).toBe("")
    await push(root, "next.txt", "x")
    const shallow = await folders.make()
    await git(["clone", "-q", "--depth=1", `file://${await origin(root)}`, shallow], shallow, LOCAL)
    await expect(tag(shallow, passes, "file")).rejects.toThrow(
      "the clone is shallow; run git fetch --unshallow origin, then rerun",
    )
  })

  test("names the tag a push failed to push, and a rerun pushes it", async () => {
    const root = await checkout()
    const hook = join(await origin(root), "hooks/pre-receive")
    await writeFile(hook, "#!/bin/sh\necho refused\nexit 1\n")
    await chmod(hook, 0o755)
    const failed = tag(root, passes, "file")
    await expect(failed).rejects.toThrow(
      /^v0\.1\.0 was not pushed to https:\/\/h\/o\/n \(git push /,
    )
    await expect(failed).rejects.toThrow(/remote: refused[\s\S]*; fix that, then rerun$/)
    await rm(hook)
    expect(await tag(root, passes, "file")).toBe(
      `Pushed v0.1.0, on ${await head(root)}, which the clone has checked out detached`,
    )
  })

  test("leaves the clone's refs as they were when the push fails, and once it succeeds", async () => {
    const root = await checkout()
    const refs = () => git(["for-each-ref"], root)
    const before = await refs()
    const hook = join(await origin(root), "hooks/pre-receive")
    await writeFile(hook, "#!/bin/sh\nexit 1\n")
    await chmod(hook, 0o755)
    await expect(tag(root, passes, "file")).rejects.toThrow("v0.1.0 was not pushed")
    expect(await refs()).toBe(before)
    await rm(hook)
    await tag(root, passes, "file")
    expect(await refs()).toBe(before)
  })

  test("rethrows an error at the push that is not Git's as it is", async () => {
    const root = await checkout()
    const aside = join(await folders.make(), "checkout")
    // A working tree moved away before the push leaves Bun no folder to start git in.
    const error = await tag(root, (at) => rename(at, aside), "file").catch((thrown) => thrown)
    await rename(aside, root)
    expect(error).toMatchObject({ code: "ENOENT" })
  })

  test("runs make check and make smoke on the commit it tags by default, and pushes nothing when they fail", async () => {
    const root = await checkout()
    const log = join(await folders.make(), "log")
    const bin = await command("make", `echo "$PWD $* $(git rev-parse HEAD)" > '${log}'\nexit 2\n`)
    const code = `release.run(${JSON.stringify(root)}, ["tag"])`
    const path = `${bin}:${await fileReads()}:${process.env.PATH}`
    expect(child(code, bin, path)).toEqual([
      1,
      "",
      "make check or smoke failed; fix it, then rerun\n",
    ])
    expect(await readFile(log, "utf8")).toBe(`${root} check smoke ${await head(root)}\n`)
    expect(await git(["ls-remote", "--tags", "origin"], root, LOCAL)).toBe("")
  })

  test("passes once make check and make smoke pass", async () => {
    const root = await checkout()
    const bin = await command("make", "exit 0\n")
    const [exit] = child(`release.makeChecks(${JSON.stringify(root)})`, bin)
    expect(exit).toBe(0)
  })
})

describe("verifyTag", () => {
  test("refuses a tag that is not the plugin's version, missing, or not on origin/main", async () => {
    const root = await checkout()
    await expect(verifyTag(root, "v0.2.0")).rejects.toThrow(
      "v0.2.0 is not the plugin's version; push v0.1.0",
    )
    await expect(verifyTag(root, "v0.1.0")).rejects.toThrow(
      "v0.1.0 is not in this clone; fetch the tags from origin, then rerun",
    )
    await git(["checkout", "-q", "--orphan", "side"], root)
    await commit(root, "side")
    await git(["tag", "v0.1.0"], root)
    await expect(verifyTag(root, "v0.1.0")).rejects.toThrow(
      "v0.1.0 is not on origin/main; tag a commit on main",
    )
    await git(["update-ref", "-d", "refs/remotes/origin/main"], root)
    await expect(verifyTag(root, "v0.1.0")).rejects.toThrow(
      /^git merge-base --is-ancestor [0-9a-f]{40} origin\/main exited 128: \S/,
    )
  })

  test("rethrows a failure to read the tag other than its absence", async () => {
    const root = await checkout()
    const bin = await command(
      "git",
      `case "$*" in *"rev-parse --verify refs/tags/"*) exit 2 ;; esac\nexec ${Bun.which("git")} "$@"\n`,
    )
    const [exit, , stderr] = child(`release.verifyTag(${JSON.stringify(root)}, "v0.1.0")`, bin)
    expect([exit, stderr]).toEqual([
      1,
      expect.stringContaining("git rev-parse --verify refs/tags/v0.1.0^{commit} exited 2"),
    ])
  })
})

describe("publish", () => {
  // A gh on the PATH that logs its arguments and replays, for each command publish runs, its reply in
  // tests/fixtures/github/: the tag's commit, a release GitHub does not hold, then create's, upload's and edit's success.
  async function replayingGh(log: string): Promise<string> {
    const bin = await command(
      "gh",
      `echo "$*" >> '${log}'\ncase "$1" in\n  api) key=api ;;\n  release) key=$2 ;;\nesac\ndir=$(dirname "$0")\ncat "$dir/$key.out"\ncat "$dir/$key.err" >&2\nexit "$(cat "$dir/$key.code")"\n`,
    )
    const replies = {
      api: "tag-commit/found.json",
      view: "release-state/missing.json",
      create: "release-create/created.json",
      upload: "upload/uploaded.json",
      edit: "release-edit/draft.json",
    }
    for (const [key, path] of Object.entries(replies)) {
      const { stdout, stderr, code } = await Bun.file(
        join(import.meta.dir, "../../fixtures/github", path),
      ).json()
      await writeFile(join(bin, `${key}.out`), stdout)
      await writeFile(join(bin, `${key}.err`), stderr)
      await writeFile(join(bin, `${key}.code`), String(code))
    }
    return bin
  }

  test("publishes through the gh on the PATH by default, passing each command its arguments", async () => {
    const root = await checkout()
    await mkdir(join(root, "dist"))
    await writeFile(join(root, "dist/nustack-0.1.0.zip"), "zip")
    await writeFile(join(root, "dist/notes.md"), "page")
    const log = join(await folders.make(), "log")
    const bin = await replayingGh(log)
    expect(
      child(
        `release.publish(${JSON.stringify(root)}, "v0.1.0", "81c986c0e0a7c511f2941ed3cec09f7975687f80")`,
        bin,
      ),
    ).toEqual([0, "Published v0.1.0\n", ""])
    expect(await readFile(log, "utf8")).toBe(
      [
        "api repos/{owner}/{repo}/commits/tags/v0.1.0 --jq .sha",
        "release view v0.1.0 --json isDraft --jq .isDraft",
        "release create v0.1.0 --draft --verify-tag --notes ",
        `release upload v0.1.0 ${root}/dist/nustack-0.1.0.zip --clobber`,
        "api repos/{owner}/{repo}/commits/tags/v0.1.0 --jq .sha",
        `release edit v0.1.0 --draft=false --title nustack 0.1.0 --notes-file ${root}/dist/notes.md --prerelease=false`,
        "",
      ].join("\n"),
    )
  })
})

describe("readPlugin", () => {
  test("names each manifest field make check refuses", async () => {
    const root = await checkout()
    const path = join(root, "plugin/.claude-plugin/plugin.json")
    const manifest = JSON.parse(await readFile(path, "utf8"))
    await writeFile(path, JSON.stringify({ ...manifest, name: 1, repository: "h/o/n" }))
    await expect(readPlugin(root)).rejects.toThrow(
      new Error(
        [
          "plugin/.claude-plugin/plugin.json: name is missing or malformed; set it in kebab case",
          "plugin/.claude-plugin/plugin.json: repository is missing or malformed; set it to https://<host>/<owner>/<name>",
        ].join("\n"),
      ),
    )
  })

  test("names a package.json make check refuses", async () => {
    const root = await checkout()
    await writeFile(join(root, "plugin/package.json"), pkg("1.0"))
    await expect(readPlugin(root)).rejects.toThrow(
      new Error(
        "plugin/package.json: version is missing or malformed; set it as <major>.<minor>.<patch>",
      ),
    )
  })

  test("names a manifest it cannot parse, and a missing package.json", async () => {
    const root = await checkout()
    await writeFile(join(root, "plugin/.claude-plugin/plugin.json"), "{")
    await rm(join(root, "plugin/package.json"))
    await expect(readPlugin(root)).rejects.toThrow(
      new Error(
        [
          "plugin/.claude-plugin/plugin.json: does not parse as its format; fix its syntax",
          "plugin/package.json: is missing; restore it",
        ].join("\n"),
      ),
    )
  })
})
