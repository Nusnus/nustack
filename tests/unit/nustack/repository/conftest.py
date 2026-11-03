"""Where the changelog tests place the changelog they build."""

from pathlib import Path

import pytest


@pytest.fixture
def changelog_path() -> Path:
    return Path("/r/CHANGELOG.md")
