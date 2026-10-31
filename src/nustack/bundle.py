"""Packaging the plugin for hosts that install it from a file."""

import stat
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
from zipfile import ZipFile
from zipfile import ZipInfo

from nustack.plugin import Plugin


@dataclass
class Bundle:
    """The plugin as one zip, identical whenever its files are."""

    TIMESTAMP: ClassVar[tuple[int, int, int, int, int, int]] = (1980, 1, 1, 0, 0, 0)
    UNIX: ClassVar[int] = 3
    FILE_MODE: ClassVar[int] = stat.S_IFREG | 0o644
    plugin: Plugin

    def write(self, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        manifest = self.plugin.manifest
        path = folder / f"{manifest.name}-{manifest.version}.zip"
        with ZipFile(path, "w") as archive:
            for file in self.plugin.files:
                self.add(archive, file.relative_to(self.plugin.root).as_posix(), file)
        return path

    def add(self, archive: ZipFile, name: str, file: Path) -> None:
        entry = ZipInfo(name, self.TIMESTAMP)
        entry.create_system = self.UNIX
        entry.external_attr = self.FILE_MODE << 16
        archive.writestr(entry, file.read_bytes())
