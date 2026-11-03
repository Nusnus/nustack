"""This repository's root and its project settings."""

from pathlib import Path

import pytest


@pytest.fixture
def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def pyproject(repository_root: Path) -> Path:
    return repository_root / "pyproject.toml"
