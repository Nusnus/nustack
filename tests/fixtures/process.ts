/**
 * A child process's exit code and all it printed, read once it exits, both streams at once, so neither fills and stalls
 * the child.
 */

/** What a finished child process gave back. */
export interface Finished {
  readonly code: number
  readonly stdout: string
  readonly stderr: string
}

export async function finished(child: {
  exited: Promise<number>
  stdout: ReadableStream
  stderr: ReadableStream
}): Promise<Finished> {
  const [code, stdout, stderr] = await Promise.all([
    child.exited,
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
  ])
  return Object.freeze({ code, stdout, stderr })
}
