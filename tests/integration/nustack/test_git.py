"""Git answers from the repository it was given, whatever the caller's Git points at.

It says whether one commit is an ancestor of another, passes input and options
through, and a failed command or a missing repository stops with a Problem naming
the fix.
"""

lazy from pathlib import Path

import pytest

from nustack.git import Git
from nustack.git import GitError
from nustack.problem import Problem
lazy from tests.fixtures.sync.git_repository import Sync


class TestGit:
    """Answers from its own repository, and fails with a Problem naming the fix.

    The caller's Git variables never redirect it; a missing repository, a failed
    command or a revision an ancestry check cannot read fails naming the fix.
    """

    def test_reads_its_own_repository_when_the_caller_points_git_elsewhere(
        self, sync: Sync, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GIT_DIR", str(sync.checkout.root / ".git"))
        assert Git(sync.upstream.root).head == sync.second

    def test_keeps_each_variable_git_does_not_list_as_local(
        self, sync: Sync, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GIT_DIR", "elsewhere")
        monkeypatch.setenv("GIT_OBJECT_DIRECTORY", "elsewhere")
        monkeypatch.setenv("NUSTACK_CANARY", "kept")
        environment = Git(sync.upstream.root).environment
        assert (
            {"GIT_DIR", "GIT_OBJECT_DIRECTORY"} & environment.keys(),
            environment["NUSTACK_CANARY"],
        ) == (set(), "kept")

    def test_names_a_missing_repository_and_the_fix(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing"
        with pytest.raises(GitError) as failed:
            Git(missing).run("rev-parse", "HEAD")
        assert failed.value.problem == Problem(
            missing,
            "cannot run Git (No such file or directory); check the clone path and Git",
        )

    def test_names_the_repository_and_the_next_step_of_a_failed_command(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(GitError) as failed:
            Git(tmp_path).run("rev-parse", "HEAD")
        assert str(failed.value) == (
            f"{tmp_path}: git rev-parse exited 128; fix the cause Git printed above, "
            "such as a missing clone or revision"
        )

    def test_tells_an_ancestor_from_a_commit_that_is_not_one(self, sync: Sync) -> None:
        git = Git(sync.upstream.root)
        assert (
            git.is_ancestor(sync.first, sync.second),
            git.is_ancestor(sync.second, sync.first),
        ) == (True, False)

    def test_fails_an_ancestry_check_on_a_revision_it_cannot_read(
        self, sync: Sync
    ) -> None:
        with pytest.raises(GitError) as failed:
            Git(sync.upstream.root).is_ancestor("HEAD", "origin/main")
        assert str(failed.value) == (
            f"{sync.upstream.root}: git merge-base exited 128; fix the cause Git"
            " printed above, such as a missing clone or revision"
        )

    def test_passes_input_and_variables_to_git(self, sync: Sync) -> None:
        git = Git(sync.upstream.root)
        assert (
            git.run("hash-object", "--stdin", stdin=b"old\n"),
            git.run(
                "var",
                "GIT_AUTHOR_IDENT",
                environment=frozendict({"GIT_AUTHOR_NAME": "Ada"}),
            ).split(b" <")[0],
        ) == (b"3367afdbbf91e638efe983616377c60477cc6612\n", b"Ada")

    def test_reports_the_exit_status_of_a_command(self, sync: Sync) -> None:
        git = Git(sync.upstream.root)
        assert (git.status("rev-parse", "HEAD"), git.status("rev-parse", "x")) == (
            0,
            128,
        )
