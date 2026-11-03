/** The fake registry keeps skills and transforms as OpenCode's registry does, so the loader's tests can trust it. */
import { describe, expect, test } from "bun:test"
import type { Skill } from "@opencode/plugin"
import { FakeRegistry, type SkillEditor } from "../../fixtures/registry.ts"

/**
 * Each skill is kept by its id, and each transform gets the editor until disposed; an id the fake does not hold gets
 * undefined and updates nothing.
 */
describe("FakeRegistry", () => {
  const skill = {
    id: "a" as Skill.ID,
    name: "a" as Skill.Name,
    description: "A.",
    autoinvoke: true,
    path: "/a/SKILL.md" as Skill.Info["path"],
    content: "",
  }

  test("lists and gets each skill added", () => {
    const { editor } = new FakeRegistry()
    editor.add(skill)
    expect([editor.list(), editor.get("a"), editor.get("b")]).toEqual([[skill], skill, undefined])
  })

  test("updates and removes a skill by its id", () => {
    const { editor } = new FakeRegistry()
    editor.add(skill)
    const describeAsB: Parameters<SkillEditor["update"]>[1] = (found) => {
      found.description = "B."
    }
    editor.update("a", describeAsB)
    editor.update("b", describeAsB)
    const updated = editor.get("a")?.description
    editor.remove("a")
    expect([updated, editor.list()]).toEqual(["B.", []])
  })

  test("hands each transform the editor, and disposes it once asked", async () => {
    const registry = new FakeRegistry()
    const registration = await registry.context.skill.transform((editor) => editor.add(skill))
    await registration.dispose()
    expect([registry.skills.get("a"), registry.disposed]).toEqual([skill, true])
  })
})
