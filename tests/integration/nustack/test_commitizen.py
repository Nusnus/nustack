"""commitizen sets the version in every file that holds it, or stops naming the fix.

A bump that fails, that cannot start or that outlasts its time limit stops with a
Problem, beside what commitizen printed on its standard output.
"""

import os
import sys
lazy from pathlib import Path

import pytest

from nustack.commitizen import Commitizen
from nustack.commitizen import CommitizenError
from nustack.problem import Problem
from tests.fixtures.git_repository import GitRepository


class TestCommitizen:
    """Sets the next patch version or the one given, and fails with the fix.

    A repository with no release tag, even when the caller's input would answer
    commitizen's question with a yes, a Python that cannot start and a bump that
    outlasts its time limit each stop it.
    """

    PYPROJECT = (
        '[project]\nname = "kit"\nversion = "1.2.3"\n\n'
        '[tool.commitizen]\nversion_provider = "uv"\ntag_format = "v$version"\n'
    )
    LOCK = 'version = 1\n\n[[package]]\nname = "kit"\nversion = "1.2.3"\n'

    @pytest.fixture
    def repository(self, tmp_path: Path) -> GitRepository:
        repository = GitRepository.init(tmp_path / "kit")
        repository.write("pyproject.toml", self.PYPROJECT)
        repository.write("uv.lock", self.LOCK)
        repository.commit("base")
        repository.git("tag", "v1.2.3")
        return repository

    @pytest.mark.parametrize(
        ("version", "bumped"), [(None, "1.2.4"), ("2.0.0", "2.0.0")]
    )
    def test_sets_the_next_patch_or_the_version_given(
        self, repository: GitRepository, version: str | None, bumped: str
    ) -> None:
        Commitizen(repository.root).bump(version)
        assert (
            (repository.root / "pyproject.toml").read_text(),
            (repository.root / "uv.lock").read_text(),
            repository.git("tag", "--list"),
        ) == (
            self.PYPROJECT.replace("1.2.3", bumped),
            self.LOCK.replace("1.2.3", bumped),
            "v1.2.3\n",
        )

    def test_stops_without_a_release_tag_beside_what_commitizen_printed(
        self, repository: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repository.git("tag", "--delete", "v1.2.3")
        with pytest.raises(CommitizenError) as caught:
            Commitizen(repository.root).bump(None)
        assert (
            caught.value.problem,
            capsys.readouterr().err.startswith(
                "No tag matching configuration could be found."
            ),
        ) == (
            Problem(
                repository.root,
                "cz bump exited 1; fix the cause it printed above, such as a release"
                " tag this clone lacks, which git fetch --tags origin brings",
            ),
            True,
        )

    def test_stops_without_a_release_tag_whatever_its_callers_input_says(
        self, repository: GitRepository, tmp_path: Path
    ) -> None:
        repository.git("tag", "--delete", "v1.2.3")
        answer = tmp_path / "answer"
        answer.write_text("y\n")
        saved = os.dup(0)
        try:
            with answer.open() as given:
                os.dup2(given.fileno(), 0)
            with pytest.raises(CommitizenError):
                Commitizen(repository.root).bump(None)
        finally:
            os.dup2(saved, 0)
            os.close(saved)
        assert (repository.root / "pyproject.toml").read_text() == self.PYPROJECT

    def test_stops_where_its_python_cannot_start(
        self, repository: GitRepository, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "executable", str(repository.root / "missing"))
        with pytest.raises(CommitizenError) as caught:
            Commitizen(repository.root).bump(None)
        problem = Problem(
            repository.root,
            "cannot run commitizen (No such file or directory); run make install",
        )
        assert (caught.value.problem, str(caught.value)) == (problem, str(problem))

    def test_stops_a_bump_that_outlasts_its_time_limit(
        self, repository: GitRepository, monkeypatch: pytest.MonkeyPatch, stall: str
    ) -> None:
        script = repository.write("stall", f"#!/bin/sh\nexec {stall}\n")
        script.chmod(0o755)
        monkeypatch.setattr(sys, "executable", str(script))
        with pytest.raises(CommitizenError) as caught:
            Commitizen(repository.root, timeout=0.1).bump(None)
        assert caught.value.problem == Problem(
            repository.root,
            "cz bump took over 0.1 seconds; check what it waits on, such as its"
            " disk, then rerun",
        )
