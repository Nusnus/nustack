"""A gh first on PATH that replays the replies each integration test gives it."""

import os
lazy from pathlib import Path

import pytest

from tests.fixtures.gh import FakeGh


@pytest.fixture
def gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeGh:
    fake = FakeGh.install(tmp_path / "gh")
    monkeypatch.setenv("PATH", f"{fake.folder}{os.pathsep}{os.environ['PATH']}")
    return fake
