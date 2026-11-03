"""A command run within a time limit, or stopped with its process group.

subprocess.run kills only its child once the limit passes, so a process the child
started, such as the ssh Git starts for a fetch, outlives it. The command runs in a
session of its own, and a stall, or an interrupt such as Ctrl-C, which reaches only
the caller's process group, stops the command's process group, which holds every
process it started unless one left it: SIGTERM first, then a wait of up to GRACE,
and one POLL past it, for the whole group to end, so each can clean up, then
SIGKILL. In its own session the command has no terminal, so Git and ssh cannot
prompt for a password, and a SIGTERM or SIGHUP sent to the caller does not reach it.
"""

import contextlib
import os
import signal
import subprocess
import time
from typing import overload
lazy from collections.abc import Mapping
lazy from pathlib import Path

# Two seconds leaves a process room to clean up on a loaded machine before SIGKILL,
# which no process can clean up after.
GRACE = 2.0
# A tenth of the grace, so the check costs little and SIGKILL follows soon after it.
POLL = GRACE / 10


@overload
def run(
    args: list[str],
    *,
    timeout: float,
    stdin: bytes,
    stderr: int | None,
    cwd: Path | None,
    env: Mapping[str, str] | None,
) -> subprocess.CompletedProcess[bytes]: ...


@overload
def run(
    args: list[str],
    *,
    timeout: float,
    stdin: str,
    stderr: int | None,
    cwd: Path | None,
    env: Mapping[str, str] | None,
) -> subprocess.CompletedProcess[str]: ...


def run(  # noqa: PLR0913 -- one argument per Popen option a caller sets
    args: list[str],
    *,
    timeout: float,
    stdin: bytes | str,
    stderr: int | None,
    cwd: Path | None,
    env: Mapping[str, str] | None,
) -> subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]:
    with subprocess.Popen(  # noqa: S603 -- argv only, no shell
        args,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr,
        text=isinstance(stdin, str),
        # A process group alone keeps the terminal, where a prompt from Git or ssh
        # in a background group stops the command; a session has no terminal.
        start_new_session=True,
    ) as process:
        try:
            stdout, errors = process.communicate(stdin, timeout)
        except BaseException:
            # SIGTERM first, since Git removes its lock files when a signal it can
            # catch ends it, and SIGKILL cannot be caught:
            # https://github.com/git/git/blob/v2.51.0/lockfile.h#L18-L25
            # The group can end on its own before either signal.
            # A second interrupt during the wait still reaches SIGKILL.
            try:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
                wait_for_group(process)
            finally:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                # A second interrupt can land before the wait reaps the command, and
                # Popen's exit waits briefly only after a first interrupt, which
                # communicate already took. SIGKILL ends it at once, so no test can
                # reach this bound; the pragma's line holds this call alone.
                process.wait(GRACE)  # pragma: no mutate
            raise
    return subprocess.CompletedProcess(args, process.returncode, stdout, errors)


# The command's own process can end at once on SIGTERM while a process it started
# is still cleaning up, so the wait lasts until the whole group is gone or the grace
# runs out.
def wait_for_group(process: subprocess.Popen[bytes] | subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + GRACE
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(GRACE)
    while time.monotonic() < deadline:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(POLL)
