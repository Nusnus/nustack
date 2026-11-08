/**
 * The fake OpenCode keeps a transform's skills until that transform's dispose, which clears every skill; keeps one hook
 * per name, session and tool hooks alike, the last registered, and runs it with the session's ID until it is disposed;
 * and keeps what its storage holds.
 */
import { expect, test } from "bun:test"
import type { Skill } from "@opencode/plugin"
import { fakeOpenCode } from "../../fixtures/opencode.ts"
import { thrown } from "../../fixtures/thrown.ts"

test("adds each skill a transform adds, until the transform is disposed", async () => {
  const opencode = fakeOpenCode()
  const registration = await opencode.context.skill.transform((editor) => {
    editor.add({ id: "a-skill" } as Skill.Info)
  })
  const added = [...opencode.skills]
  await registration.dispose()
  expect([added, opencode.skills]).toEqual([["a-skill"], []])
})

test("runs each session and tool hook with the session's ID until it is disposed, then refuses to run it", async () => {
  const opencode = fakeOpenCode()
  const events: unknown[] = []
  const compaction = await opencode.context.session.hook("compaction", (event) => {
    events.push(event)
  })
  await opencode.context.tool.hook("execute.after", (event) => {
    events.push(event)
  })
  await opencode.run(["compaction", { messages: [] }])
  await opencode.run(["execute.after", { sessionID: "t" }])
  await compaction.dispose()
  const refused = await thrown(() => opencode.run(["compaction", {}]))
  expect([events, [...opencode.hooks.keys()], refused]).toEqual([
    [{ sessionID: "s", messages: [] }, { sessionID: "t" }],
    ["execute.after"],
    new Error("no compaction hook is registered; register one before running it"),
  ])
})

test("gives a second fake, made with the first's store, what the first stored", async () => {
  const first = fakeOpenCode()
  await first.context.storage.set("a-key", "a value")
  const second = fakeOpenCode(first.stored)
  const read = [
    await second.context.storage.get("a-key"),
    await second.context.storage.get("b-key"),
  ]
  expect(read).toEqual(["a value", undefined])
})
