/** A child process's exit code and all it printed, read once it exits. */

/** What a finished child process gave back. */
export interface Finished {
  code: number
  stdout: string
  stderr: string
}

/** Waits for the child to exit while reading both of its output streams, so neither fills and stalls it. */
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
  return { code, stdout, stderr }
}
