/**
 * sync copies a record's skills from upstream through a real clone with no blob and no checkout, rewrites the record and
 * lists the changes, or proposes nothing when no copied file changes; list gives each record's branch and title;
 * proposed keeps a branch whose open pull request from this repository into the base already proposes the copy on the
 * base's head, resets it once upstream, the base or the copy moves or no such pull request is open, and stops when gh
 * fails or prints no list of pull requests.
 */
import { afterEach, expect, test } from "bun:test"
import { existsSync } from "node:fs"
import { chmod, mkdir, readdir, readFile, stat, symlink, writeFile } from "node:fs/promises"
import { dirname, join } from "node:path"
import type { Gh, GhResult } from "../../../scripts/gh.ts"
import { GitError, git } from "../../../scripts/git.ts"
import { blobOf } from "../../../scripts/record.ts"
import { cloneUpstream, list, proposed, run, sync } from "../../../scripts/sync.ts"
import { TemporaryFolders } from "../../fixtures/folders.ts"
import { AUTHOR, commit, LOCAL } from "../../fixtures/scripts/git.ts"

const folders = new TemporaryFolders()
afterEach(() => folders.clear())
const record = {
  upstream: "https://h/o/n",
  source: "skills",
  folder: "plugin/skills",
  skills: ["s"],
}
const blob = (text: string | Uint8Array) => blobOf(Buffer.from(text))
const script = join(import.meta.dir, "../../../scripts/sync.ts")

// An upstream repository holding the files, beside its bare copy at <upstream>.git, which a clone reads.
async function upstreamOf(
  files: Record<string, string | Uint8Array>,
  executables: readonly string[] = [],
): Promise<string> {
  const upstream = join(await folders.make(), "up")
  for (const [path, bytes] of Object.entries(files)) {
    await mkdir(dirname(join(upstream, path)), { recursive: true })
    await writeFile(join(upstream, path), bytes)
  }
  for (const path of executables) await chmod(join(upstream, path), 0o755)
  await git(["init", "-q", upstream], upstream)
  await commit(upstream)
  await git(["clone", "-q", "--bare", upstream, `${upstream}.git`], dirname(upstream), LOCAL)
  return upstream
}

// A repository holding each record in vendored/, staged, as list reads them from Git's index.
async function repositoryOf(records: Record<string, unknown>): Promise<string> {
  const root = await folders.make()
  await git(["init", "-q", root], root)
  await mkdir(join(root, "vendored"))
  for (const [name, text] of Object.entries(records))
    await writeFile(join(root, "vendored", name), `${JSON.stringify(text, null, 2)}\n`)
  await git(["add", "."], root)
  return root
}

// Clones upstream's bare copy in place of the record's https upstream, checking the clone fetches no blob up front and
// checks nothing out.
const clonerOf = (upstream: string) => async (url: string, into: string) => {
  expect(url).toBe("https://h/o/n")
  await cloneUpstream(`file://${upstream}`, into, LOCAL)
  expect(await git(["config", "remote.origin.url"], into)).toBe(`file://${upstream}.git\n`)
  expect(await git(["config", "remote.origin.partialclonefilter"], into)).toBe("blob:none\n")
  expect(await readdir(into)).toEqual([".git"])
}

test("copies each blob's bytes and mode under upstream's root LICENSE, drops what upstream dropped and lists the changes", async () => {
  const binary = new Uint8Array([0xff, 0xfe, 0x00, 0x80])
  // A checkout would turn the LF file into CRLF; the copy keeps the blob's bytes.
  const upstream = await upstreamOf({
    ".gitattributes": "*.md text eol=crlf\n",
    LICENSE: "MIT\n",
    "skills/s/SKILL.md": "new\n",
    "skills/s/A.bin": binary,
    "skills/s/nested/SKILL.md": "x\n",
    "skills/t/SKILL.md": "other\n",
    "skills/Not Kebab/SKILL.md": "x\n",
  })
  const head = (await git(["rev-parse", "HEAD"], upstream)).trim()
  const kept = { "s/LICENSE": blob("MIT\n"), "s/SKILL.md": blob("old") }
  const old = { ...record, commit: "a".repeat(40), files: { ...kept, "s/old.md": blob("old") } }
  const root = await repositoryOf({ "x.json": old })
  await mkdir(join(root, "plugin/skills/s"), { recursive: true })
  for (const [file, text] of [
    ["old.md", "old"],
    ["SKILL.md", "old"],
    ["LICENSE", "MIT\n"],
  ] as const)
    await writeFile(join(root, "plugin/skills/s", file), text)
  await git(["add", "."], root)
  const cloned = clonerOf(upstream)
  const publish = async () => {
    await commit(upstream)
    const branches = ["HEAD:refs/heads/master", "HEAD:refs/heads/main"]
    await git(["push", "-q", "--force", `${upstream}.git`, ...branches], upstream, LOCAL)
  }
  const out = join(await folders.make(), "body.md")
  expect(await run(root, ["sync", "vendored/x.json", out], cloned)).toBe(`Wrote ${out}`)
  const text = await readFile(out, "utf8")
  const copied = {
    "s/A.bin": blob(binary),
    "s/LICENSE": blob("MIT\n"),
    "s/SKILL.md": blob("new\n"),
    "s/nested/SKILL.md": blob("x\n"),
  }
  const written = JSON.parse(await readFile(join(root, "vendored/x.json"), "utf8"))
  expect(written).toEqual({ ...record, commit: head, files: copied })
  expect(Object.keys(written.files)).toEqual(Object.keys(copied))
  expect(await readFile(join(root, "plugin/skills/s/SKILL.md"), "utf8")).toBe("new\n")
  expect(new Uint8Array(await readFile(join(root, "plugin/skills/s/A.bin")))).toEqual(binary)
  expect(existsSync(join(root, "plugin/skills/s/old.md"))).toBe(false)
  expect(text).toContain(
    "- `s/SKILL.md`, changed\n- `s/A.bin`, added\n- `s/nested/SKILL.md`, added\n- `s/old.md`, removed\n",
  )
  await git(["add", "."], root)
  expect(await run(root, ["sync", "vendored/x.json", out], cloned)).toBe(
    `Wrote ${out}\nThe copy matches upstream, so the sync proposes nothing.`,
  )
  await writeFile(join(upstream, "skills/s/run.sh"), "#!/bin/sh\n")
  await chmod(join(upstream, "skills/s/run.sh"), 0o755)
  await publish()
  await sync(root, "vendored/x.json", cloned)
  expect(JSON.parse(await readFile(join(root, "vendored/x.json"), "utf8")).files).toEqual({
    ...copied,
    "s/run.sh": blob("#!/bin/sh\n"),
  })
  const modeOf = async (file: string) => (await stat(join(root, "plugin/skills/s", file))).mode
  expect([await modeOf("run.sh"), await modeOf("SKILL.md")].map((mode) => mode & 0o777)).toEqual([
    0o755, 0o644,
  ])
  await git(["add", "."], root)
  expect((await sync(root, "vendored/x.json", cloned)).proposes).toBe(false)
  await writeFile(join(upstream, "skills/s/a b.md"), "x")
  await publish()
  await expect(sync(root, "vendored/x.json", cloned)).rejects.toThrow(
    "skills/s upstream holds an entry no record can list; review it there",
  )
  await git(["rm", "-q", "skills/s/a b.md"], upstream)
  await symlink("SKILL.md", join(upstream, "skills/s/link.md"))
  await publish()
  await expect(sync(root, "vendored/x.json", cloned)).rejects.toThrow(
    "skills/s upstream holds an entry no record can list; review it there",
  )
  await writeFile(
    join(root, "vendored/x.json"),
    `${JSON.stringify({ ...old, skills: ["gone"], commit: null, files: {} }, null, 2)}\n`,
  )
  await expect(sync(root, "vendored/x.json", cloned)).rejects.toThrow(
    new Error("https://h/o/n holds no skills/gone/SKILL.md or no LICENSE; fix vendored/x.json"),
  )
})

// Git lists the skill's own LICENSE before upstream's root one under source A, and after it under source skills.
test.each(["A", "skills"])(
  "copies a skill's own LICENSE, with its mode, over upstream's root one under source %s",
  async (source) => {
    const files = {
      LICENSE: "root\n",
      [`${source}/s/LICENSE`]: "own\n",
      [`${source}/s/SKILL.md`]: "x\n",
    }
    const upstream = await upstreamOf(files, ["LICENSE"])
    const root = await repositoryOf({ "x.json": { ...record, source, commit: null, files: {} } })
    await sync(root, "vendored/x.json", clonerOf(upstream))
    const license = join(root, "plugin/skills/s/LICENSE")
    expect(await readFile(license, "utf8")).toBe("own\n")
    expect((await stat(license)).mode & 0o777).toBe(0o644)
  },
)

// Git lists upstream's root LICENSE before a skill's own files, so it comes before each file that sorts ahead of it.
test("lists a new copy's files in path order, in its record and its body, upstream's root LICENSE among them", async () => {
  const upstream = await upstreamOf({
    LICENSE: "MIT\n",
    "skills/s/AGENTS.md": "a\n",
    "skills/s/SKILL.md": "x\n",
  })
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  const { body } = await sync(root, "vendored/x.json", clonerOf(upstream))
  expect(body).toContain("- `s/AGENTS.md`, added\n- `s/LICENSE`, added\n- `s/SKILL.md`, added\n")
  const written = JSON.parse(await readFile(join(root, "vendored/x.json"), "utf8"))
  expect(Object.keys(written.files)).toEqual(["s/AGENTS.md", "s/LICENSE", "s/SKILL.md"])
})

test("rewrites a record edited by hand since its last sync, whose copy matches upstream", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const files = { "s/LICENSE": blob("MIT\n"), "s/SKILL.md": blob("x\n") }
  const head = (await git(["rev-parse", "HEAD"], upstream)).trim()
  const edited = { ...record, commit: head, files: { ...files, "s/SKILL.md": blob("edited\n") } }
  const root = await repositoryOf({ "x.json": edited })
  const skill = join(root, "plugin/skills/s")
  await mkdir(skill, { recursive: true })
  await writeFile(join(skill, "LICENSE"), "MIT\n")
  await writeFile(join(skill, "SKILL.md"), "x\n")
  await git(["add", "."], root)
  const { body, proposes } = await sync(root, "vendored/x.json", clonerOf(upstream))
  expect(proposes).toBe(true)
  expect(body).toContain(".\n\n- `vendored/x.json`, the record\n\nRead the copy")
  const written = JSON.parse(await readFile(join(root, "vendored/x.json"), "utf8"))
  expect(written).toEqual({ ...record, commit: head, files })
})

test("restores a copy edited by hand since its last sync, its mode included", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const files = { "s/LICENSE": blob("MIT\n"), "s/SKILL.md": blob("x\n") }
  const head = (await git(["rev-parse", "HEAD"], upstream)).trim()
  const root = await repositoryOf({ "x.json": { ...record, commit: head, files } })
  const skill = join(root, "plugin/skills/s")
  await mkdir(skill, { recursive: true })
  await writeFile(join(skill, "LICENSE"), "MIT\n")
  await writeFile(join(skill, "SKILL.md"), "edited\n")
  await chmod(join(skill, "LICENSE"), 0o755)
  await git(["add", "."], root)
  const before = await readFile(join(root, "vendored/x.json"), "utf8")
  const { body: text } = await sync(root, "vendored/x.json", clonerOf(upstream))
  expect(text).toContain(".\n\n- `s/LICENSE`, changed\n- `s/SKILL.md`, changed\n\nRead the copy")
  expect(text).not.toContain("the record")
  expect(await readFile(join(root, "vendored/x.json"), "utf8")).toBe(before)
  expect(await readFile(join(skill, "SKILL.md"), "utf8")).toBe("x\n")
  expect((await stat(join(skill, "LICENSE"))).mode & 0o777).toBe(0o644)
})

test("refuses a skill upstream holds with no LICENSE of its own and none at its root", async () => {
  const upstream = await upstreamOf({ "skills/s/SKILL.md": "x\n" })
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  await expect(sync(root, "vendored/x.json", clonerOf(upstream))).rejects.toThrow(
    new Error("https://h/o/n holds no skills/s/SKILL.md or no LICENSE; fix vendored/x.json"),
  )
})

test("takes upstream's new commit into the record when upstream's files hold and the copy differs", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const files = { "s/LICENSE": blob("MIT\n"), "s/SKILL.md": blob("x\n") }
  const old = (await git(["rev-parse", "HEAD"], upstream)).trim()
  // Upstream changes the skill and changes it back, so its files hold at a newer commit that touched them.
  await writeFile(join(upstream, "skills/s/SKILL.md"), "y\n")
  await commit(upstream)
  await writeFile(join(upstream, "skills/s/SKILL.md"), "x\n")
  const head = await commit(upstream)
  await git(["push", "-q", `${upstream}.git`, "HEAD"], upstream, LOCAL)
  const root = await repositoryOf({ "x.json": { ...record, commit: old, files } })
  const skill = join(root, "plugin/skills/s")
  await mkdir(skill, { recursive: true })
  await writeFile(join(skill, "LICENSE"), "MIT\n")
  await writeFile(join(skill, "SKILL.md"), "edited\n")
  await git(["add", "."], root)
  const { proposes } = await sync(root, "vendored/x.json", clonerOf(upstream))
  expect(proposes).toBe(true)
  const written = JSON.parse(await readFile(join(root, "vendored/x.json"), "utf8"))
  expect(written).toEqual({ ...record, commit: head, files })
})

test("takes upstream's merge commit into the record, not the commit of the branch it merged that changed the copy", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  await git(["checkout", "-q", "-b", "side"], upstream)
  await writeFile(join(upstream, "skills/s/SKILL.md"), "y\n")
  await commit(upstream)
  await git(["checkout", "-q", "-"], upstream)
  const merged = [...AUTHOR, "merge", "-q", "--no-ff", "-m", "m", "side"]
  await git(merged, upstream)
  const merge = (await git(["rev-parse", "HEAD"], upstream)).trim()
  await git(["push", "-q", `${upstream}.git`, "HEAD"], upstream, LOCAL)
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  await sync(root, "vendored/x.json", clonerOf(upstream))
  expect(JSON.parse(await readFile(join(root, "vendored/x.json"), "utf8")).commit).toBe(merge)
})

test("removes its clone of upstream after a sync that succeeds and one that throws", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  const unlicensed = await upstreamOf({ "skills/s/SKILL.md": "x\n" })
  const other = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  const temporary = await folders.make()
  const saved = process.env.TMPDIR
  process.env.TMPDIR = temporary
  try {
    await sync(root, "vendored/x.json", clonerOf(upstream))
    await expect(sync(other, "vendored/x.json", clonerOf(unlicensed))).rejects.toThrow()
  } finally {
    if (saved === undefined) delete process.env.TMPDIR
    else process.env.TMPDIR = saved
  }
  expect(await readdir(temporary)).toEqual([])
})

test("moves the record's commit to upstream's commit that changes the root LICENSE a skill borrows", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  await sync(root, "vendored/x.json", clonerOf(upstream))
  await git(["add", "."], root)
  await writeFile(join(upstream, "LICENSE"), "MIT, 2026\n")
  const licensed = await commit(upstream)
  await git(["push", "-q", `${upstream}.git`, "HEAD"], upstream, LOCAL)
  expect((await sync(root, "vendored/x.json", clonerOf(upstream))).proposes).toBe(true)
  expect(JSON.parse(await readFile(join(root, "vendored/x.json"), "utf8")).commit).toBe(licensed)
})

test("clones over HTTPS alone by default, refusing a file:// upstream", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const into = await folders.make()
  await expect(cloneUpstream(`file://${upstream}`, into)).rejects.toThrow(
    /transport 'file' not allowed/,
  )
})

test("refuses a skill whose upstream folder holds a submodule, which no record can list", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const head = (await git(["rev-parse", "HEAD"], upstream)).trim()
  await git(["update-index", "--add", "--cacheinfo", `160000,${head},skills/s/sub`], upstream)
  await git([...AUTHOR, "commit", "-qm", "sub"], upstream)
  await git(["push", "-q", `${upstream}.git`, "HEAD"], upstream, LOCAL)
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  await expect(sync(root, "vendored/x.json", clonerOf(upstream))).rejects.toThrow(
    new Error("skills/s upstream holds an entry no record can list; review it there"),
  )
})

test("proposes nothing for a copy that matches upstream, naming no skill when upstream holds no other", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const files = { "s/LICENSE": blob("MIT\n"), "s/SKILL.md": blob("x\n") }
  const head = (await git(["rev-parse", "HEAD"], upstream)).trim()
  const root = await repositoryOf({ "x.json": { ...record, commit: head, files } })
  const skill = join(root, "plugin/skills/s")
  await mkdir(skill, { recursive: true })
  await writeFile(join(skill, "LICENSE"), "MIT\n")
  await writeFile(join(skill, "SKILL.md"), "x\n")
  await git(["add", "."], root)
  const out = join(root, "body.md")
  expect(await run(root, ["sync", "vendored/x.json", out], clonerOf(upstream))).toBe(
    `Wrote ${out}\nThe copy matches upstream, so the sync proposes nothing.`,
  )
})

test("reads an upstream source that starts with a dash as a folder, not an option", async () => {
  const upstream = await upstreamOf({
    LICENSE: "MIT\n",
    "-x/s/SKILL.md": "x\n",
    "-x/s/nested/a.md": "a\n",
    "-x/t/SKILL.md": "t\n",
  })
  const root = await repositoryOf({
    "x.json": { ...record, source: "-x", commit: null, files: {} },
  })
  await sync(root, "vendored/x.json", clonerOf(upstream))
  expect(JSON.parse(await readFile(join(root, "vendored/x.json"), "utf8")).files).toEqual({
    "s/LICENSE": blob("MIT\n"),
    "s/SKILL.md": blob("x\n"),
    "s/nested/a.md": blob("a\n"),
  })
  await git(["add", "."], root)
  expect((await sync(root, "vendored/x.json", clonerOf(upstream))).proposes).toBe(false)
})

test("stops on a pull request body longer than GitHub's 65,536 characters, writing no body, copy or record", async () => {
  // Long names push the body past the limit with few files, which keeps the upstream's setup short.
  const name = (n: number) => `${"a-long-kebab-file-name-".repeat(8)}padding-${n}.md`
  const many = Object.fromEntries(
    Array.from({ length: 320 }, (_, n) => [`skills/s/${name(n)}`, `${n}\n`]),
  )
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n", ...many })
  const old = { ...record, commit: null, files: {} }
  const root = await repositoryOf({ "x.json": old })
  const out = join(await folders.make(), "body.md")
  await expect(run(root, ["sync", "vendored/x.json", out], clonerOf(upstream))).rejects.toThrow(
    "vendored/x.json: its sync's pull request body for plugin/skills runs past GitHub's 65,536 characters; split its skills across records, then rerun",
  )
  expect(existsSync(out)).toBe(false)
  expect(existsSync(join(root, "plugin/skills/s"))).toBe(false)
  expect(JSON.parse(await readFile(join(root, "vendored/x.json"), "utf8"))).toEqual(old)
})

test("refuses a file under a root LICENSE folder, which no record can list", async () => {
  const upstream = await upstreamOf({
    "LICENSE/MIT": "MIT\n",
    "skills/s/LICENSE": "MIT\n",
    "skills/s/SKILL.md": "x\n",
  })
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  await expect(sync(root, "vendored/x.json", clonerOf(upstream))).rejects.toThrow(
    new Error("skills/s upstream holds an entry no record can list; review it there"),
  )
})

test("links upstream's commits since the recorded one from the body", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const head = (await git(["rev-parse", "HEAD"], upstream)).trim()
  const github = {
    ...record,
    upstream: "https://github.com/o/n",
    commit: "a".repeat(40),
    files: { "s/LICENSE": blob("MIT\n"), "s/SKILL.md": blob("x\n") },
  }
  const root = await repositoryOf({ "x.json": github })
  const cloned = (_url: string, into: string) => cloneUpstream(`file://${upstream}`, into, LOCAL)
  const { body } = await sync(root, "vendored/x.json", cloned)
  expect(body).toContain(
    `\nUpstream's commits since the last sync: https://github.com/o/n/compare/${"a".repeat(40)}...${head}\n`,
  )
})

test("refuses a copy whose index entry it cannot read", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  // A Git that lists the index in a form the sync does not know, and runs every other command itself.
  const bin = await folders.make()
  const real = Bun.which("git")
  await writeFile(
    join(bin, "git"),
    `#!/bin/sh\ncase " $* " in *" ls-files "*) printf 'unknown\\0'; exit 0;; esac\nexec '${real}' "$@"\n`,
  )
  await chmod(join(bin, "git"), 0o755)
  const restore = process.env.PATH
  process.env.PATH = `${bin}:${restore}`
  const ran = sync(root, "vendored/x.json", clonerOf(upstream)).finally(() => {
    process.env.PATH = restore
  })
  await expect(ran).rejects.toThrow(
    new Error("plugin/skills: holds an index entry the sync cannot read; rerun git add on it"),
  )
})

test("refuses a broken record with every problem it has", async () => {
  const root = await repositoryOf({ "x.json": { ...record, upstream: "http://h/o/n", skills: [] } })
  const problems = [
    "vendored/x.json: is not a record; make sure it holds exactly upstream, source, folder, skills, commit and files",
    "vendored/x.json: is not a record; make sure upstream is https://<host>/<owner>/<name>",
    "vendored/x.json: is not a record; make sure skills lists distinct skill names in kebab case",
    "vendored/x.json: is not a record; make sure commit is null or a full commit SHA",
    "vendored/x.json: is not a record; make sure files maps each file, under one of its skills, to its Git blob",
  ].join("\n")
  await expect(sync(root, "vendored/x.json")).rejects.toThrow(new Error(problems))
  await expect(list(root)).rejects.toThrow(new Error(problems))
})

test.each([
  ["vendored/gone.json", "vendored/gone.json: is missing; restore it"],
  ["vendored/folder.json", "vendored/folder.json: is missing; restore it"],
  ["vendored/link.json", "vendored/link.json: is a symlink; put the file itself there"],
  ["vendored/sub/x.json", "vendored/sub/x.json: is not named <copy>.json in kebab case; rename it"],
  ["x.json", "x.json: is not named <copy>.json in kebab case; rename it"],
])("refuses the record %s", async (path, problem) => {
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  await symlink("x.json", join(root, "vendored/link.json"))
  await mkdir(join(root, "vendored/sub"))
  await mkdir(join(root, "vendored/folder.json"))
  await writeFile(join(root, "vendored/sub/x.json"), "{}")
  await writeFile(join(root, "x.json"), "{}")
  const clone = () => Promise.reject(new Error("the sync cloned upstream"))
  await expect(sync(root, path, clone)).rejects.toThrow(new Error(problem))
})

test("names the record whose upstream does not clone, beside what Git printed", async () => {
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  const missingUpstream = (_: string, into: string) =>
    cloneUpstream("file:///nonexistent", into, LOCAL)
  await expect(sync(root, "vendored/x.json", missingUpstream)).rejects.toThrow(
    /^vendored\/x\.json: its upstream did not clone; check that it exists and is public, then rerun\. git clone .+ exited 128: \S/,
  )
})

test("lists the records of the repository it sits in, run from another folder", async () => {
  const ran = Bun.spawnSync([process.execPath, script, "list"], { cwd: await folders.make() })
  expect([ran.exitCode, ran.stderr.toString()]).toEqual([0, ""])
  expect(JSON.parse(ran.stdout.toString())).not.toEqual([])
})

test("loads no plugin code", () => {
  // A child Bun lists each module it loaded, so any import of plugin code, however deep or caught, shows.
  const script = `await import(${JSON.stringify(join(import.meta.dir, "../../../scripts/sync.ts"))})
console.log(JSON.stringify(Object.keys(require.cache)))`
  const child = Bun.spawnSync([process.execPath, "-e", script])
  const plugin = join(import.meta.dir, "../../../plugin/")
  const loaded: string[] = JSON.parse(child.stdout.toString())
  expect(loaded.filter((path) => path.startsWith(plugin))).toEqual([])
  expect(loaded).toContain(join(import.meta.dir, "../../../scripts/sync.ts"))
})

test("refuses to list no record", async () => {
  await expect(list(await repositoryOf({}))).rejects.toThrow(
    new Error("vendored/: holds no record to sync; add one, as AGENTS.md › Where things live says"),
  )
})

test("prints a failing command's problem and exits 1, with no stack trace", () => {
  const failed = Bun.spawnSync([process.execPath, script, "sync", "vendored/gone.json", "body.md"])
  expect([failed.exitCode, failed.stdout.toString(), failed.stderr.toString()]).toEqual([
    1,
    "",
    "vendored/gone.json: is missing; restore it\n",
  ])
})

test("lists each record's branch, titling a copy in plugin/ feat and any other docs", async () => {
  const copy = { ...record, commit: null, files: {} }
  const root = await repositoryOf({
    "a.json": copy,
    "b.json": { ...copy, folder: ".agents/skills" },
  })
  expect(await run(root, ["list"])).toBe(await list(root))
  expect(JSON.parse(await list(root))).toEqual([
    {
      record: "vendored/a.json",
      branch: "sync/a",
      title: "feat: sync vendored/a.json from https://h/o/n",
    },
    {
      record: "vendored/b.json",
      branch: "sync/b",
      title: "docs: sync vendored/b.json from https://h/o/n",
    },
  ])
})

test.each([[["--help"]], [["list", "--help"]], [["sync", "--help"]]])(
  "prints its usage on %j",
  (args) => {
    const help = Bun.spawnSync([process.execPath, script, ...args])
    expect([help.exitCode, help.stdout.toString()]).toEqual([
      0,
      "usage: bun scripts/sync.ts list | sync <record> <body-file> | proposed <record> <branch> <base> <body-file>\n",
    ])
  },
)

test.each([
  [["pull"]],
  [["sync", "vendored/x.json"]],
  [["sync", "vendored/x.json", "body.md", "extra"]],
  [["proposed", "vendored/x.json", "sync/x", "main", "body.md", "extra"]],
  [["--help", "list"]],
  [["list", "--help", "extra"]],
  [["list", "extra"]],
  [[]],
])("exits 1 with its usage on %j", (args) => {
  const sync = Bun.spawnSync([process.execPath, script, ...args])
  expect([sync.exitCode, sync.stderr.toString()]).toEqual([
    1,
    "usage: bun scripts/sync.ts list | sync <record> <body-file> | proposed <record> <branch> <base> <body-file>\n",
  ])
})

// A base's bare repository whose sync/x branch proposes upstream's copy, with a reviewer's commit on top that adds a
// changelog entry and makes the edits given.
async function reviewed(upstream: string, edits: Record<string, string> = {}): Promise<string> {
  const base = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  await commit(base)
  const origin = join(await folders.make(), "origin.git")
  await git(["clone", "-q", "--bare", base, origin], base, LOCAL)
  const work = await folders.make()
  await git(["clone", "-q", origin, work], work, LOCAL)
  await git(["checkout", "-q", "-b", "sync/x"], work)
  await sync(work, "vendored/x.json", clonerOf(upstream))
  await commit(work)
  await writeFile(join(work, "CHANGELOG.md"), "- The reviewer's entry.\n")
  for (const [path, text] of Object.entries(edits)) await writeFile(join(work, path), text)
  await commit(work)
  await git(["push", "-q", "origin", "sync/x"], work, LOCAL)
  return origin
}

const GITHUB = join(import.meta.dir, "../../fixtures/github")
const reply = (path: string): Promise<GhResult> => Bun.file(join(GITHUB, path)).json()

// gh 2.x's replies about Nusnus-Private/nustack's pull request #143. pr-view/body.json and pr-view/title.json are
// `gh pr view 143 --json body` and `--json title` as gh prints them, {"<field>":<value>} and a newline, built from what
// `gh api repos/Nusnus-Private/nustack/pulls/143 --jq .body` and `--jq '{title}'` printed; pr-edit/143.json is
// `gh pr edit 143 --body-file body.md`'s, run with the body it held.
const VIEWED = await reply("pr-view/body.json")
// #143's body, closing on no newline, as GitHub keeps a body.
const HELD: string = JSON.parse(VIEWED.stdout).body
const viewing = (body: string): GhResult => ({ ...VIEWED, stdout: `${JSON.stringify({ body })}\n` })

// A gh that answers the open pull requests from the branch into main with a reply recorded in
// tests/fixtures/github/open-prs/, `gh pr view <n> --json body` with the reply given, holding HELD unless another, and
// `gh pr edit <n> --body-file <file>` with pr-edit/143.json's, adding each number it edits and the file's text to edits;
// it fails on any other command. Each reply is gh 2.x's to `gh pr list --repo
// <repository> --head <branch> --base <base> --state open --json isCrossRepository,number`: same-repo.json from
// Nusnus-Private/nustack's devin/1794046854-harness-rewrite into main, which one of its own pull requests proposes;
// other-base.json from Nusnus-Private/nustack's devin/1794046898-test-bar into main, whose only pull request targets
// another branch; none.json from Nusnus-Private/nustack's sync/none-open into main, which none comes from; fork.json from
// cli/cli's release-download-verify into its default branch, trunk, which only a fork's pull request comes from.
const ghOf =
  (
    branch: string,
    listed: "same-repo" | "other-base" | "none" | "fork",
    viewed: GhResult = viewing(HELD),
    edits: string[] = [],
  ): Gh =>
  async (args) => {
    const command = args.join(" ")
    if (
      command ===
      `pr list --head ${branch} --base main --state open --json isCrossRepository,number`
    )
      return reply(`open-prs/${listed}.json`)
    const [, verb, number, file] =
      /^pr (view|edit) (\d+) (?:--json body|--body-file (.+))$/.exec(command) ?? []
    if (verb === "view") return viewed
    if (verb === "edit" && number !== undefined && file !== undefined) {
      edits.push(`${number}: ${await readFile(file, "utf8")}`)
      return reply("pr-edit/143.json")
    }
    return { code: 1, stdout: "", stderr: `no reply to gh ${command}` }
  }

// What proposed writes to $GITHUB_OUTPUT from a clone of the base, which holds every branch, once sync has run in it,
// asking the gh given which pull requests are open from the branch, then the message it stops with, if it stops.
async function proposedOutput(
  origin: string,
  upstream: string,
  branch = "sync/x",
  gh = ghOf(branch, "same-repo"),
  written = HELD,
): Promise<string> {
  const root = await folders.make()
  await git(["clone", "-q", origin, root], root, LOCAL)
  await sync(root, "vendored/x.json", clonerOf(upstream))
  const output = join(await folders.make(), "output")
  // An earlier step's line, which proposed adds to rather than replaces.
  const earlier = "earlier=step\n"
  await writeFile(output, earlier)
  const bodyFile = join(await folders.make(), "body.md")
  await writeFile(bodyFile, written)
  process.env.GITHUB_OUTPUT = output
  const stopped = await run(
    root,
    ["proposed", "vendored/x.json", branch, "main", bodyFile],
    undefined,
    gh,
  ).then(
    () => "",
    (error: Error) => `stopped: ${error.message}`,
  )
  delete process.env.GITHUB_OUTPUT
  const text = await readFile(output, "utf8")
  expect(text).toStartWith(earlier)
  return text.slice(earlier.length) + stopped
}

test("keeps a branch, with the reviewer's commit, that proposes this copy on the base's head", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  expect(await proposedOutput(await reviewed(upstream), upstream)).toBe("proposed=true\n")
})

test.each([
  ["the body the sync writes", HELD, HELD, false],
  ["that body with a closing newline", HELD, `${HELD}\n`, false],
  ["another body", HELD, `${HELD}\n\n- Another file.`, true],
] as const)(
  "gives a kept pull request the sync's body only when it differs, as for %s",
  async (_written, held, written, edited) => {
    const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
    const edits: string[] = []
    const gh = ghOf("sync/x", "same-repo", viewing(held), edits)
    expect(await proposedOutput(await reviewed(upstream), upstream, "sync/x", gh, written)).toBe(
      "proposed=true\n",
    )
    expect(edits).toEqual(edited ? [`139: ${written}`] : [])
  },
)

test("stops when gh prints no pull request body, writing no proposed=true", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const titled = ghOf("sync/x", "same-repo", await reply("pr-view/title.json"))
  expect(await proposedOutput(await reviewed(upstream), upstream, "sync/x", titled)).toBe(
    "stopped: gh pr view 139 --json body printed no pull request body; update gh, then rerun",
  )
})

test("resets the branch once upstream moves", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const origin = await reviewed(upstream)
  await writeFile(join(upstream, "skills/s/SKILL.md"), "y\n")
  await commit(upstream)
  await git(["push", "-q", `${upstream}.git`, "HEAD"], upstream, LOCAL)
  expect(await proposedOutput(origin, upstream)).toBe("")
})

test("keeps the branch through an upstream commit that touches no copied file", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const origin = await reviewed(upstream)
  await writeFile(join(upstream, "README.md"), "r\n")
  await commit(upstream)
  await git(["push", "-q", `${upstream}.git`, "HEAD"], upstream, LOCAL)
  expect(await proposedOutput(origin, upstream)).toBe("proposed=true\n")
})

test("keeps the branch through a change to a root LICENSE no skill borrows", async () => {
  const upstream = await upstreamOf({
    LICENSE: "MIT\n",
    "skills/s/LICENSE": "Apache\n",
    "skills/s/SKILL.md": "x\n",
  })
  const origin = await reviewed(upstream)
  await writeFile(join(upstream, "LICENSE"), "MIT, 2026\n")
  await commit(upstream)
  await git(["push", "-q", `${upstream}.git`, "HEAD"], upstream, LOCAL)
  expect(await proposedOutput(origin, upstream)).toBe("proposed=true\n")
})

test("resets the branch once the base moves", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const origin = await reviewed(upstream)
  const base = await folders.make()
  await git(["clone", "-q", origin, base], base, LOCAL)
  await writeFile(join(base, "README.md"), "r\n")
  await commit(base)
  await git(["push", "-q", "origin", "HEAD"], base, LOCAL)
  expect(await proposedOutput(origin, upstream)).toBe("")
})

test("proposes the copy afresh once the owner closes the branch's pull request unmerged", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  expect(
    await proposedOutput(await reviewed(upstream), upstream, "sync/x", ghOf("sync/x", "none")),
  ).toBe("")
})

test("proposes the copy afresh when the branch's only open pull request targets another base", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  expect(
    await proposedOutput(
      await reviewed(upstream),
      upstream,
      "sync/x",
      ghOf("sync/x", "other-base"),
    ),
  ).toBe("")
})

test("proposes the copy afresh when only a fork's pull request comes from a branch of that name", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  expect(
    await proposedOutput(await reviewed(upstream), upstream, "sync/x", ghOf("sync/x", "fork")),
  ).toBe("")
})

test("stops when gh fails, such as on its login, writing no proposed=true", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const failing: Gh = async () => ({ code: 4, stdout: "", stderr: "gh auth login first\n" })
  expect(await proposedOutput(await reviewed(upstream), upstream, "sync/x", failing)).toBe(
    "stopped: gh pr list --head sync/x --base main --state open --json isCrossRepository,number exited 4: gh auth login first; fix that, then rerun",
  )
})

test.each([["{}\n"], ["not json\n"], ['[{"number":1}]\n'], ['[{"isCrossRepository":false}]\n']])(
  "stops when gh prints %j, no list of pull requests",
  async (stdout) => {
    const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
    const unlisted: Gh = async () => ({ code: 0, stdout, stderr: "" })
    expect(await proposedOutput(await reviewed(upstream), upstream, "sync/x", unlisted)).toBe(
      "stopped: gh pr list --head sync/x --base main --state open --json isCrossRepository,number printed no list of pull requests; update gh, then rerun",
    )
  },
)

test("resets a branch whose copy a reviewer edited by hand", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  const origin = await reviewed(upstream, { "plugin/skills/s/SKILL.md": "edited\n" })
  expect(await proposedOutput(origin, upstream)).toBe("")
})

test("stops on a Git failure other than a no, such as a folder that is no repository", async () => {
  const root = await folders.make()
  await mkdir(join(root, "vendored"))
  await writeFile(
    join(root, "vendored/x.json"),
    `${JSON.stringify({ ...record, commit: null, files: {} }, null, 2)}\n`,
  )
  await expect(
    proposed(root, "vendored/x.json", "sync/x", "main", ghOf("sync/x", "same-repo")),
  ).rejects.toThrow(GitError)
})

test("proposes the copy afresh when no branch proposes it", async () => {
  const upstream = await upstreamOf({ LICENSE: "MIT\n", "skills/s/SKILL.md": "x\n" })
  expect(await proposedOutput(await reviewed(upstream), upstream, "sync/other")).toBe("")
})

test("stops on an upstream that names its commits by SHA-256, before it reads a tree or writes a file", async () => {
  const upstream = join(await folders.make(), "up")
  await mkdir(join(upstream, "skills/s"), { recursive: true })
  await writeFile(join(upstream, "LICENSE"), "MIT\n")
  await writeFile(join(upstream, "skills/s/SKILL.md"), "x\n")
  await git(["init", "-q", "--object-format=sha256", upstream], upstream)
  await commit(upstream)
  await git(["clone", "-q", "--bare", upstream, `${upstream}.git`], dirname(upstream), LOCAL)
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  const before = await readFile(join(root, "vendored/x.json"), "utf8")
  const out = join(await folders.make(), "body.md")
  await expect(run(root, ["sync", "vendored/x.json", out], clonerOf(upstream))).rejects.toThrow(
    "vendored/x.json: its upstream names its commits by other than SHA-1; nustack syncs SHA-1 repositories only, so point the record at one",
  )
  expect(await readFile(join(root, "vendored/x.json"), "utf8")).toBe(before)
  expect(existsSync(join(root, "plugin"))).toBe(false)
  expect(existsSync(out)).toBe(false)
})

test("stops proposed outside a GitHub Actions step, which gives no $GITHUB_OUTPUT", async () => {
  const root = await repositoryOf({ "x.json": { ...record, commit: null, files: {} } })
  await expect(
    run(root, ["proposed", "vendored/x.json", "sync/x", "main", "body.md"]),
  ).rejects.toThrow("GITHUB_OUTPUT is unset; run proposed in a GitHub Actions step")
})
