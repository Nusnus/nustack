/** Git for the script tests: each repository's own config and gitconfig beside this file only, whatever the machine's holds, and a fixed author. */
import { join } from "node:path"
import { type GitOptions, git } from "../../../scripts/git.ts"

Object.assign(process.env, {
  GIT_CONFIG_GLOBAL: join(import.meta.dir, "gitconfig"),
  GIT_CONFIG_NOSYSTEM: "1",
})
process.env.XDG_CONFIG_HOME = "/nonexistent" // where Git looks for the machine's excludes and attributes

export const LOCAL: GitOptions = Object.freeze({ transport: "file" })
export const AUTHOR = Object.freeze(["-c", "user.name=T", "-c", "user.email=t@t"])

export async function commit(root: string, message = "c"): Promise<string> {
  await git(["add", "."], root)
  await git([...AUTHOR, "commit", "-qm", message], root)
  return (await git(["rev-parse", "HEAD"], root)).trim()
}
