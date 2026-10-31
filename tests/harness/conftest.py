"""Fixtures that give each test its own copy of this repository, free to break."""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from nustack.problem import Problem
from nustack.repository import Repository

ROOT = Path(__file__).parents[2]


@pytest.fixture
def whats() -> Callable[[list[Problem]], list[str]]:
    def what_each_says(problems: list[Problem]) -> list[str]:
        return [problem.what for problem in problems]

    return what_each_says


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    shutil.copytree(ROOT / "plugin", tmp_path / "plugin")
    for marketplace in (".claude-plugin", ".cursor-plugin"):
        shutil.copytree(ROOT / marketplace, tmp_path / marketplace)
    for name in ("CHANGELOG.md", "LICENSE", "pyproject.toml"):
        shutil.copy(ROOT / name, tmp_path)
    return Repository(tmp_path)


@pytest.fixture
def plugin_root(repository: Repository) -> Path:
    return repository.plugin.root


@pytest.fixture
def version(repository: Repository) -> str:
    return repository.plugin.manifest.version
