"""A fresh model repository for each unit test to break, and a folder outside it."""

lazy from pathlib import Path

import pytest

from tests.fixtures.repository import ModelRepository


@pytest.fixture
def repository(tmp_path: Path) -> ModelRepository:
    return ModelRepository(tmp_path)


@pytest.fixture
def elsewhere(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))
