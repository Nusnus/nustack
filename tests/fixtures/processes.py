"""When a command is ready, whether a process still runs, and running gh or a module.

A command writes Ready's FIFO once it is set up, and the test acts then. A tool's
module runs under the test's interpreter, and gh is whichever is first on PATH, such as
the fake. `alive` counts a zombie as ended, since it holds no running code.
"""

import subprocess
import sys
lazy from collections.abc import Callable
lazy from pathlib import Path


class Ready:
    """The FIFO a command writes once it is set up, and what the test does then."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.actions: list[Callable[[], None]] = []

    def reached(self) -> None:
        for action in self.actions:
            action()


def alive(pid: int) -> bool:
    state = subprocess.run(  # noqa: S603 -- argv only, no shell
        ["ps", "-o", "stat=", "-p", str(pid)],  # noqa: S607 -- the system's ps
        stdout=subprocess.PIPE,
        # Ruff asks for check; ps exits 1 for a pid that has ended, which alive reads:
        # https://docs.astral.sh/ruff/rules/subprocess-run-without-check/
        check=False,
        text=True,
    ).stdout.strip()
    return state != "" and not state.startswith("Z")


def run_gh(*argv: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- argv only, no shell
        ["gh", *argv],  # noqa: S607 -- the gh first on PATH, such as the fake
        input=stdin,
        capture_output=True,
        text=True,
        # Ruff asks for check; a test that runs gh reads its exit status itself:
        # https://docs.astral.sh/ruff/rules/subprocess-run-without-check/
        check=False,
    )


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
