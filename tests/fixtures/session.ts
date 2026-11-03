/**
 * Stand-ins for OpenCode's session hooks and plugin storage, for the loader's tests, typed by OpenCode's own types;
 * running a hook no one registered fails.
 */
import type { ModelRequest, SessionHooks, Store, UserPrompt } from "../../plugin/opencode.ts"

/** OpenCode's session hooks, which run only inside OpenCode. */
export class FakeSession implements SessionHooks {
  readonly hooks = new Map<string, (request: ModelRequest | UserPrompt) => Promise<void> | void>()

  readonly hook: SessionHooks["hook"] = async (name, callback) => {
    this.hooks.set(name, callback as (request: ModelRequest | UserPrompt) => Promise<void> | void)
    return {
      dispose: async () => {
        this.hooks.delete(name)
      },
    }
  }

  async run(name: "prompt", request: UserPrompt): Promise<void>
  async run(name: "context" | "compaction", request: ModelRequest): Promise<void>
  async run(name: string, request: ModelRequest | UserPrompt): Promise<void> {
    const hook = this.hooks.get(name)
    if (hook === undefined) throw new Error(`no ${name} hook is registered`)
    await hook(request)
  }
}

/** OpenCode's plugin storage, which lives only inside OpenCode. */
export class FakeStorage implements Store {
  readonly entries = new Map<string, Parameters<Store["set"]>[1]>()

  readonly get: Store["get"] = async (key) => this.entries.get(key)

  readonly set: Store["set"] = async (key, value) => {
    this.entries.set(key, value)
  }
}
