"""A copy's files, read from Git's recursive tree listing.

Each path sits inside the copied folder, with its mode and object, the governing
license included, so two copies compare wherever each sits and find which upstream
revision a copy matches. A copy without its skill file or license, or holding a
symlink or a submodule, cannot be copied.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar
lazy from collections.abc import Iterable
lazy from pathlib import Path

from nustack.plugin.skill import Skill
from nustack.problem import Problem


class Mode(StrEnum):
    """The Git file modes a recursive tree listing holds."""

    REGULAR = "100644"
    EXECUTABLE = "100755"
    SYMLINK = "120000"
    SUBMODULE = "160000"


@dataclass(frozen=True)
class GitEntry:
    """A Git tree entry; the mode distinguishes equal bytes with different uses."""

    mode: Mode
    oid: str


@dataclass(frozen=True)
class CopyTree:
    """Holds a copy's Git entries with its license, to compare it with another copy.

    It finds the paths two copies differ in and the newest upstream revision a
    copy matches.
    """

    LICENSE: ClassVar[str] = "LICENSE"
    UNCOPIABLE: ClassVar[frozendict[Mode, str]] = frozendict(
        {Mode.SYMLINK: "a symlink", Mode.SUBMODULE: "a submodule"}
    )
    files: frozendict[str, GitEntry]

    @classmethod
    def from_listing(cls, listing: bytes, folder: str) -> CopyTree:
        entries: dict[str, GitEntry] = {}
        for record in listing.decode(errors="surrogateescape").split("\0")[:-1]:
            fields, path = record.split("\t", 1)
            mode, _, oid = fields.split()
            entries[path] = GitEntry(Mode(mode), oid)
        prefix = f"{folder}/"
        files = {
            file_path.removeprefix(prefix): entry
            for file_path, entry in entries.items()
            if file_path.startswith(prefix)
        }
        if cls.LICENSE in entries:
            files.setdefault(cls.LICENSE, entries[cls.LICENSE])
        return cls(frozendict(files))

    def changed_paths(self, other: CopyTree) -> tuple[str, ...]:
        return tuple(
            path
            for path in sorted(self.files.keys() | other.files.keys())
            if self.files.get(path) != other.files.get(path)
        )

    def newest_match(self, history: Iterable[tuple[str, CopyTree]]) -> str | None:
        if Skill.FILE not in self.files:
            return None
        return next((sha for sha, tree in history if self == tree), None)

    def problems(self, copy: Path) -> list[Problem]:
        missing = [
            Problem(copy / name, f"has no upstream source; {fix}")
            for name, fix in {
                Skill.FILE: "pass --source the skill's folder upstream",
                self.LICENSE: (
                    "upstream holds no LICENSE in the skill's folder or at its root;"
                    " ask the owner to raise it upstream"
                ),
            }.items()
            if name not in self.files
        ]
        return missing + [
            Problem(
                copy / path,
                f"is {self.UNCOPIABLE[entry.mode]} upstream, which no copy can hold;"
                " ask the owner to raise it upstream",
            )
            for path, entry in self.files.items()
            if entry.mode in self.UNCOPIABLE
        ]
