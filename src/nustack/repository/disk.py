"""A repository read from disk once, into the snapshot every check decides on.

The plugin folder, and each skill folder a vendored copy's record names, is scanned
without following a symlink; a symlink, or a folder the disk will not list, leaves
only those entries, so no check sees part of the tree. Each file released beside
the plugin, and each record, reads as its kind, and the harness's sources and tests
as their paths beside each folder that would not list. A refusal keeps the disk's
reason, and a path that a file, a shut folder or a symlink loop blocks names what
blocks it. In a Git repository, every scan and listing leaves out each untracked
path Git ignores below the folder it starts from, and all that path holds, such as a
.DS_Store Finder leaves, so the check, and the zip it lets through, skip it.
"""

import errno
import stat
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath

from nustack.git import Git
from nustack.plugin.plugin import Plugin
from nustack.record import CopyRecord
from nustack.repository.repository import Repository
from nustack.repository.vendored import VendoredCopies
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
    """A repository on disk, read once into the values the checks take.

    Each path in ignored, relative to the root, is left out with all it holds, unless
    a scan or listing starts from it.
    """

    root: Path
    ignored: frozenset[PurePosixPath] = frozenset()

    # Git ignores a path only in a repository, which holds .git at its top; Git's
    # failure to list them raises GitError.
    @classmethod
    def of(cls, root: Path) -> Disk:
        if not (root / ".git").exists():
            return cls(root)
        return cls(root, Git(root).ignored())

    def snapshot(self) -> Snapshot:
        sources, unlisted_sources = self.listing(Repository.SOURCES)
        tests, unlisted_tests = self.listing(Repository.TESTS)
        listed, unlisted_records = self.listing(CopyRecord.FOLDER)
        records = frozendict(
            (path, self.read_record(self.root / path))
            for path in sorted({*listed, *self.globbed(CopyRecord.FOLDER)})
        )
        copied = self.skill_folders(records)
        listings = [
            self.listing(folder)
            for folder in VendoredCopies.DESTINATIONS
            if not folder.is_relative_to(Plugin.FOLDER)
        ]
        # A symlink holds no file of its own, so it marks no leftover copy.
        destination_files = tuple(
            path
            for files, _ in listings
            for path in files
            if not (self.root / path).is_symlink()
        )
        # Each copy's own tree names a folder in it that will not open.
        unlisted_destinations = {
            path: unopened
            for _, unlisted in listings
            for path, unopened in unlisted.items()
            if not any(path.is_relative_to(copy) for copy in copied)
        }
        return Snapshot(
            self.root,
            self.tree(self.root / Plugin.FOLDER),
            frozendict(
                (path, self.read(self.root / path)) for path in Repository.FILES
            ),
            sources,
            tests,
            frozendict(
                sorted(
                    (
                        unlisted_sources
                        | unlisted_tests
                        | unlisted_records
                        | unlisted_destinations
                    ).items()
                )
            ),
            records,
            frozendict(
                (folder, self.tree(self.root / folder)) for folder in sorted(copied)
            ),
            destination_files,
        )

    # Only the folders a valid record names in a destination are read. Each record
    # is parsed again, beside Repository.record_readings, on purpose: Disk reads
    # bytes and never Problems, so the snapshot it returns, like the model
    # repository's, holds the records unparsed, and the check names each record it
    # cannot read from that snapshot alone.
    @staticmethod
    def skill_folders(records: frozendict[PurePosixPath, Read]) -> set[PurePosixPath]:
        folders: set[PurePosixPath] = set()
        for path, read in records.items():
            # The folders drop each Problem, so the path and fix it names never show.
            reading = CopyRecord.reading(  # pragma: no mutate
                Path(), path, read, CopyRecord.MISSING
            )
            if (
                isinstance(reading, CopyRecord)
                and reading.folder in VendoredCopies.DESTINATIONS
            ):
                folders |= set(reading.skill_folders)
        return folders

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
                    (listed, listed.lstat().st_mode)
                    for listed in folder.iterdir()
                    if self.inside(self.root, listed) not in self.ignored
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

    # The sync workflow's glob follows a symlink, so a record, like the plugin, is
    # read only where it and its folder are themselves.
    @classmethod
    def read_record(cls, path: Path) -> Read:
        if path.parent.is_symlink():
            return Unreadable.since(path.parent, CopyRecord.FOLDER_SYMLINK)
        if path.is_symlink():
            return Unreadable(CopyRecord.SYMLINK)
        return cls.read(path)

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
                return Unreadable.since(place.parent, Unopened.of(error).reason)
            except OSError as error:
                if error.errno != errno.ELOOP:
                    return Unreadable.of(error)
                return Unreadable.since(
                    place,
                    "is a symlink that leads back to itself; point it at the file or"
                    " folder it stands for",
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
            folders[:] = [
                name
                for name in folders
                if name != "__pycache__"
                and self.inside(self.root, parent / name) not in self.ignored
            ]
            files += [
                path
                for name in names
                if (path := self.inside(self.root, parent / name)) not in self.ignored
                and (parent / name).is_file()
            ]
        return tuple(sorted(files)), unlisted

    # The sync workflow globs <folder>/*.json, so it reaches an entry there that is
    # no regular file too, which the check then reads and reports.
    def globbed(self, folder: PurePosixPath) -> tuple[PurePosixPath, ...]:
        return tuple(
            inside
            for path in (self.root / folder).glob(f"*{CopyRecord.SUFFIX}")
            if (inside := self.inside(self.root, path)) not in self.ignored
        )

    @staticmethod
    def inside(root: Path, path: Path) -> PurePosixPath:
        return PurePosixPath(path.relative_to(root).as_posix())
