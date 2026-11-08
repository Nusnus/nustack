/**
 * A script prints its usage for --help alone, or as a command's only argument; runMain prints what a script returns, or
 * its error's message alone, exiting 1; requireTool stops on a tool not on the PATH, saying how to install it.
 */
import { afterEach, beforeEach, describe, expect, spyOn, test } from "bun:test"
import { asksForUsage, requireTool, runMain } from "../../../scripts/command.ts"

test.each([
  [["--help"], true],
  [["list", "--help"], true],
  [[], false],
  [["list"], false],
  [["list", "x"], false],
  [["--help", "list"], false],
  [["other", "--help"], false],
  [["list", "--help", "x"], false],
] as const)("asksForUsage(%p) is %p", (args, asks) => {
  expect(asksForUsage(args, ["list", "sync"])).toBe(asks)
})

describe("runMain", () => {
  let exitCode: typeof process.exitCode
  beforeEach(() => {
    exitCode = process.exitCode
  })
  afterEach(() => {
    // Bun keeps a code once set, even when set back to undefined, so an unset one goes back as 0.
    process.exitCode = exitCode ?? 0
  })

  test("prints what the script returns for the root and the command line's arguments", async () => {
    const log = spyOn(console, "log").mockImplementation(() => {})
    try {
      await runMain(async (root, args) => `${root} ${args.join(" ")}`, "/r")
      expect(log.mock.calls).toEqual([[`/r ${process.argv.slice(2).join(" ")}`]])
      expect(process.exitCode).toBe(exitCode)
    } finally {
      log.mockRestore()
    }
  })

  test.each([
    ["an error", new Error("stop"), "stop"],
    ["a string", "text", "text"],
  ])(
    "prints %s it throws, its message alone with no stack, and exits 1",
    async (_, thrown, printed) => {
      const error = spyOn(console, "error").mockImplementation(() => {})
      try {
        await runMain(async () => {
          throw thrown
        }, "/r")
        expect(error.mock.calls).toEqual([[printed]])
        expect(process.exitCode).toBe(1)
      } finally {
        error.mockRestore()
      }
    },
  )
})

describe("requireTool", () => {
  test("stops on a tool not on the PATH, saying how to install it", () => {
    const which = spyOn(Bun, "which").mockReturnValue(null)
    try {
      expect(() => requireTool("x", "install x")).toThrow("x is not on PATH; install x, then rerun")
      expect(which).toHaveBeenCalledWith("x")
    } finally {
      which.mockRestore()
    }
  })

  test("passes a tool on the PATH", () => {
    const which = spyOn(Bun, "which").mockReturnValue("/bin/x")
    try {
      expect(() => requireTool("x", "install x")).not.toThrow()
    } finally {
      which.mockRestore()
    }
  })
})
