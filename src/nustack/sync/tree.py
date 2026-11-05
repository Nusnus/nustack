"""A copy's files, read from Git's recursive tree listing.

Each path sits inside one copied skill's folder, named from the folder that holds
the skills, with its mode and object, each skill's governing license included, so
two copies compare wherever each sits. A skill without its skill file or license,
or a copy holding a symlink, a submodule or a file named with a character other
than a letter, digit, ., _ or -, cannot be copied.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
from typing import ClassVar
lazy from collections.abc import Iterable
lazy from pathlib import Path

from nustack.plugin.skill import Skill
from nustack.problem import Problem
from nustack.record import CopyRecord
from nustack.record import file_path


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
    """Holds a copy's Git entries with each skill's license, to compare two copies.

    It finds the paths two copies differ in, and the blobs a record holds.
    """

    LICENSE: ClassVar[str] = CopyRecord.LICENSE
    UNCOPIABLE: ClassVar[frozendict[Mode, str]] = frozendict(
        {Mode.SYMLINK: "a symlink", Mode.SUBMODULE: "a submodule"}
    )
    UNNAMEABLE: ClassVar[str] = (
        "a file named with a character other than a letter, digit, ., _ or -"
    )
    files: frozendict[str, GitEntry]

    # Each skill folder, wherever it sits, copies to a folder of its own name.
    @classmethod
    def from_listing(cls, listing: bytes, folders: Iterable[str]) -> CopyTree:
        entries: dict[str, GitEntry] = {}
        for record in listing.decode(errors="surrogateescape").split("\0")[:-1]:
            fields, path = record.split("\t", 1)
            mode, _, oid = fields.split()
            entries[path] = GitEntry(Mode(mode), oid)
        files: dict[str, GitEntry] = {}
        for folder in folders:
            skill = PurePosixPath(folder).name
            prefix = f"{folder}/"
            files |= {
                f"{skill}/{file_path.removeprefix(prefix)}": entry
                for file_path, entry in entries.items()
                if file_path.startswith(prefix)
            }
            if cls.LICENSE in entries:
                files.setdefault(f"{skill}/{cls.LICENSE}", entries[cls.LICENSE])
        return cls(frozendict(sorted(files.items())))

    @property
    def blobs(self) -> frozendict[str, str]:
        return frozendict((path, entry.oid) for path, entry in self.files.items())

    def changed_paths(self, other: CopyTree) -> tuple[str, ...]:
        return tuple(
            path
            for path in sorted(self.files.keys() | other.files.keys())
            if self.files.get(path) != other.files.get(path)
        )

    # A skill upstream renamed shows among the new skills, which the fix names.
    def problems(
        self, checkout: Path, record: CopyRecord, new_skills: tuple[str, ...]
    ) -> list[Problem]:
        copy_folder = checkout / record.folder
        candidates = (
            f" (upstream holds {', '.join(new_skills)}, which the record does not list)"
            if new_skills
            else ""
        )
        missing = [
            Problem(copy_folder / skill / name, f"has no upstream source; {fix}")
            for skill in record.skills
            for name, fix in {
                Skill.FILE: (
                    "set the record's source to the upstream folder that holds the"
                    " skill's folder, rename the skill in the record's skills to"
                    f" upstream's new name as AGENTS.md says{candidates}, or drop the"
                    " skill from the record's skills"
                ),
                self.LICENSE: (
                    "upstream holds no LICENSE in the skill's folder or at its root;"
                    " ask the owner to raise it upstream"
                ),
            }.items()
            # A skill with no SKILL.md upstream is gone or renamed, so its LICENSE
            # is missing for that one reason.
            if f"{skill}/{name}" not in self.files
            and (name == Skill.FILE or f"{skill}/{Skill.FILE}" in self.files)
        ]
        uncopiable = {
            (path.partition("/")[0], kind): None
            for path, entry in self.files.items()
            for kind in self.uncopiable(path, entry)
        }
        return missing + [
            Problem(
                copy_folder / skill,
                f"holds, upstream, {kind}, which no copy can hold; ask the owner to"
                " raise it upstream",
            )
            for skill, kind in uncopiable
        ]

    # A record holds a path only in the characters its schema takes, which leave
    # out every byte of a name that is not UTF-8.
    def uncopiable(self, path: str, entry: GitEntry) -> tuple[str, ...]:
        kinds = (self.UNCOPIABLE[entry.mode],) if entry.mode in self.UNCOPIABLE else ()
        try:
            _ = file_path(path)
        except ValueError:
            return (*kinds, self.UNNAMEABLE)
        return kinds
