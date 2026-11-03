"""The plugin packed as one zip, for hosts that install it from a file.

The zip holds the same bytes whenever the plugin's files are the same. An output
folder or path it cannot write to is a Problem with the next step.
"""

import stat
from dataclasses import dataclass
from typing import ClassVar
from zipfile import ZipFile
from zipfile import ZipInfo
lazy from pathlib import Path

from nustack.problem import Problem
lazy from nustack.plugin.manifest import Manifest
lazy from nustack.tree import Tree


@dataclass(frozen=True)
class Bundle:
    """The plugin as one zip, identical whenever its files are."""

    UNIX: ClassVar[int] = 3
    FILE_MODE: ClassVar[int] = stat.S_IFREG | 0o644
    NOT_A_FOLDER: ClassVar[str] = (
        "is a file, not a folder; pass --out a folder, or remove the file"
    )
    tree: Tree
    manifest: Manifest

    @property
    def name(self) -> str:
        return f"{self.manifest.name}-{self.manifest.version}.zip"

    def write(self, folder: Path) -> Path | Problem:
        path = folder / self.name
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except FileExistsError:
            return Problem(folder, self.NOT_A_FOLDER)
        except OSError as error:
            return self.unwritable(folder, error)
        try:
            archive = ZipFile(path, "w")
        except OSError as error:
            if path.exists():
                return self.unwritable(path, error, "remove what is in its place, or ")
            return self.unwritable(folder, error)
        with archive:
            for name, file in self.tree.files.items():
                entry = ZipInfo(name.as_posix())
                entry.create_system = self.UNIX
                entry.external_attr = self.FILE_MODE << 16
                archive.writestr(entry, file.content)
        return path

    def unwritable(self, place: Path, error: OSError, removal: str = "") -> Problem:
        return Problem(
            place,
            f"cannot be written ({error.strerror}); "
            f"{removal}pass --out a folder you can write to",
        )
