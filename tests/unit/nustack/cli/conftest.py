"""A working folder outside the model repository, for the command tests."""

import pytest


@pytest.fixture
def elsewhere(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))
