/**
 * What the scripts share as commands: the form of the usage each prints, for the release and sync scripts when they
 * print it and how each runs from the command line. A usage names how to run its script, then its arguments' forms,
 * and --help alone, or as a command's only argument, asks for it. A script prints what it returns, or its error's message with no stack trace, exiting 1.
 */
export function usage(script: string, forms: string): string {
  return `usage: bun scripts/${script}.ts ${forms}`
}

export function asksForUsage(args: readonly string[], commands: readonly string[]): boolean {
  const [first, second] = args
  return (
    (args.length === 1 && first === "--help") ||
    (args.length === 2 && second === "--help" && commands.some((name) => name === first))
  )
}

export async function runMain(
  run: (root: string, args: readonly string[]) => Promise<string>,
  root: string,
): Promise<void> {
  try {
    console.log(await run(root, process.argv.slice(2)))
  } catch (error) {
    console.error(error instanceof Error ? error.message : error)
    process.exitCode = 1
  }
}
