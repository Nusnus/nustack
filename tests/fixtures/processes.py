"""When a command is ready, whether a process still runs, and running a tool's module.

A command writes Ready's FIFO once it is set up, and a tool's module runs under the
test's interpreter. `alive` counts a zombie as ended, since it holds no running code.
"""

import subprocess
import sys
lazy import threading
lazy from pathlib import Path


class Ready:
    """The FIFO a command writes once it is set up, and the timers that start then."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.timers: list[threading.Timer] = []
        self.started: list[threading.Timer] = []

    def start(self) -> None:
        for timer in self.timers:
            timer.start()
            self.started.append(timer)

    def stop(self) -> None:
        for timer in self.started:
            timer.cancel()
            timer.join()


def alive(pid: int) -> bool:
    state = subprocess.run(  # noqa: S603 -- argv only, no shell
        ["ps", "-o", "stat=", "-p", str(pid)],  # noqa: S607 -- the system's ps
        stdout=subprocess.PIPE,
        check=False,
        text=True,
    ).stdout.strip()
    return state != "" and not state.startswith("Z")


def run_module(
    *argv: str, cwd: Path | None = None, source: str | None = None, check: bool = False
) -> str:
    return subprocess.run(  # noqa: S603 -- the test's own interpreter, with fixed arguments
        [sys.executable, "-m", *argv],
        cwd=cwd,
        input=source,
        capture_output=True,
        text=True,
        # Ruff asks for check; a test that reads the output itself leaves it off:
        # https://docs.astral.sh/ruff/rules/subprocess-run-without-check/
        check=check,
    ).stdout
