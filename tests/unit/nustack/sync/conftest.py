"""What the sync's unit tests read: Git trees, histories, contents and descriptions."""

lazy from pathlib import Path

import pytest


@pytest.fixture
def sync_fixtures(repository_root: Path) -> Path:
    return repository_root / "tests/fixtures/sync"
