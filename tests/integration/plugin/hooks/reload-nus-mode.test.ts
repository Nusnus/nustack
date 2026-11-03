/**
 * After a summarization, the Claude Code hook prints nus-mode's folder and body for a session whose transcript shows it
 * loaded the mode, prints nothing otherwise, and stops with the fix on input or an installed SKILL.md it cannot use.
 * The transcripts and SessionStart inputs in tests/fixtures/claude-code are records from real Claude Code sessions.
 * Coverage cannot reach the sh script, as bunfig.toml says, so each of its branches here was seen to fail when broken
 * by hand.
 */
import { afterEach, describe, expect, test } from "bun:test"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { TemporaryFolders } from "../../../fixtures/folders.ts"
import { finished } from "../../../fixtures/process.ts"

const claudeCode = join(import.meta.dirname, "..", "..", "..", "fixtures", "claude-code")
const inputs = join(claudeCode, "session-start")
// Claude Code's SessionStart input after a /compact: the one input the hook acts on. Each test points its
// transcript_path at the transcript it needs.
const compact = JSON.parse(await readFile(join(inputs, "compact.json"), "utf8"))
// Claude Code's SessionStart input when a session starts: an input without a summarization.
const startup = await readFile(join(inputs, "startup.json"), "utf8")
const record = await readFile(join(claudeCode, "transcripts", "invoked.jsonl"), "utf8")

/**
 * Only a compaction's input is acted on. Of transcript_path's JSON escapes, only \", \\ and \/ are undone; any other
 * input it cannot read stops it with exit code 1 and the fix on stderr, which Claude Code shows the user. Claude Code
 * passes one JSON line naming the session's transcript and the input's source
 * (https://code.claude.com/docs/en/hooks#common-input-fields; https://code.claude.com/docs/en/hooks#sessionstart-input),
 * so an input that breaks that stands for another host or a run from outside Claude Code. An input without a source,
 * or a session that only listed the mode or invoked another plugin's nus-mode, gets nothing; of two transcript paths
 * the first counts, and a mode loaded from a CRLF SKILL.md is found.
 */
describe("reload-nus-mode.sh", () => {
  const plugin = join(import.meta.dirname, "..", "..", "..", "..", "plugin")
  const transcripts = join(claudeCode, "transcripts")
  // The transcript line that holds the body of a nus-mode the session invoked: the line the hook looks for.
  const invoked = join(transcripts, "invoked.jsonl")
  // The transcript line that lists nus-mode among the skills, with only nustack installed and Claude Code's bundled
  // skills off: a line that names nus-mode without its body.
  const listed = join(transcripts, "listed.jsonl")
  // The load record of a session that invoked another plugin's nus-mode, installed beside nustack, as /other:nus-mode.
  const otherPlugin = join(transcripts, "other-plugin.jsonl")
  // The recorded session ran nustack from this folder; the hook reloads only its own plugin's mode, so each run points
  // the record at the plugin folder it runs with.
  const recorded = "/home/ubuntu/scratch/nustack/plugin"
  const folders = new TemporaryFolders()

  function local(text: string, root = plugin): string {
    return text.replaceAll(recorded, JSON.stringify(root).slice(1, -1))
  }

  async function written(text: string, name = "session.jsonl"): Promise<string> {
    const path = join(await folders.make(), name)
    await writeFile(path, text)
    return path
  }

  /** One run of the hook on the input Claude Code would pass it. */
  class Run {
    readonly code: number
    readonly stdout: string
    readonly stderr: string

    constructor(code: number, stdout: string, stderr: string) {
      this.code = code
      this.stdout = stdout
      this.stderr = stderr
    }

    static after(transcript: string, root = plugin): Promise<Run> {
      return Run.of(JSON.stringify({ ...compact, transcript_path: transcript }), root)
    }

    static async of(input: string, root: string | null = plugin): Promise<Run> {
      const env = { ...process.env }
      delete env.CLAUDE_PLUGIN_ROOT
      if (root !== null) env.CLAUDE_PLUGIN_ROOT = root
      const hook = Bun.spawn(["sh", join(plugin, "hooks", "reload-nus-mode.sh")], {
        env,
        stdin: new Blob([input]),
        stderr: "pipe",
      })
      const { code, stdout, stderr } = await finished(hook)
      return new Run(code, stdout, stderr)
    }
  }

  afterEach(() => folders.clear())

  test("prints nothing at a session start without a summarization", async () => {
    const run = await Run.of(startup)
    expect([run.code, run.stdout, run.stderr]).toEqual([0, "", ""])
  })

  test("prints nothing for an input without a source", async () => {
    // Claude Code's SessionStart input always has a source; this stands for a host whose input lacks one.
    const run = await Run.of(
      JSON.stringify({ ...compact, source: undefined, transcript_path: invoked }),
    )
    expect([run.code, run.stdout, run.stderr]).toEqual([0, "", ""])
  })

  test("takes the first transcript_path of an input that names two", async () => {
    // Claude Code passes one JSON line; this one adds a second naming another transcript.
    const transcript = await written(local(record))
    const input = `${JSON.stringify({ ...compact, transcript_path: transcript })}\n${JSON.stringify({ transcript_path: "/nonexistent/session.jsonl" })}`
    const run = await Run.of(input)
    expect([run.code, run.stdout]).toEqual([0, (await Run.after(transcript)).stdout])
  })

  test.each([
    [
      // Claude Code always passes transcript_path; this stands for a run from outside it.
      "has no transcript_path",
      JSON.stringify({ ...compact, transcript_path: undefined }),
      "nustack reload-nus-mode: the hook input has no transcript_path; run the hook from Claude Code, which passes one\n",
    ],
    [
      // JSON writes a control character in a path as \u; the recorded path holds none.
      "holds an escape the hook cannot undo",
      JSON.stringify({ ...compact, transcript_path: "/tmp/\u0001/session.jsonl" }),
      'nustack reload-nus-mode: transcript_path holds a JSON escape other than \\", \\\\ or \\/; move the session to a path without one\n',
    ],
    [
      // Claude Code names the session's transcript; this stands for one deleted before the hook reads it.
      "names a transcript that is missing",
      JSON.stringify({ ...compact, transcript_path: "/nonexistent/session.jsonl" }),
      "nustack reload-nus-mode: the transcript that transcript_path names is no readable file; check that the file exists\n",
    ],
    [
      // Claude Code names the session's transcript file; this stands for a folder in its place.
      "names a folder",
      JSON.stringify({ ...compact, transcript_path: tmpdir() }),
      "nustack reload-nus-mode: the transcript that transcript_path names is no readable file; check that the file exists\n",
    ],
  ])("stops with the fix on an input that %s", async (_case, input, problem) => {
    const run = await Run.of(input)
    expect([run.code, run.stdout, run.stderr]).toEqual([1, "", problem])
  })

  test("reads a transcript path holding an escaped backslash as the path it names", async () => {
    const folder = await folders.make()
    await mkdir(join(folder, "a\\b"))
    await writeFile(join(folder, "a\\b", "session.jsonl"), local(record))
    const run = await Run.after(join(folder, "a\\b", "session.jsonl"))
    expect([run.code, run.stdout]).toEqual([
      0,
      (await Run.after(await written(local(record)))).stdout,
    ])
  })

  test("reads a transcript path holding an escaped quote as the path it names", async () => {
    const folder = await folders.make()
    await mkdir(join(folder, 'a"b'))
    await writeFile(join(folder, 'a"b', "session.jsonl"), local(record))
    const run = await Run.after(join(folder, 'a"b', "session.jsonl"))
    expect([run.code, run.stdout]).toEqual([
      0,
      (await Run.after(await written(local(record)))).stdout,
    ])
  })

  test("reads a transcript path whose slashes JSON escapes as \\/ as the path it names", async () => {
    // Claude Code writes / unescaped, as tests/fixtures/claude-code/session-start/compact.json records; JSON allows \/,
    // so this input escapes each one.
    const transcript = await written(local(record))
    const input = JSON.stringify({ ...compact, transcript_path: transcript }).replaceAll("/", "\\/")
    const run = await Run.of(input)
    expect([run.code, run.stdout]).toEqual([0, (await Run.after(transcript)).stdout])
  })

  test("stops with the fix when CLAUDE_PLUGIN_ROOT is unset", async () => {
    const run = await Run.of(JSON.stringify({ ...compact, transcript_path: invoked }), null)
    expect([run.code, run.stdout, run.stderr]).toEqual([
      1,
      "",
      "nustack reload-nus-mode: CLAUDE_PLUGIN_ROOT is unset; run the hook from Claude Code, which sets it\n",
    ])
  })

  test.each([
    [
      "is missing",
      null,
      "nustack reload-nus-mode: nus-mode's SKILL.md cannot be read; reinstall the nustack plugin\n",
    ],
    [
      "does not open with its title",
      (text: string) => text.replace("\n# nus-mode\n", "\n# The mode\n"),
      "nustack reload-nus-mode: nus-mode's SKILL.md does not open with its title; reinstall the nustack plugin\n",
    ],
    [
      "has no frontmatter",
      (text: string) => text.slice(text.indexOf("# nus-mode\n")),
      "nustack reload-nus-mode: nus-mode's SKILL.md does not open with its title; reinstall the nustack plugin\n",
    ],
    [
      "has one frontmatter fence",
      (text: string) => `---\n${text.slice(text.indexOf("# nus-mode\n"))}`,
      "nustack reload-nus-mode: nus-mode's SKILL.md does not open with its title; reinstall the nustack plugin\n",
    ],
    [
      "has a blank body",
      (text: string) => text.slice(0, text.indexOf("\n# nus-mode\n")),
      "nustack reload-nus-mode: nus-mode's SKILL.md does not open with its title; reinstall the nustack plugin\n",
    ],
  ])("stops with the fix when an installed SKILL.md %s", async (_case, edit, problem) => {
    const root = await folders.make()
    await mkdir(join(root, "skills", "nus-mode"), { recursive: true })
    if (edit !== null) {
      const text = await readFile(join(plugin, "skills", "nus-mode", "SKILL.md"), "utf8")
      await writeFile(join(root, "skills", "nus-mode", "SKILL.md"), edit(text))
    }
    const run = await Run.after(invoked, root)
    expect([run.code, run.stdout, run.stderr]).toEqual([1, "", problem])
  })

  test("prints nus-mode's folder and body, without its frontmatter, for a session that invoked it", async () => {
    const run = await Run.after(await written(local(record)))
    const text = await readFile(join(plugin, "skills", "nus-mode", "SKILL.md"), "utf8")
    const body = text
      .split("\n")
      .slice(text.split("\n").indexOf("---", 1) + 1)
      .join("\n")
      .replace(/^\n+/, "")
    expect([run.code, run.stdout, run.stderr]).toEqual([
      0,
      "This session worked in nus-mode before its context was summarized. nus-mode follows; keep working in it.\n\n" +
        `Base directory for this skill: ${plugin}/skills/nus-mode\n\n${body}`,
      "",
    ])
  })

  test.each([
    ["an LF", "\n"],
    ["a CRLF", "\r\n"],
  ])(
    "prints %s SKILL.md's whole body with LF lines, every section included",
    async (_case, end) => {
      const root = await folders.make()
      await mkdir(join(root, "skills", "nus-mode"), { recursive: true })
      // A SKILL.md the test writes, so the expected output can hold its whole body.
      const text =
        "---\nname: nus-mode\ndescription: A mode.\n---\n\n# nus-mode\n\nSay hi.\n\n## Playbooks\n\n- One.\n"
      await writeFile(join(root, "skills", "nus-mode", "SKILL.md"), text.replaceAll("\n", end))
      const run = await Run.after(await written(local(record, root)), root)
      expect([run.code, run.stdout, run.stderr]).toEqual([
        0,
        "This session worked in nus-mode before its context was summarized. nus-mode follows; keep working in it.\n\n" +
          `Base directory for this skill: ${root}/skills/nus-mode\n\n# nus-mode\n\nSay hi.\n\n## Playbooks\n\n- One.\n`,
        "",
      ])
    },
  )

  test("finds a mode a session loaded from a CRLF SKILL.md", async () => {
    // No recorded session loaded a CRLF SKILL.md; this one turns the recorded load's line breaks into CRLF ones, as
    // JSON writes them.
    const run = await Run.after(await written(local(record).replaceAll("\\n", "\\r\\n")))
    expect([run.code, run.stdout]).toEqual([
      0,
      (await Run.after(await written(local(record)))).stdout,
    ])
  })

  test("prints nothing for a session that only listed nus-mode among its skills", async () => {
    const run = await Run.after(listed)
    expect([run.code, run.stdout, run.stderr]).toEqual([0, "", ""])
  })

  test("prints nothing for a session that only invoked another plugin's skill named nus-mode", async () => {
    const run = await Run.after(otherPlugin)
    expect([run.code, run.stdout, run.stderr]).toEqual([0, "", ""])
  })

  test.each([
    [
      // No recorded session quoted the mode in a prompt; this one drops the load record's meta flag, which a prompt the
      // user types lacks.
      "quoted the mode in a prompt",
      (line: string) => line.replace('"isMeta":true,', ""),
    ],
    [
      // No recorded session read SKILL.md through a tool; this one drops the folder line a skill load opens with, which
      // a tool result that quotes the file lacks.
      "quoted the mode without the folder a load gives",
      (line: string) => line.replace(/Base directory for this skill: [^"]*?\\n\\n/, ""),
    ],
    [
      // No recorded session loaded a skill titled past the mode's title; this one adds a letter to the recorded load's
      // title.
      "loaded a skill whose title starts with the mode's",
      (line: string) => line.replace("# nus-mode\\n", "# nus-modes\\n"),
    ],
    [
      // No recorded session loaded a skill whose body quotes the mode; this one renames the recorded load's skill and
      // opens its body with the mode's folder line and title.
      "loaded another skill whose body quotes the mode's folder line and title",
      (line: string) =>
        line.replace(
          "/skills/nus-mode\\n\\n# nus-mode\\n",
          "/skills/sample-mode\\n\\nIt quotes: Base directory for this skill: /plugin/skills/nus-mode\\n\\n# nus-mode\\n",
        ),
    ],
  ])("prints nothing for a session that only %s", async (_case, edit) => {
    expect(edit(local(record))).not.toBe(local(record))
    const run = await Run.after(await written(edit(local(record))))
    expect([run.code, run.stdout, run.stderr]).toEqual([0, "", ""])
  })
})
