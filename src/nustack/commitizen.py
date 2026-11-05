"""commitizen's `cz bump`, run to set a release's version in every file that holds it.

It sets the next patch version, or the one given, and makes no commit, tag or changelog
entry. A bump that fails, that cannot start, or that outlasts its time limit stops with
a Problem naming the fix beside what commitizen printed.
"""

import subprocess
import sys
from dataclasses import dataclass
from typing import ClassVar
lazy from pathlib import Path

from nustack import process_group
from nustack.problem import Problem
lazy from nustack.version import Version


class CommitizenError(Exception):
    """A bump failed or outlasted its time limit; the problem says what to do."""

    def __init__(self, problem: Problem) -> None:
        super().__init__(problem)
        self.problem = problem


@dataclass(frozen=True)
class Commitizen:
    """Runs commitizen, from the Python that runs nustack, on one repository."""

    # commitizen reads the increment in any case, and mutmut leaves class values
    # alone, so no mutant of it runs.
    PATCH: ClassVar[str] = "PATCH"
    # With no tag, commitizen asks whether the bump is the first; an empty input
    # answers nothing, so it stops rather than read the caller's input as a yes.
    NO_ANSWER: ClassVar[str] = ""
    root: Path
    # A bump reads the release tags and rewrites a few small files, which takes about
    # a second; a minute still stops one that stalls.
    timeout: float = 60

    # --increment PATCH keeps a version below 0.1.0, which commitizen would otherwise
    # pick for a feat commit in 0.x. commitizen asks whether the bump is the first
    # one when it finds no release tag, and with no terminal stops instead of asking:
    # https://commitizen-tools.github.io/commitizen/commands/bump/
    def bump(self, version: Version | None) -> None:
        increment = ["--increment", self.PATCH] if version is None else [version]
        command = [sys.executable, "-m", "commitizen", "bump", "--version-files-only"]
        try:
            completed = process_group.run(
                [*command, *increment],
                timeout=self.timeout,
                stdin=self.NO_ANSWER,
                stderr=None,
                cwd=self.root,
                env=None,
            )
        except OSError as error:
            what = f"cannot run commitizen ({error.strerror}); run make install"
            raise CommitizenError(Problem(self.root, what)) from error
        except subprocess.TimeoutExpired as error:
            what = (
                f"cz bump took over {self.timeout:g} seconds; check what it waits on,"
                " such as its disk, then rerun"
            )
            raise CommitizenError(Problem(self.root, what)) from error
        if completed.returncode != 0:
            # commitizen prints some of its reasons on stdout, such as a missing tag.
            sys.stderr.write(completed.stdout)
            what = (
                f"cz bump exited {completed.returncode}; fix the cause it printed"
                " above, such as a release tag this clone lacks, which git fetch"
                " --tags origin brings"
            )
            raise CommitizenError(Problem(self.root, what))
