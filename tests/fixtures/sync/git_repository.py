"""Real Git repositories shaped like the sync's upstream and nustack's checkout."""

import os
import subprocess
from dataclasses import dataclass
from typing import ClassVar
lazy from pathlib import Path


@dataclass(frozen=True)
class GitRepository:
    """A Git repository whose commits a test makes through the real Git.

    Each commit has one fixed date and author, so its hash is the same on every run.
    """

    DATE: ClassVar[str] = "2026-01-01T00:00:00Z"
    root: Path

    @classmethod
    def init(cls, root: Path) -> GitRepository:
        repository = cls(root)
        root.mkdir()
        # The expected descriptions hold these repositories' SHA-1 commit names, and Git
        # 3.0 makes SHA-256 the default: https://git-scm.com/docs/BreakingChanges
        repository.git("init", "-q", "-b", "main", "--object-format=sha1")
        return repository

    def write(self, path: str, text: str) -> Path:
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return file

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD").strip()

    def git(self, *args: str) -> str:
        return subprocess.run(  # noqa: S603 -- argv only, no shell
            ["git", *args],  # noqa: S607 -- the Git on PATH, as the sync uses
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
            env={
                "PATH": os.environ["PATH"],
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.org",
                "GIT_AUTHOR_DATE": self.DATE,
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.org",
                "GIT_COMMITTER_DATE": self.DATE,
            },
        ).stdout


@dataclass(frozen=True)
class Sync:
    """An upstream skill that moved on once, and a checkout copying its first state.

    The skill's folder name is a glob pattern, so Git reading it as a pattern
    instead of a path shows.
    """

    SOURCE: ClassVar[str] = "skills/*"
    FOLDER: ClassVar[str] = "copy"
    upstream: GitRepository
    checkout: GitRepository
    first: str
    second: str
