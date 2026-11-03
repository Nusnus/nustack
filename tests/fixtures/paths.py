"""This repository's root, its project settings and the replies Git and gh recorded."""

from pathlib import Path

import pytest


@pytest.fixture
def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def pyproject(repository_root: Path) -> Path:
    return repository_root / "pyproject.toml"


@pytest.fixture
def sync_fixtures(repository_root: Path) -> Path:
    return repository_root / "tests/fixtures/sync"


# gh's replies, one folder per GitHub method that reads them, each recorded unedited
# with the argv that drew it from microsoft/bioemu, which is archived, so read-only.
# Only a repository's writers see its drafts, so release-draft/draft.json was
# recorded from one of nustack's own, without its argv, and open-pulls/several.json
# without the base and branch filters, so it lists every open pull request.
@pytest.fixture
def github_fixtures(repository_root: Path) -> Path:
    return repository_root / "tests/fixtures/github"
