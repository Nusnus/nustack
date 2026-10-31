"""Packaging the plugin for hosts that install it from a file."""

import os
import stat
import sys
from pathlib import Path
from zipfile import ZIP_STORED
from zipfile import ZipFile

import pytest

from nustack.bundle import Bundle
from nustack.plugin import Plugin
from nustack.repository import Repository


def test_the_zip_ignores_file_times(repository: Repository, tmp_path: Path) -> None:
    plugin = repository.plugin
    first = Bundle(repository.plugin).write(tmp_path / "first").read_bytes()
    for path in plugin.files:
        os.utime(path, (0, 0))
    assert Bundle(repository.plugin).write(tmp_path / "second").read_bytes() == first


def test_the_zip_holds_regular_files(
    repository: Repository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    with ZipFile(Bundle(repository.plugin).write(tmp_path)) as archive:
        entries = archive.infolist()
    assert {entry.create_system for entry in entries} == {3}
    assert {entry.external_attr >> 16 for entry in entries} == {stat.S_IFREG | 0o644}


def test_the_zip_stores_its_files_uncompressed(
    repository: Repository, tmp_path: Path
) -> None:
    with ZipFile(Bundle(repository.plugin).write(tmp_path)) as archive:
        entries = archive.infolist()
    assert {entry.compress_type for entry in entries} == {ZIP_STORED}


def test_the_zip_holds_the_license(repository: Repository, tmp_path: Path) -> None:
    with ZipFile(Bundle(repository.plugin).write(tmp_path)) as archive:
        license_text = archive.read(Plugin.LICENSE)
    assert license_text == repository.license_path.read_bytes()


def test_the_zip_lists_its_files_in_posix_path_order(
    repository: Repository, tmp_path: Path
) -> None:
    (repository.plugin.root / "skills" / "nus-mode" / "playbooks-a.md").write_text("")
    with ZipFile(Bundle(repository.plugin).write(tmp_path)) as archive:
        names = archive.namelist()
    assert names.index("skills/nus-mode/playbooks-a.md") < names.index(
        "skills/nus-mode/playbooks/investigate.md"
    )


def test_the_zip_installs_as_the_plugin_it_came_from(
    repository: Repository, tmp_path: Path
) -> None:
    plugin = repository.plugin
    with ZipFile(Bundle(plugin).write(tmp_path / "dist")) as archive:
        archive.extractall(tmp_path / "installed")
    installed = Plugin(tmp_path / "installed")
    assert installed.problems() == []
    assert installed.manifest == plugin.manifest
    assert [path.relative_to(installed.root) for path in installed.files] == [
        path.relative_to(plugin.root) for path in plugin.files
    ]
    assert [path.read_bytes() for path in installed.files] == [
        path.read_bytes() for path in plugin.files
    ]
