/** A stand-in for OpenCode's skill registry, for the loader's tests. */
import type { Plugin, Skill } from "@opencode/plugin"

export type SkillEditor = Parameters<Parameters<Plugin.Context["skill"]["transform"]>[0]>[0]

/**
 * A stand-in for OpenCode's skill registry, which runs only inside OpenCode: it follows the
 * SkillEditor contract in @opencode/plugin's types, and the tests in tests/unit/fixtures/registry.test.ts hold it to
 * that contract.
 */
export class FakeRegistry {
  readonly skills = new Map<string, Skill.Info>()
  disposed = false

  get editor(): SkillEditor {
    return {
      list: () => [...this.skills.values()],
      get: (id) => this.skills.get(id),
      add: (skill) => {
        this.skills.set(skill.id, skill)
      },
      update: (id, change) => {
        const skill = this.skills.get(id)
        if (skill === undefined) return
        const copy = { ...skill }
        change(copy)
        this.skills.set(id, copy)
      },
      remove: (id) => {
        this.skills.delete(id)
      },
    }
  }

  get context(): { skill: Pick<Plugin.Context["skill"], "transform"> } {
    return {
      skill: {
        transform: async (edit) => {
          edit(this.editor)
          return {
            dispose: async () => {
              this.disposed = true
            },
          }
        },
      },
    }
  }
}
