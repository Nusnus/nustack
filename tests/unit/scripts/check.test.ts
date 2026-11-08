/** Each rule check.ts holds reports a copy of a passing tree broken the way it forbids, with the file and the fix. */
import { describe, expect, spyOn, test } from "bun:test"
import { check } from "../../../scripts/check.ts"
import * as parser from "../../../scripts/markdown.ts"
import { blobOf, type CopyRecord, recordText } from "../../../scripts/record.ts"
import type { Tree } from "../../../scripts/tree.ts"
import { manifest } from "../../fixtures/metadata.ts"

const bytes = (text: string) => new TextEncoder().encode(text)
const knap = "---\nname: knap\ndescription: k\nlicense: MIT\n---\n[x](../../nowhere.md)\n"
const mode = [
  "---\nname: nus-mode\ndescription: m\n---\n# nus-mode\n",
  "## Playbooks\n\n- [p](playbooks/p.md)\n",
  "## Principles\n\n- [n](../principle-naming/SKILL.md), [web](https://x.y), [a](#goal)\n",
].join("\n")
const principle = (name: string, description = "n") =>
  `---\nname: ${name}\ndescription: ${description}\ndisable-model-invocation: true\ntriggers:\n  - user\n---\n`
const record: CopyRecord = {
  upstream: "https://github.com/o/n",
  source: "skills",
  folder: "plugin/skills",
  skills: ["knap"],
  commit: "a".repeat(40),
  files: { "knap/LICENSE": blobOf(bytes("MIT")), "knap/SKILL.md": blobOf(bytes(knap)) },
}
const MODE = "plugin/skills/nus-mode/SKILL.md"
const NAMING = "plugin/skills/principle-naming/SKILL.md"

function tree(changes: Record<string, string | null | "symlink"> = {}): Tree {
  const files: Record<string, string | null | "symlink"> = {
    LICENSE: "MIT",
    ".gitattributes": "plugin/** text eol=lf\nplugin/skills/knap/** -text\n",
    "plugin/LICENSE": "MIT",
    "pyproject.toml": '[project]\nversion = "0.1.0"\n',
    "plugin/.claude-plugin/plugin.json": JSON.stringify(manifest),
    "plugin/.cursor-plugin/plugin.json": JSON.stringify(manifest),
    "plugin/.devin-plugin/plugin.json": JSON.stringify(manifest),
    "plugin/package.json": JSON.stringify({ name: "nustack", version: "0.1.0", type: "module" }),
    ".claude-plugin/marketplace.json": JSON.stringify({ plugins: [{ name: "nustack" }] }),
    ".cursor-plugin/marketplace.json": JSON.stringify({ plugins: [{ name: "nustack" }] }),
    ".github/workflows/ci.yml": "jobs:\n  release-zip:\n    needs: make-check\n",
    ".github/workflows/release.yml": "jobs:\n  ci:\n    needs: tag\n  publish:\n    needs: ci\n",
    "plugin/opencode.ts": "export {}\n",
    [MODE]: mode,
    "plugin/skills/nus-mode/playbooks/p.md": "# p\n\n[mode](../SKILL.md)\n",
    [NAMING]: principle("principle-naming"),
    "plugin/skills/knap/SKILL.md": knap,
    "plugin/skills/knap/LICENSE": "MIT",
    "vendored/obsidian-skills.json": recordText(record),
    ...changes,
  }
  return new Map(
    Object.entries(files).flatMap(([path, text]) =>
      text === null ? [] : [[path, text === "symlink" ? text : bytes(text)] as const],
    ),
  )
}

const problems = async (changes: Record<string, string | null | "symlink">) =>
  (await check(tree(changes))).map(String)

describe("check", () => {
  test("passes a tree that keeps every rule", async () => {
    expect(await check(tree())).toEqual([])
  })

  test("parses each Markdown file once, however many rules read it", async () => {
    const parse = spyOn(parser, "markdown")
    try {
      await check(tree())
      const texts = parse.mock.calls.map(([text]) => text)
      expect(texts.length).toBeGreaterThan(1)
      expect(new Set(texts).size).toBe(texts.length)
    } finally {
      parse.mockRestore()
    }
  })

  test.each<[string, Record<string, string | null | "symlink">, string[]]>([
    [
      "a manifest that differs",
      { "plugin/.devin-plugin/plugin.json": JSON.stringify({ ...manifest, version: "0.2.0" }) },
      [
        "plugin/.devin-plugin/plugin.json: differs from plugin/.claude-plugin/plugin.json; make every manifest the same",
      ],
    ],
    [
      "a publish job that needs no CI",
      { ".github/workflows/release.yml": "jobs:\n  ci:\n    needs: tag\n" },
      [
        ".github/workflows/release.yml: jobs.publish.needs is not ci, so a release could publish before CI passes; set it to ci",
      ],
    ],
    [
      "a stray file in plugin/",
      { "plugin/notes.txt": "x" },
      ["plugin/notes.txt: is not a file the plugin installs; move it out of plugin/"],
    ],
    [
      "a principle with playbooks",
      { "plugin/skills/principle-naming/playbooks/p.md": "# p\n" },
      [
        "plugin/skills/principle-naming/playbooks/p.md: is not a file the plugin installs; move it out of plugin/",
      ],
    ],
    [
      "a symlink in plugin/",
      { "plugin/opencode.ts": "symlink" },
      ["plugin/opencode.ts: is a symlink; put the file itself there"],
    ],
    [
      "a missing loader",
      { "plugin/opencode.ts": null },
      ["plugin/opencode.ts: is missing; restore it"],
    ],
    ["a missing LICENSE", { LICENSE: null }, ["LICENSE: is missing; restore it"]],
    [
      "a plugin LICENSE unlike the repository's",
      { "plugin/LICENSE": "Apache" },
      ["plugin/LICENSE: is not the repository's LICENSE; copy that one here"],
    ],
    [
      "a skill folder out of kebab case",
      { "plugin/skills/Principle-x/SKILL.md": principle("Principle-x") },
      [
        "plugin/skills/Principle-x/SKILL.md: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/Principle-x: is not named in kebab case; rename it",
      ],
    ],
    [
      "a skill folder with no SKILL.md",
      { "plugin/skills/principle-x/notes.md": "x" },
      [
        "plugin/skills/principle-x/notes.md: is not a file the plugin installs; move it out of plugin/",
        "plugin/skills/principle-x: has no SKILL.md; add one or remove it",
        `${MODE}: ## Principles does not link plugin/skills/principle-x/SKILL.md; link it there`,
      ],
    ],
    [
      "a name that is not its folder's",
      { [NAMING]: principle("principle-names") },
      [`${NAMING}: name is not its folder's; use one for both`],
    ],
    [
      "a description over 1024 characters",
      { [NAMING]: principle("principle-naming", "d".repeat(1025)) },
      [`${NAMING}: description has over 1024 characters; shorten it`],
    ],
    [
      "a field outside the authored ones",
      { [NAMING]: principle("principle-naming").replace("---\n", "---\nlicense: MIT\n") },
      [
        `${NAMING}: holds a field outside name, description, disable-model-invocation, triggers; drop it`,
      ],
    ],
    [
      "a principle the model can invoke",
      { [NAMING]: "---\nname: principle-naming\ndescription: n\n---\n" },
      [`${NAMING}: needs disable-model-invocation: true and triggers: [user]`],
    ],
    [
      "a mode the model cannot invoke",
      {
        [MODE]: mode.replace(
          "description: m\n",
          "description: m\ndisable-model-invocation: true\n",
        ),
      },
      [
        `${MODE}: sets disable-model-invocation or triggers, which a mode leaves unset; drop both, or name the folder principle-<name> or language-<name> if it is one`,
      ],
    ],
    [
      "a field that spans lines",
      { [NAMING]: principle("principle-naming", ">\n  n") },
      [
        `${NAMING}: holds a line that is neither a field, <key>: <value>, nor a list entry under a field with no value, <spaces>- <value>; keep each field and entry to one line`,
      ],
    ],
    [
      "a list entry under a field with a value",
      {
        [NAMING]: principle("principle-naming").replace(
          "description: n\n",
          "description: n\n  - x\n",
        ),
      },
      [
        `${NAMING}: holds a line that is neither a field, <key>: <value>, nor a list entry under a field with no value, <spaces>- <value>; keep each field and entry to one line`,
      ],
    ],
    [
      "a value that holds ---",
      { [NAMING]: principle("principle-naming", '"a --- b"') },
      [`${NAMING}: a value holds ---; reword it`],
    ],
    [
      "an authored skill of 500 lines",
      { [NAMING]: principle("principle-naming") + "x\n".repeat(493) },
      [`${NAMING}: has 500 lines, where it needs under 500; shorten it`],
    ],
    [
      "a second mode",
      {
        "plugin/skills/other-mode/SKILL.md":
          "---\nname: other-mode\ndescription: o\n---\n# other-mode\n",
      },
      [
        "plugin/skills: holds 2 modes, where it needs exactly 1; keep one mode, and name each other skill principle-<name> or language-<name>",
      ],
    ],
    [
      "a mode over its cap",
      { [MODE]: `${mode}\n${"x".repeat(9000)}\n` },
      [
        expect.stringMatching(
          /^plugin\/skills\/nus-mode\/SKILL\.md: body has \d+ characters, over 9000; cut it$/,
        ),
      ],
    ],
    [
      "a playbook the mode does not link",
      { "plugin/skills/nus-mode/playbooks/q.md": "# q\n" },
      [`${MODE}: ## Playbooks does not link plugin/skills/nus-mode/playbooks/q.md; link it there`],
    ],
    [
      "a principle linked under the wrong heading",
      { [MODE]: mode.replace("## Principles", "## Languages") },
      [`${MODE}: ## Principles does not link ${NAMING}; link it there`],
    ],
    [
      "a link to no file",
      { "plugin/skills/nus-mode/playbooks/p.md": "# p\n\n[x](gone.md)\n" },
      [
        "plugin/skills/nus-mode/playbooks/p.md: links gone.md, no file under plugin/; link one, or a full URL",
      ],
    ],
    [
      "a link that climbs out of plugin/",
      { "plugin/skills/nus-mode/playbooks/p.md": "# p\n\n[x](../../../../LICENSE)\n" },
      [
        "plugin/skills/nus-mode/playbooks/p.md: links ../../../../LICENSE, no file under plugin/; link one, or a full URL",
      ],
    ],
    [
      "an absolute link",
      { "plugin/skills/nus-mode/playbooks/p.md": "# p\n\n[x]: /plugin/LICENSE\n" },
      [
        "plugin/skills/nus-mode/playbooks/p.md: links the absolute path /plugin/LICENSE, which breaks once the plugin moves; link it by its path from this file",
      ],
    ],
    [
      "a copy's file that its record does not list",
      { "plugin/skills/knap/extra.md": "x" },
      [
        "plugin/skills/knap/extra.md: is not in vendored/obsidian-skills.json; remove it, or rerun the sync",
      ],
    ],
    [
      "a copy's file at another blob",
      { "plugin/skills/knap/LICENSE": "MIT\r\n" },
      [
        "plugin/skills/knap/LICENSE: is missing or not the blob vendored/obsidian-skills.json lists; restore it, or rerun the sync",
      ],
    ],
    [
      "a record named out of kebab case",
      { "vendored/Bad.json": recordText(record) },
      ["vendored/Bad.json: is not named <copy>.json in kebab case; rename it"],
    ],
    [
      "a copy whose text .gitattributes keeps",
      { ".gitattributes": "plugin/** text eol=lf\n" },
      [
        ".gitattributes: does not unset text for plugin/skills/knap; add the line plugin/skills/knap/** -text",
      ],
    ],
    [
      "a .gitattributes that sets text again after the copies' lines",
      { ".gitattributes": "plugin/skills/knap/** -text\nplugin/** text eol=lf\n" },
      [".gitattributes: holds a line after the first that unsets text; move it above those lines"],
    ],
    [
      "a .gitattributes that leaves plugin/'s line endings to the clone",
      { ".gitattributes": "plugin/skills/knap/** -text\n" },
      [".gitattributes: does not set plugin/** text eol=lf; add that line"],
    ],
  ])("reports %s", async (_, changes, expected) => {
    expect(await problems(changes)).toEqual(expected)
  })
})
