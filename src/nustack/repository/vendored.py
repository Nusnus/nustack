"""The vendored copies, which review reads as their sources wrote them.

Each copy's record names the skill folders the sync writes, and the bytes each file
there holds; every commit hook that rewrites files, Ruff, and Git's line-ending
conversion must skip those folders.
"""

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar
from typing import assert_never

from nustack.plugin.plugin import Plugin
from nustack.problem import Problem
from nustack.record import CopyRecord
from nustack.tree import Missing
from nustack.tree import NotAFolder
from nustack.tree import Special
from nustack.tree import Symlink
from nustack.tree import Unopened
from nustack.tree import Unreadable
lazy from nustack.github.name import RepositoryUrl
lazy from nustack.repository.gitattributes import GitAttributes
lazy from nustack.repository.hooks import Hooks
lazy from nustack.repository.pyproject import Pyproject
lazy from nustack.tree import Tree


@dataclass(frozen=True)
class VendoredCopies:
    """The vendored copies, each held to its record, which Ruff and the text hooks skip.

    Review reads each copy byte for byte as its source wrote it, so every skill
    folder a record names holds exactly the files the record lists, with the bytes
    of each, and no two records name one folder or folders inside each other. A
    record copies only into a skills folder a host reads, so no record makes the
    hooks, Ruff and Git skip other files; the check holds a record that names
    another folder to that alone. A record whose commit is null, before its first
    sync, names folders that do not exist yet, which the hooks, Ruff and Git skip
    already. A folder in a skills folder a copy lands in that holds a LICENSE but no
    record names is a copy a record dropped.
    """

    PLUGIN_SKILLS: ClassVar[PurePosixPath] = Plugin.FOLDER / Plugin.SKILLS
    DESTINATIONS: ClassVar[tuple[PurePosixPath, ...]] = (
        PurePosixPath(".agents/skills"),
        PLUGIN_SKILLS,
    )
    REWRITERS: ClassVar[tuple[str, ...]] = (
        "end-of-file-fixer",
        "fix-byte-order-marker",
        "mixed-line-ending",
        "trailing-whitespace",
        "markdownlint-cli2",
    )
    root: Path
    records: frozendict[PurePosixPath, CopyRecord]
    copies: frozendict[PurePosixPath, Tree]
    destination_files: tuple[PurePosixPath, ...]
    home: RepositoryUrl | None

    @cached_property
    def overlaps(self) -> tuple[tuple[PurePosixPath, PurePosixPath], ...]:
        return tuple(
            (path, other_path)
            for path, record in self.records.items()
            for other_path, other in self.records.items()
            if other_path != path
            and any(
                mine.is_relative_to(theirs) or theirs.is_relative_to(mine)
                for mine in record.skill_folders
                for theirs in other.skill_folders
            )
        )

    @cached_property
    def overlapping(self) -> frozenset[PurePosixPath]:
        return frozenset(path for path, _ in self.overlaps)

    @cached_property
    def placed(self) -> frozendict[PurePosixPath, CopyRecord]:
        return frozendict(
            (path, record)
            for path, record in self.records.items()
            if record.folder in self.DESTINATIONS
            and path not in self.overlapping
            and not self.is_home(record)
        )

    @cached_property
    def folders(self) -> tuple[PurePosixPath, ...]:
        return tuple(
            sorted(
                {
                    folder
                    for record in self.placed.values()
                    for folder in record.skill_folders
                }
            )
        )

    @cached_property
    def plugin_skills(self) -> frozenset[str]:
        return frozenset(
            skill
            for record in self.placed.values()
            if record.folder == self.PLUGIN_SKILLS
            for skill in record.skills
        )

    # A record left out of placed for its upstream still names its plugin folders,
    # so the plugin reads them as copies rather than as leftovers.
    @cached_property
    def recorded_plugin_skills(self) -> frozenset[str]:
        return frozenset(
            skill
            for record in self.records.values()
            if record.folder == self.PLUGIN_SKILLS
            for skill in record.skills
        )

    @property
    def exclude(self) -> str | None:
        if not self.folders:
            return None
        return "^(?:" + "|".join(re.escape(str(path)) for path in self.folders) + ")/"

    @property
    def unset_text(self) -> tuple[str, ...]:
        return tuple(f"{folder}/** -text" for folder in self.folders)

    def problems(
        self,
        hooks: Hooks | None,
        pyproject: Pyproject | None,
        attributes: GitAttributes | None,
    ) -> list[Problem]:
        problems = [
            *self.place_problems(),
            *self.upstream_problems(),
            *(
                problem
                for path, record in self.placed.items()
                for problem in self.copy_problems(path, record)
            ),
        ]
        # A record that names no skills folder a host reads, a skill folder another
        # record names, or this repository as its upstream, has no folder the hooks
        # and Ruff could skip, so its folder or upstream problem stands alone.
        if len(self.placed) < len(self.records):
            return problems
        if hooks is not None:
            problems += self.hook_problems(hooks)
        if pyproject is not None:
            problems += self.ruff_problems(pyproject)
        if attributes is not None:
            problems += self.attribute_problems(attributes)
        return problems

    # The sync copies one record, so it stops on that record's own place or
    # upstream problem, as nustack check would.
    def record_problems(self, path: PurePosixPath) -> list[Problem]:
        return [
            problem
            for problem in (*self.place_problems(), *self.upstream_problems())
            if problem.where == self.root / path
        ]

    def place_problems(self) -> list[Problem]:
        destinations = " or ".join(str(folder) for folder in self.DESTINATIONS)
        problems = [
            Problem(
                self.root / path,
                f"folder and skills: names a skill folder that {other_path} names too,"
                " or one inside it or around it; give each skill folder one record",
            )
            for path, other_path in self.overlaps
        ]
        return problems + [
            Problem(
                self.root / path,
                f"folder: names no skills folder a host reads; set it to"
                f" {destinations}",
            )
            for path, record in self.records.items()
            if record.folder not in self.DESTINATIONS
        ]

    # The plugin names each leftover in its own skills folder, since its rules for
    # authored skills skip that folder too; this names each one elsewhere.
    def leftover_problems(self) -> list[Problem]:
        recorded = {
            folder
            for record in self.records.values()
            for folder in record.skill_folders
        }
        return [
            Problem(self.root / path.parent, Plugin.LEFTOVER)
            for path in self.destination_files
            if path.name == CopyRecord.LICENSE
            and path.parent.parent in self.DESTINATIONS
            and path.parent not in recorded
        ]

    # A copy folder that holds a symlink or will not open reads as only those
    # entries, as the plugin folder does, so nothing else in it is compared.
    def copy_problems(self, path: PurePosixPath, record: CopyRecord) -> list[Problem]:
        fix = (
            "rerun the sync workflow, or remove every folder the record"
            f" {path} names until the first sync"
            if record.commit is None
            else "rerun the sync workflow, or restore the copy from the commit the"
            f" record {path} names"
        )
        if record.commit is None and all(
            isinstance(self.copies[folder].entries.get(PurePosixPath(".")), Missing)
            for folder in record.skill_folders
        ):
            return []
        problems: list[Problem] = []
        for skill in record.skills:
            folder = self.root / record.skill_folder(skill)
            tree = self.copies[record.skill_folder(skill)]
            blocking = [
                self.blocking_problem(folder / entry_path, entry, fix)
                for entry_path, entry in tree.entries.items()
                if isinstance(entry, Symlink | NotAFolder | Missing | Unopened)
            ]
            if blocking:
                problems += blocking
                continue
            recorded = record.files_of(skill)
            held = {
                str(file_path): CopyRecord.blob(file.content)
                for file_path, file in tree.files.items()
            }
            unreadable = {
                str(entry_path): entry
                for entry_path, entry in tree.entries.items()
                if isinstance(entry, Unreadable)
            }
            special = {
                str(entry_path)
                for entry_path, entry in tree.entries.items()
                if isinstance(entry, Special)
            }
            problems += [
                Problem(folder / name, f"is missing from the copy; {fix}")
                for name in sorted(
                    recorded.keys() - held.keys() - unreadable.keys() - special
                )
            ]
            problems += [
                Problem(
                    folder / name,
                    f"is not in the copy its record lists; remove it, or {fix}",
                )
                for name in sorted(held.keys() - recorded.keys())
            ]
            problems += [
                Problem(
                    folder / name,
                    f"differs from upstream's bytes its record lists; {fix}",
                )
                for name in sorted(held.keys() & recorded.keys())
                if held[name] != recorded[name]
            ]
            problems += [
                Problem(folder / name, entry.reason)
                for name, entry in sorted(unreadable.items())
            ]
            problems += [
                Problem(
                    folder / entry_path,
                    f"is no file the copy can hold; remove it, or {fix}",
                )
                for entry_path in sorted(special)
            ]
        return problems

    @staticmethod
    def blocking_problem(
        where: Path, entry: Symlink | NotAFolder | Missing | Unopened, fix: str
    ) -> Problem:
        match entry:
            case Missing():
                return Problem(where, f"is missing; {fix}")
            case NotAFolder():
                return Problem(where, f"{Problem.NOT_A_FOLDER}; remove it, then {fix}")
            case Symlink():
                return Problem(
                    where,
                    f"is a symlink, which a copy cannot hold; remove it, then {fix}",
                )
            case Unopened(reason=reason):
                return Problem(where, reason)
            case unexpected:
                assert_never(unexpected)

    # A skill copied from nustack is one its authors write, so no record holds it.
    # The check knows this repository only by its manifests' URL, so a record that
    # names it by another URL, such as an old owner's, passes; review holds that.
    def upstream_problems(self) -> list[Problem]:
        return [
            Problem(
                self.root / path,
                "upstream: names this repository, whose skills its authors write;"
                " remove the record and keep the skills as authored ones",
            )
            for path, record in self.records.items()
            if self.is_home(record)
        ]

    def is_home(self, record: CopyRecord) -> bool:
        return self.home is not None and self.repository_key(
            record.upstream
        ) == self.repository_key(self.home)

    @staticmethod
    def repository_key(url: RepositoryUrl) -> tuple[str, str, str]:
        owner_name = url.name_with_owner
        return (
            url.host.casefold().removeprefix("www."),
            owner_name.owner.casefold(),
            owner_name.name.casefold(),
        )

    def hook_problems(self, hooks: Hooks) -> list[Problem]:
        ids = {hook.id for hook in hooks.hooks}
        fix = (
            "set its exclude to ^(?:, then each vendored skill folder passed through"
            " Python's re.escape, sorted and joined by |, then )/"
        )
        return [
            *(
                Problem(
                    self.root / Hooks.PATH,
                    f"has no {name} hook; restore it, with an exclude of the vendored"
                    " skill folders",
                )
                for name in self.REWRITERS
                if name not in ids
            ),
            *(
                Problem(
                    self.root / Hooks.PATH,
                    f"has the {name} hook skip other folders than the vendored skill"
                    f" folders; {fix}",
                )
                for name in self.REWRITERS
                if self.exclude is not None
                and any(
                    hook.id == name
                    and hook.exclude is not None
                    and hook.exclude != self.exclude
                    for hook in hooks.hooks
                )
            ),
            *(
                Problem(
                    self.root / Hooks.PATH,
                    f"has the {name} hook skip files though no record names a"
                    " vendored skill folder; remove its exclude",
                )
                for name in self.REWRITERS
                if self.exclude is None
                and any(
                    hook.id == name and hook.exclude is not None for hook in hooks.hooks
                )
            ),
            *(
                Problem(
                    self.root / Hooks.PATH,
                    f"has the {name} hook skip none of the vendored skill folders;"
                    f" {fix}",
                )
                for name in self.REWRITERS
                if self.exclude is not None
                and any(
                    hook.id == name and hook.exclude is None for hook in hooks.hooks
                )
            ),
        ]

    def ruff_problems(self, pyproject: Pyproject) -> list[Problem]:
        skipped = {
            skip.removesuffix("/") for skip in pyproject.tool.ruff.extend_exclude
        }
        if skipped == {str(folder) for folder in self.folders}:
            return []
        if not self.folders:
            return [
                Problem(
                    self.root / Pyproject.PATH,
                    "has a [tool.ruff] extend-exclude though no record names a"
                    " vendored skill folder; remove extend-exclude",
                )
            ]
        return [
            Problem(
                self.root / Pyproject.PATH,
                "has a [tool.ruff] extend-exclude other than the vendored skill"
                " folders; set it to exactly the folders the records name",
            )
        ]

    # A later line overrides an earlier one, so the lines that unset text for the
    # copies come last, after plugin/'s line that sets it:
    # https://git-scm.com/docs/gitattributes#_description
    def attribute_problems(self, attributes: GitAttributes) -> list[Problem]:
        lines = attributes.lines
        unsetting = tuple(line for line in lines if "-text" in line.split()[1:])
        ending = lines[len(lines) - len(self.unset_text) :]
        if unsetting == ending == self.unset_text:
            return []
        if not self.folders:
            return [
                Problem(
                    self.root / GitAttributes.PATH,
                    "unsets text though no record names a vendored skill folder;"
                    " remove each -text",
                )
            ]
        return [
            Problem(
                self.root / GitAttributes.PATH,
                "does not end on a line <folder>/** -text for each vendored skill"
                " folder, sorted, with no other line unsetting text; end it on"
                " exactly those lines, so Git keeps each copy's bytes",
            )
        ]
