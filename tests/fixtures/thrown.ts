/** What a call threw or rejected with, for a test to compare whole. */

// Bun's toThrow, given an Error, compares only its message, though its reference says it compares the name too
// (https://bun.com/reference/bun/test/Matchers/toThrow), so a test compares what a call threw with toEqual, which
// compares both.
export function thrown(call: () => unknown): Promise<unknown> {
  return Promise.try(call).catch((caught: unknown) => caught)
}
