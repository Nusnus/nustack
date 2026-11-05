"""Git, run on one repository whatever Git hook variables the caller exports.

Paths never read as options or patterns. A command that fails, that Git cannot
start, or that outlasts its time limit stops with a Problem naming the fix beside
the message Git printed, as does a commit Git names by other than its SHA-1.
"""

import os
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property
from pathlib import PurePosixPath
from typing import ClassVar
lazy from collections.abc import Generator
lazy from pathlib import Path

from nustack import process_group
from nustack.problem import Problem
from nustack.sha import NotSha1Error
from nustack.sha import Sha


class GitError(Exception):
    """A Git command failed or outlasted its time limit; the problem says what to do."""

    def __init__(self, problem: Problem) -> None:
        super().__init__(problem)
        self.problem = problem


@dataclass(frozen=True)
class Git:
    """Runs Git on one repository, reading paths as paths, never as patterns."""

    # These commands always reach a remote, so their stall points at it.
    REMOTE_COMMANDS: ClassVar[frozenset[str]] = frozenset(
        {"fetch", "ls-remote", "push"}
    )
    # Of the other commands nustack runs, only a blob read can reach a remote, and
    # only in a partial clone, such as the sync's blob:none clone of upstream, which
    # fetches each missing object from its promisor remote; logs and tree listings
    # read commits and trees, which such a clone holds:
    # https://git-scm.com/docs/partial-clone
    FETCHING_COMMANDS: ClassVar[frozenset[str]] = frozenset({"cat-file"})

    root: Path
    # The slowest command, a fetch or push of one small branch, takes seconds when
    # the network is healthy; a minute leaves room for a slow one and still stops a
    # stalled one.
    timeout: float = 60

    # A Git hook exports variables such as GIT_DIR that point Git at another
    # repository; Git lists them all:
    # https://git-scm.com/docs/git-rev-parse#Documentation/git-rev-parse.txt---local-env-vars
    # rev-parse starts no process of its own, so subprocess.run's kill stops all of
    # it.
    @cached_property
    def environment(self) -> frozendict[str, str]:
        try:
            listing = subprocess.run(
                ["git", "rev-parse", "--local-env-vars"],  # noqa: S607 -- runner's Git
                stdout=subprocess.PIPE,
                check=True,
                text=True,
                timeout=self.timeout,
            ).stdout
        except subprocess.TimeoutExpired as error:
            raise GitError(self.stall("rev-parse")) from error
        local = set(listing.split())
        return frozendict(
            (name, value) for name, value in os.environ.items() if name not in local
        )

    @property
    def head(self) -> Sha:
        with self.naming_by_sha("git rev-parse"):
            return Sha(self.run("rev-parse", "HEAD").decode().strip())

    @contextmanager
    def naming_by_sha(self, source: str) -> Generator[None]:
        try:
            yield
        except NotSha1Error as error:
            raise GitError(Problem(self.root, f"{source} {error}")) from error

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

    # rev-parse --verify --quiet exits 1, silently, when no commit has the name:
    # https://git-scm.com/docs/git-rev-parse#Documentation/git-rev-parse.txt---verify
    def has_commit(self, commit: Sha) -> bool:
        match self.status("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}"):
            case 0:
                return True
            case 1:
                return False
            case status:
                raise GitError(self.failure("rev-parse", status))

    # rev-parse --verify --quiet exits 1, silently, when the commit holds no such path.
    def file_at(self, commit: Sha, path: PurePosixPath) -> bytes | None:
        name = f"{commit}:{path}"
        match self.status("rev-parse", "--verify", "--quiet", name):
            case 0:
                return self.run("cat-file", "blob", name)
            case 1:
                return None
            case status:
                raise GitError(self.failure("rev-parse", status))

    # Each path that differs from the commit in the working tree, staged or not, and
    # each untracked path Git does not ignore.
    def changed_since(self, commit: Sha) -> tuple[PurePosixPath, ...]:
        listings = (
            self.run("diff", "--name-only", "--no-renames", "-z", str(commit), "--"),
            self.run("ls-files", "--others", "--exclude-standard", "-z"),
        )
        paths = {
            PurePosixPath(path)
            for listing in listings
            for path in listing.decode(errors="surrogateescape").split("\0")
            if path
        }
        return tuple(sorted(paths))

    def run(
        self,
        command: str,
        *args: str,
        stdin: bytes = b"",
        environment: frozendict[str, str] = frozendict(),
    ) -> bytes:
        completed = self.complete(command, args, stdin, environment)
        if completed.returncode != 0:
            raise GitError(self.failure(command, completed.returncode))
        return completed.stdout

    def status(self, command: str, *args: str) -> int:
        completed = self.complete(command, args)
        return completed.returncode

    def complete(
        self,
        command: str,
        args: tuple[str, ...],
        stdin: bytes = b"",
        environment: frozendict[str, str] = frozendict(),
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            return process_group.run(
                ["git", "--literal-pathspecs", command, *args],
                timeout=self.timeout,
                stdin=stdin,
                stderr=None,
                cwd=self.root,
                env=self.environment | environment,
            )
        except OSError as error:
            what = f"cannot run Git ({error.strerror}); check the clone path and Git"
            raise GitError(Problem(self.root, what)) from error
        except subprocess.TimeoutExpired as error:
            raise GitError(self.stall(command)) from error

    def stall(self, command: str) -> Problem:
        if command in self.REMOTE_COMMANDS:
            check = "check that the remote answers"
        elif command in self.FETCHING_COMMANDS:
            check = (
                "check what Git waits on, such as its disk or, in a partial clone,"
                " the remote it fetches from"
            )
        else:
            check = "check what Git waits on, such as its disk or a hook"
        return Problem(
            self.root,
            f"git {command} took over {self.timeout:g} seconds; {check}, then rerun",
        )

    def failure(self, command: str, status: int) -> Problem:
        return Problem(
            self.root,
            f"git {command} exited {status}; fix the cause Git printed above, such as"
            " a missing clone or revision",
        )
