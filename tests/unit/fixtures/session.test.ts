/** The fakes that stand in for OpenCode's session hooks and plugin storage behave as those do. */
import { describe, expect, test } from "bun:test"
import type { ModelRequest } from "../../../plugin/opencode.ts"
import { FakeSession, FakeStorage } from "../../fixtures/session.ts"

/** The fake keeps one hook per name, and running a name with no hook registered is an error. */
describe("FakeSession", () => {
  const request: ModelRequest = {
    sessionID: "ses_1" as ModelRequest["sessionID"],
    messages: [],
    system: [],
  }

  test("runs the hook registered under a name, and none once its registration is disposed", async () => {
    const session = new FakeSession()
    const seen: ModelRequest[] = []
    const registration = await session.hook("context", async (got) => void seen.push(got))
    await session.run("context", request)
    await registration.dispose()
    expect(seen).toEqual([request])
    await expect(session.run("context", request)).rejects.toThrow("no context hook is registered")
  })
})

/** The fake keeps values between calls, and an unset key reads as undefined. */
describe("FakeStorage", () => {
  test("gives back what was set, and nothing for a key never set", async () => {
    const storage = new FakeStorage()
    await storage.set("a", true)
    expect([await storage.get("a"), await storage.get("b")]).toEqual([true, undefined])
  })
})
