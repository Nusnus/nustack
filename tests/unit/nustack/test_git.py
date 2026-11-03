"""A Git error's text is the Problem it carries, and each Git command has a minute."""

from datetime import timedelta
from pathlib import Path

from nustack.git import Git
from nustack.git import GitError
from nustack.problem import Problem


class TestGitError:
    """A Git failure's text is the Problem it carries."""

    def test_gives_its_problem_as_its_text(self) -> None:
        problem = Problem(Path("/r"), "git fetch exited 1; fix the cause Git printed")
        assert (
            str(GitError(problem))
            == "/r: git fetch exited 1; fix the cause Git printed"
        )


class TestGit:
    """Each Git command has a time limit."""

    def test_gives_each_command_a_minute_by_default(self) -> None:
        assert Git(Path("/r")).timeout == timedelta(minutes=1).total_seconds()
