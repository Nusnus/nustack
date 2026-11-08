/** The metadata the script tests share: a manifest every rule passes, and a tree that holds one file. */
import type { Tree } from "../../scripts/tree.ts"

/** A plugin manifest that every metadata rule passes. */
export const manifest = {
  name: "nustack",
  version: "0.1.0",
  description: "d",
  author: { name: "A" },
  homepage: "https://h",
  repository: "https://h/o/n",
  license: "MIT",
}

/** A tree whose one file at path holds value, as written when it is text, or as JSON. */
export const tree = (path: string, value: unknown): Tree =>
  new Map([
    [path, new TextEncoder().encode(typeof value === "string" ? value : JSON.stringify(value))],
  ])
