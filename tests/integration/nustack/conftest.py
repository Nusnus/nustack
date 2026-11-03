"""The real Git repositories and gh's recorded replies the integration tests share.

That is upstream, a checkout copying its first state with the PR template the sync
fills, and an empty remote the sync pushes to, beside a command that never ends on its
own, a Git and a gh that stall, the FIFO a command writes once it is ready, and the
suite's per-test limit, which the grace for a stopped group lasts, so no deadline on
work that must finish undercuts it.
"""

import os
import shutil
import subprocess
lazy from pathlib import Path

import pytest

from nustack import process_group
from nustack.sync.description import SyncTemplate
from tests.fixtures.processes import Ready
from tests.fixtures.sync.git_repository import GitRepository
from tests.fixtures.sync.git_repository import Sync


@pytest.fixture
def sync(tmp_path: Path) -> Sync:
    upstream = GitRepository.init(tmp_path / "upstream")
    upstream.write("LICENSE", "MIT\n")
    upstream.write(f"{Sync.SOURCE_FOLDER}/SKILL.md", "old\n")
    first = upstream.commit("first")
    upstream.write(f"{Sync.SOURCE_FOLDER}/SKILL.md", "new\n")
    upstream.write(f"{Sync.SOURCE_FOLDER}/tool", "").chmod(0o755)
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
def remote_url(sync: Sync, tmp_path: Path) -> str:
    sync.checkout.git("init", "-q", "--bare", str(tmp_path / "remote.git"))
    return str(tmp_path / "remote.git")


# gh's replies, one folder per GitHub method that reads them, each recorded unedited by
# gh 2.78.0 with the argv that drew it, from microsoft/bioemu, which is archived, so
# read-only. The missing.json replies of default-branch and open-pulls come from
# repositories that do not exist, and release-state/unauthorized.json and
# pull-close/unauthorized.json from a bad GH_TOKEN, the latter against the o/r the
# proposal tests name. Only a repository's writers see its drafts, so
# release-state/draft.json was recorded from one of nustack's own, without its argv, and
# open-pulls/several.json without the head filter, so it lists every open pull request
# for main.
@pytest.fixture
def github_fixtures(repository_root: Path) -> Path:
    return repository_root / "tests/fixtures/github"


# A command a time limit must stop never ends on its own, so no load lets it finish
# first; tail follows /dev/null until a signal ends it, and writes to /dev/null, since
# tail dies of SIGPIPE once run closes the pipe it would otherwise write to:
# https://github.com/coreutils/coreutils/blob/v8.32/src/tail.c#L340-L375
@pytest.fixture
def stall() -> str:
    return "/usr/bin/tail -f /dev/null > /dev/null"


@pytest.fixture
def stalling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stall: str) -> None:
    folder = tmp_path / "stalling"
    folder.mkdir()
    for name in ("git", "gh"):
        script = folder / name
        script.write_text(f"#!/bin/sh\nexec {stall}\n")
        script.chmod(0o755)
    monkeypatch.setenv("PATH", str(folder))


# A loaded machine can let a command's limit pass, or an interrupt land, before its
# shell sets its trap or starts its processes. So each command writes the FIFO once it
# is set up, and its limit counts, and the test acts, from when the fixture reads it.
# Only the first communicate, the command's, waits for the FIFO, so a later process,
# such as alive's ps, runs at once.
@pytest.fixture
def ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ready:
    ready = Ready(tmp_path / "ready")
    os.mkfifo(ready.path)
    communicate = subprocess.Popen.communicate

    def once_ready(
        process: subprocess.Popen[bytes], stdin: bytes, timeout: float
    ) -> tuple[bytes, bytes]:
        monkeypatch.setattr(subprocess.Popen, "communicate", communicate)
        _ = ready.path.read_bytes()
        ready.reached()
        return communicate(process, stdin, timeout)

    monkeypatch.setattr(subprocess.Popen, "communicate", once_ready)
    return ready


@pytest.fixture
def per_test_limit(pytestconfig: pytest.Config) -> float:
    return float(pytestconfig.getini("timeout"))


# The wait for a stopped group is work that must finish, so it lasts as long as the
# test may, and a slow clean-up on a loaded machine still ends before SIGKILL.
@pytest.fixture
def unhurried(monkeypatch: pytest.MonkeyPatch, per_test_limit: float) -> None:
    monkeypatch.setattr(process_group, "GRACE", per_test_limit)
