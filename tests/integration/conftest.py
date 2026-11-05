"""The Git and the gh every integration test runs.

Git reads only the repository's own config and excludes, so a test passes or fails the
same on each machine. gh is a fake first on PATH that replays the replies each test
gives it.
"""

import os
lazy from pathlib import Path

import pytest

from tests.fixtures.gh import FakeGh


# Git also reads the system's and the user's config, and the user's excludes file,
# which defaults to $XDG_CONFIG_HOME/git/ignore even when no config names it:
# https://git-scm.com/docs/git#Documentation/git.txt-GITCONFIGGLOBAL
# https://git-scm.com/docs/git-config#Documentation/git-config.txt-coreexcludesFile
@pytest.fixture(autouse=True)
def isolated_git(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    config = tmp_path_factory.getbasetemp() / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))


@pytest.fixture
def gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeGh:
    fake = FakeGh.install(tmp_path / "gh")
    monkeypatch.setenv("PATH", f"{fake.folder}{os.pathsep}{os.environ['PATH']}")
    return fake
