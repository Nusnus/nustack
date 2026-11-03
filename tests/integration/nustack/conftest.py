"""The real Git repositories the sync's and release's integration tests share.

That is upstream, a checkout copying its first state with the PR template the sync
fills, and an empty remote the sync pushes to.
"""

import shutil
lazy from pathlib import Path

import pytest

from nustack.sync.description import SyncTemplate
from tests.fixtures.sync.git_repository import GitRepository
from tests.fixtures.sync.git_repository import Sync


@pytest.fixture
def sync(tmp_path: Path) -> Sync:
    upstream = GitRepository.init(tmp_path / "upstream")
    upstream.write("LICENSE", "MIT\n")
    upstream.write(f"{Sync.SOURCE}/SKILL.md", "old\n")
    first = upstream.commit("first")
    upstream.write(f"{Sync.SOURCE}/SKILL.md", "new\n")
    upstream.write(f"{Sync.SOURCE}/tool", "").chmod(0o755)
    second = upstream.commit("second")
    checkout = GitRepository.init(tmp_path / "checkout")
    checkout.write(f"{Sync.FOLDER}/LICENSE", "MIT\n")
    checkout.write(f"{Sync.FOLDER}/SKILL.md", "old\n")
    checkout.commit("base")
    return Sync(upstream, checkout, first, second)


@pytest.fixture
def template(sync: Sync, repository_root: Path) -> None:
    path = SyncTemplate.PATH
    shutil.copy(repository_root / path, sync.checkout.write(str(path), ""))
    sync.checkout.commit("template")


@pytest.fixture
def remote(sync: Sync, tmp_path: Path) -> str:
    sync.checkout.git("init", "-q", "--bare", str(tmp_path / "remote.git"))
    return str(tmp_path / "remote.git")
