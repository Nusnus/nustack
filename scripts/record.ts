/**
 * The model of a record in vendored/, which the check and the sync share: its shape and the Git blob of each file. Its
 * KEBAB and UPSTREAM also hold a manifest's name and repository, in metadata.ts.
 */
import { decode, type Problem, problem } from "./tree.ts"

export const RECORD_FOLDERS = Object.freeze([".agents/skills", "plugin/skills"] as const)

/** A record in vendored/, read once where it enters, then trusted. */
export type CopyRecord = Readonly<{
  upstream: string
  source: string
  folder: (typeof RECORD_FOLDERS)[number]
  skills: readonly string[]
  commit: string | null
  files: Readonly<Record<string, string>>
}>

export const KEBAB = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
export const FILE_PATH = /^(?!(?:.*\/)?\.\.?(?:\/|$))[\w.-]+(?:\/[\w.-]+)*$/
// A Git object's SHA-1 name, as a commit, a tree entry and an index entry give it.
export const OBJECT_ID = "[0-9a-f]{40}"
export const SHA = new RegExp(`^${OBJECT_ID}$`)
// A host of dot-separated labels, then an owner and a name in the forms GitHub takes, so no user, port, query, fragment
// or . segment passes.
const HOST_LABEL = "[A-Za-z0-9](?:-*[A-Za-z0-9])*"
const OWNER = "[A-Za-z0-9](?:-?[A-Za-z0-9])*(?:_[A-Za-z0-9]+)?"
export const UPSTREAM = new RegExp(
  `^https://${HOST_LABEL}(?:\\.${HOST_LABEL})*/${OWNER}/(?!\\.\\.?$)[\\w.-]+(?<!\\.git)$`,
)

export function parseRecord(path: string, bytes?: Uint8Array | "symlink"): CopyRecord | Problem[] {
  const stem = /^vendored\/(.+)\.json$/.exec(path)?.[1]
  if (!matches(stem, KEBAB))
    return [problem(`${path}: is not named <copy>.json in kebab case; rename it`)]
  const parsed = decode(new Map(bytes === undefined ? [] : [[path, bytes]]), path)
  if (!Array.isArray(parsed)) return [parsed.problem]
  const record = Object(parsed[0]) as Record<string, unknown>
  const { upstream, source, folder, skills, commit, files } = record
  const names: unknown[] = Array.isArray(skills) ? skills : []
  const isMap = files instanceof Object && !Array.isArray(files)
  const listed: [string, unknown][] = isMap ? Object.entries(files) : []
  const distinct = names.length > 0 && new Set(names).size === names.length
  const complete = names.every((name) =>
    ["SKILL.md", "LICENSE"].every((file) => `${name}/${file}` in Object(files)),
  )
  const shape = {
    "it holds exactly upstream, source, folder, skills, commit and files":
      Object.keys(record).sort().join() === "commit,files,folder,skills,source,upstream",
    "upstream is https://<host>/<owner>/<name>": matches(upstream, UPSTREAM),
    "source is a folder path in upstream": matches(source, FILE_PATH),
    "folder is .agents/skills or plugin/skills": RECORD_FOLDERS.some((name) => name === folder),
    "skills lists distinct skill names in kebab case":
      distinct && names.every((name) => matches(name, KEBAB)),
    "commit is null or a full commit SHA": commit === null || matches(commit, SHA),
    "files maps each file, under one of its skills, to its Git blob":
      isMap &&
      listed.every(
        ([file, blob]) =>
          matches(file, FILE_PATH) &&
          names.some((name) => file.startsWith(`${name}/`)) &&
          matches(blob, SHA),
      ),
    "files is {} while commit is null": commit !== null || listed.length === 0,
    "files lists a file once commit is set": commit === null || !isMap || listed.length > 0,
    "files gives each skill its SKILL.md and LICENSE": listed.length === 0 || complete,
  }
  const fixes = Object.entries(shape).flatMap(([fix, holds]) => (holds ? [] : [fix]))
  if (fixes.length > 0)
    return fixes.map((fix) => problem(`${path}: is not a record; make sure ${fix}`))
  for (const part of [names, files, record]) Object.freeze(part)
  return record as CopyRecord
}

// The one layout of a record, which the sync writes and the check holds each record to, byte for byte.
export function recordText(record: CopyRecord): string {
  const { upstream, source, folder, skills, commit } = record
  const files = Object.fromEntries(
    Object.entries(record.files).sort(([a], [b]) => (a < b ? -1 : 1)),
  )
  return `${JSON.stringify({ upstream, source, folder, skills, commit, files }, null, 2)}\n`
}

export function matches(value: unknown, pattern: RegExp): value is string {
  return typeof value === "string" && pattern.test(value)
}

export function blobOf(bytes: Uint8Array): string {
  return new Bun.CryptoHasher("sha1").update(`blob ${bytes.length}\0`).update(bytes).digest("hex")
}
