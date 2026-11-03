"""A repository read from disk once, into the snapshot every check decides on.

The plugin folder is scanned without following a symlink; a symlink, or a folder
the disk will not list, leaves only those entries, so no check sees part of the
tree. Each file released beside the plugin reads as its kind, and the harness's
sources and tests as their paths beside each folder that would not list. A refusal
keeps the disk's reason, and a path that a file, a shut folder or a symlink loop
blocks names what blocks it.
"""

import errno
import stat
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath

from nustack.repository.repository import Repository
from nustack.tree import Blocked
from nustack.tree import Entry
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Missing
from nustack.tree import NotAFolder
from nustack.tree import Read
from nustack.tree import Snapshot
from nustack.tree import Special
from nustack.tree import Symlink
from nustack.tree import Tree
from nustack.tree import Unopened
from nustack.tree import Unreadable


@dataclass(frozen=True)
class Disk:
    """A repository on disk, read once into the values the checks take."""

    root: Path

    def snapshot(self) -> Snapshot:
        sources, unlisted_sources = self.listing(Repository.SOURCES)
        tests, unlisted_tests = self.listing(Repository.TESTS)
        return Snapshot(
            self.root,
            self.tree(self.root / Repository.PLUGIN),
            frozendict(
                (path, self.read(self.root / path)) for path in Repository.FILES
            ),
            sources,
            tests,
            frozendict(sorted((unlisted_sources | unlisted_tests).items())),
        )

    def tree(self, root: Path) -> Tree:
        if (unusable := self.unusable_root(root)) is not None:
            return Tree(root, frozendict({PurePosixPath("."): unusable}))
        entries: dict[PurePosixPath, Entry] = {}
        regular: list[PurePosixPath] = []
        pending = [root]
        while pending:
            folder = pending.pop()
            try:
                children = [
                    (listed, listed.lstat().st_mode) for listed in folder.iterdir()
                ]
            except OSError as error:
                entries[self.inside(root, folder)] = Unopened.of(error)
                children = []
            for child, mode in children:
                path = self.inside(root, child)
                if stat.S_ISDIR(mode):
                    entries[path] = Folder()
                    pending.append(child)
                elif stat.S_ISLNK(mode):
                    entries[path] = Symlink()
                elif stat.S_ISREG(mode):
                    regular.append(path)
                else:
                    entries[path] = Special()
        unsafe = {
            unsafe_path: entry
            for unsafe_path, entry in entries.items()
            if isinstance(entry, Symlink | Unopened)
        }
        if unsafe:
            return Tree(root, frozendict(sorted(unsafe.items())))
        for path in regular:
            entries[path] = self.load(root / path)
        return Tree(root, frozendict(sorted(entries.items())))

    @staticmethod
    def unusable_root(root: Path) -> Symlink | NotAFolder | Missing | Unopened | None:
        try:
            mode = root.lstat().st_mode
        except FileNotFoundError, NotADirectoryError:
            return Missing()
        except OSError as error:
            return Unopened.of(error)
        if stat.S_ISLNK(mode):
            return Symlink()
        if not stat.S_ISDIR(mode):
            return NotAFolder()
        return None

    @classmethod
    def read(cls, path: Path) -> Read:
        match cls.mode(path):
            case int() as mode if stat.S_ISDIR(mode):
                return Folder()
            case int() as mode if stat.S_ISREG(mode):
                return cls.load(path)
            case int():
                return Special()
            case refusal:
                return refusal

    @staticmethod
    def mode(path: Path) -> int | Missing | Blocked | Unreadable:
        for place in (*reversed(path.parents), path):
            try:
                mode = place.stat().st_mode
            except FileNotFoundError:
                return Missing()
            except PermissionError as error:
                return Unreadable(
                    f"cannot be read, since {place.parent} {Unopened.of(error).reason}"
                )
            except OSError as error:
                if error.errno != errno.ELOOP:
                    return Unreadable.of(error)
                return Unreadable(
                    f"cannot be read, since {place} is a symlink that leads back to"
                    " itself; point it at the file or folder it stands for"
                )
            if place != path and not stat.S_ISDIR(mode):
                return Blocked(
                    place,
                    File.IN_A_FOLDERS_PLACE
                    if stat.S_ISREG(mode)
                    else Special.IN_A_FOLDERS_PLACE,
                )
        return mode

    @staticmethod
    def load(path: Path) -> File | Unreadable:
        try:
            return File(path.read_bytes())
        except OSError as error:
            return Unreadable.of(error)

    def listing(
        self, folder: PurePosixPath
    ) -> tuple[tuple[PurePosixPath, ...], dict[PurePosixPath, Unopened]]:
        files: list[PurePosixPath] = []
        unlisted: dict[PurePosixPath, Unopened] = {}

        def refuse(error: OSError) -> None:
            if not isinstance(error, FileNotFoundError | NotADirectoryError):
                unlisted[self.inside(self.root, Path(error.filename))] = Unopened.of(
                    error
                )

        for parent, folders, names in (self.root / folder).walk(on_error=refuse):
            folders[:] = [name for name in folders if name != "__pycache__"]
            files += [
                self.inside(self.root, parent / name)
                for name in names
                if (parent / name).is_file()
            ]
        return tuple(sorted(files)), unlisted

    @staticmethod
    def inside(root: Path, path: Path) -> PurePosixPath:
        return PurePosixPath(path.relative_to(root).as_posix())
