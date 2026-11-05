"""The files a check reads, held in memory, so every check decides without I/O.

Each path reads as its kind: a file's bytes, a folder, a symlink no check follows,
any other entry, nothing, the entry above it that sits where a folder belongs, or
the disk's refusal with its reason. A snapshot holds what `nustack check` reads
from one repository.
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar
from typing import assert_never
lazy from pathlib import Path
lazy from pathlib import PurePosixPath


class Absent(ABC):
    """An entry where a file belongs that holds no file, naming why."""

    @abstractmethod
    def absence(self, missing: str) -> str: ...


@dataclass(frozen=True)
class File:
    """A regular file, as the bytes it holds."""

    IN_A_FOLDERS_PLACE: ClassVar[str] = (
        "is a file where a folder belongs; move the file, then add the folder"
    )
    content: bytes

    @cached_property
    def text(self) -> str | None:
        try:
            return self.content.decode()
        except UnicodeDecodeError:
            return None


@dataclass(frozen=True)
class Folder(Absent):
    """A folder that opened."""

    IN_A_FILES_PLACE: ClassVar[str] = (
        "is a folder where a file belongs; move the folder, then add the file"
    )

    def absence(self, missing: str) -> str:  # noqa: ARG002 -- Absent.absence's form
        return self.IN_A_FILES_PLACE


@dataclass(frozen=True)
class Symlink:
    """A symlink, which no check reads through."""


@dataclass(frozen=True)
class Special(Absent):
    """An entry that is neither a file, a folder nor a symlink, such as a pipe."""

    UNEXPECTED: ClassVar[str] = "is neither a file nor a folder; remove it"
    IN_PLACE_OF: ClassVar[str] = UNEXPECTED + ", then add the {}"
    IN_A_FILES_PLACE: ClassVar[str] = IN_PLACE_OF.format("file")
    IN_A_FOLDERS_PLACE: ClassVar[str] = IN_PLACE_OF.format("folder")

    def absence(self, missing: str) -> str:  # noqa: ARG002 -- Absent.absence's form
        return self.IN_A_FILES_PLACE


@dataclass(frozen=True)
class NotAFolder:
    """A file, or any entry but a folder, where a folder belongs."""


@dataclass(frozen=True)
class Missing(Absent):
    """A path that holds neither a regular file nor a folder."""

    def absence(self, missing: str) -> str:
        return missing


@dataclass(frozen=True)
class Blocked(Absent):
    """A path under an entry that sits where a folder belongs, named with its fix."""

    place: Path
    what: str

    def absence(self, missing: str) -> str:  # noqa: ARG002 -- Absent.absence's form
        return Unreadable.since(self.place, self.what).reason


@dataclass(frozen=True)
class Unreadable:
    """A file that would not open, and why."""

    reason: str

    @classmethod
    def of(cls, error: OSError) -> Unreadable:
        return cls(f"cannot be read ({error.strerror}); make it readable")

    @classmethod
    def since(cls, place: Path, what: str) -> Unreadable:
        return cls(f"cannot be read, since {place} {what}")


@dataclass(frozen=True)
class Unopened:
    """A folder whose entries would not list, and why."""

    reason: str

    @classmethod
    def of(cls, error: OSError) -> Unopened:
        return cls(
            f"cannot be opened ({error.strerror}); "
            "give the folder read and execute permission"
        )


type Entry = (
    File | Folder | Symlink | Special | NotAFolder | Missing | Unreadable | Unopened
)
type Read = File | Folder | Special | Missing | Blocked | Unreadable


@dataclass(frozen=True)
class Tree:
    """A folder and every entry under it, keyed by its path inside the folder.

    A scan that meets a symlink or a folder it cannot open holds only those
    entries, since reading on would go through the symlink or see part of the tree.
    The folder itself, when it is a symlink, no folder or missing, is the entry at `.`.
    """

    root: Path
    entries: frozendict[PurePosixPath, Entry]

    @cached_property
    def files(self) -> frozendict[PurePosixPath, File]:
        return frozendict(
            (path, entry)
            for path, entry in sorted(self.entries.items())
            if isinstance(entry, File)
        )

    def read(self, path: PurePosixPath) -> Read:
        match self.entries.get(path):
            case File() | Folder() | Special() | Unreadable() as found:
                return found
            case Symlink() | NotAFolder() | Missing() | Unopened() | None:
                for parent in reversed(path.parents[:-1]):
                    match self.entries.get(parent):
                        case File() | Unreadable():
                            return Blocked(self.root / parent, File.IN_A_FOLDERS_PLACE)
                        case Special():
                            return Blocked(
                                self.root / parent, Special.IN_A_FOLDERS_PLACE
                            )
                        case (
                            Folder()
                            | Symlink()
                            | NotAFolder()
                            | Missing()
                            | Unopened()
                            | None
                        ):
                            pass
                        case unexpected:
                            assert_never(unexpected)
                return Missing()
            case unexpected:
                assert_never(unexpected)


@dataclass(frozen=True)
class Snapshot:
    """What `nustack check` reads from a repository.

    That is the plugin, the files released beside it, and the paths of the
    harness's sources and tests, with each folder among them that would not list.
    """

    root: Path
    plugin: Tree
    files: frozendict[PurePosixPath, Read]
    sources: tuple[PurePosixPath, ...]
    tests: tuple[PurePosixPath, ...]
    unlisted: frozendict[PurePosixPath, Unopened]

    def read(self, path: PurePosixPath) -> Read:
        return self.files[path]
