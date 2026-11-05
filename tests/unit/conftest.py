"""A fresh model repository for each unit test to break."""

lazy from pathlib import Path

import pytest

from tests.fixtures.repository import ModelRepository


@pytest.fixture
def repository(tmp_path: Path) -> ModelRepository:
    return ModelRepository(tmp_path)
