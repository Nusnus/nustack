"""Git, run on one repository whatever Git hook variables the caller exports.

Paths never read as options or patterns. A command that fails, or that Git cannot
start, stops with a Problem naming the fix beside the message Git printed.
"""

import os
import subprocess
from dataclasses import dataclass
from functools import cached_property
lazy from pathlib import Path

from nustack.problem import Problem


class GitError(Exception):
    """A Git command failed; Git's own message names why."""

    def __init__(self, problem: Problem) -> None:
        super().__init__(problem)
        self.problem = problem


@dataclass(frozen=True)
class Git:
    """Runs Git on one repository, reading paths as paths, never as patterns."""

    root: Path

    # A Git hook exports variables such as GIT_DIR that point Git at another
    # repository; Git lists them all:
    # https://git-scm.com/docs/git-rev-parse#Documentation/git-rev-parse.txt---local-env-vars
    @cached_property
    def environment(self) -> frozendict[str, str]:
        listing = subprocess.run(
            ["git", "rev-parse", "--local-env-vars"],  # noqa: S607 -- runner's Git
            stdout=subprocess.PIPE,
            check=True,
            text=True,
        ).stdout
        local = set(listing.split())
        return frozendict(
            (name, value) for name, value in os.environ.items() if name not in local
        )

    @property
    def head(self) -> str:
        return self.run("rev-parse", "HEAD").decode().strip()

    # merge-base exits 1 when the commit is not an ancestor and another non-zero
    # status when Git fails: https://git-scm.com/docs/git-merge-base
    def is_ancestor(self, commit: str, of: str) -> bool:
        match self.status("merge-base", "--is-ancestor", commit, of):
            case 0:
                return True
            case 1:
                return False
            case status:
                raise GitError(self.failure("merge-base", status))

    def run(
        self,
        command: str,
        *args: str,
        # Only the commands given input read it, so no test tells the default from
        # another value.
        stdin: bytes = b"",  # pragma: no mutate
        environment: frozendict[str, str] = frozendict(),
    ) -> bytes:
        completed = self.complete(command, args, stdin, environment)
        if completed.returncode != 0:
            raise GitError(self.failure(command, completed.returncode))
        return completed.stdout

    def status(self, command: str, *args: str) -> int:
        # The commands it runs read no input, so no test tells one input from another.
        completed = self.complete(command, args, b"", frozendict())  # pragma: no mutate
        return completed.returncode

    def complete(
        self,
        command: str,
        args: tuple[str, ...],
        stdin: bytes,
        environment: frozendict[str, str],
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(  # noqa: S603 -- argv only, no shell
                ["git", "--literal-pathspecs", command, *args],  # noqa: S607 -- runner's Git
                cwd=self.root,
                env=self.environment | environment,
                input=stdin,
                stdout=subprocess.PIPE,
                # Ruff asks for check, and the caller reads the exit status; False is
                # subprocess.run's default, so no mutant of it acts differently:
                # https://docs.astral.sh/ruff/rules/subprocess-run-without-check/
                check=False,  # pragma: no mutate
            )
        except OSError as error:
            what = f"cannot run Git ({error.strerror}); check the clone path and Git"
            raise GitError(Problem(self.root, what)) from error

    def failure(self, command: str, status: int) -> Problem:
        return Problem(
            self.root,
            f"git {command} exited {status}; fix the cause Git printed above, such as"
            " a missing clone or revision",
        )
