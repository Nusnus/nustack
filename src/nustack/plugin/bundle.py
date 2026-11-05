"""The plugin packed as one zip, for hosts that install it from a file.

The zip holds the same bytes whenever the plugin's files are the same, and lands
whole or not at all for every reader and for a run that stops: it is written to a
`.<zip name>.<random>.partial` file beside it, removed on any failure or interrupt, so
only a killed run, such as one sent SIGKILL, can leave one. It is not flushed to disk,
so a machine crash can leave a cut zip, which a rerun rebuilds. A zip folder or zip
path it cannot write to is a Problem with the next step.
"""

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
from zipfile import ZipFile
from zipfile import ZipInfo

from nustack.problem import Problem
lazy from nustack.plugin.manifest import Manifest
lazy from nustack.tree import Tree


@dataclass(frozen=True)
class Bundle:
    """The plugin as one zip, whole to its readers, identical whenever its files are."""

    UNIX: ClassVar[int] = 3
    FILE_MODE: ClassVar[int] = stat.S_IFREG | 0o644
    # tempfile makes its file readable by its owner alone; the zip is for anyone:
    # https://docs.python.org/3/library/tempfile.html#tempfile.mkstemp
    ZIP_MODE: ClassVar[int] = 0o644
    NOT_A_FOLDER: ClassVar[str] = (
        "is a file, not a folder; pass --zip-folder a folder, or remove the file"
    )
    tree: Tree
    manifest: Manifest

    @property
    def name(self) -> str:
        return f"{self.manifest.name}-{self.manifest.version}.zip"

    def write(self, zip_folder: Path) -> Path | Problem:
        path = zip_folder / self.name
        try:
            zip_folder.mkdir(parents=True, exist_ok=True)
        except FileExistsError:
            return Problem(zip_folder, self.NOT_A_FOLDER)
        except OSError as error:
            return self.unwritable(zip_folder, error)
        try:
            descriptor, location = tempfile.mkstemp(
                prefix=f".{self.name}.", suffix=".partial", dir=zip_folder
            )
        except OSError as error:
            return self.unwritable(zip_folder, error)
        partial = Path(location)
        try:
            os.close(descriptor)
            try:
                with ZipFile(partial, "w") as archive:
                    for name, file in self.tree.files.items():
                        entry = ZipInfo(name.as_posix())
                        # ZipInfo sets 0 (MS-DOS) on Windows and 3 (Unix) elsewhere,
                        # so the zip is the same from every OS only when set:
                        # https://github.com/python/cpython/blob/v3.15.2/Lib/zipfile/__init__.py#L468-L472
                        entry.create_system = self.UNIX
                        entry.external_attr = self.FILE_MODE << 16
                        archive.writestr(entry, file.content)
                partial.chmod(self.ZIP_MODE)
            except OSError as error:
                return self.unwritable(zip_folder, error)
            try:
                partial.replace(path)
            except OSError as error:
                return self.unwritable(path, error, "remove what is in its place, or ")
        finally:
            # Once the move lands the partial name is gone, so this acts only on a
            # failure; a flag for success would add a branch no test can tell apart.
            partial.unlink(missing_ok=True)
        return path

    @staticmethod
    def unwritable(place: Path, error: OSError, removal: str = "") -> Problem:
        return Problem(
            place,
            f"cannot be written ({error.strerror}); "
            f"{removal}pass --zip-folder a folder you can write to",
        )
