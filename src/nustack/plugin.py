"""The rules that span the whole plugin rather than one skill or document."""

import stat
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import ClassVar
from typing import NamedTuple

from nustack.document import Document
from nustack.manifest import InvalidMetadataError
from nustack.manifest import Manifest
from nustack.problem import Problem
from nustack.problem import cannot_open
from nustack.problem import cannot_read
from nustack.skill import Kind
from nustack.skill import Skill


class Scan(NamedTuple):
    """Every path under the plugin, and a problem per folder that would not open."""

    paths: list[Path]
    unopened: list[Problem]


@dataclass
class Plugin:
    """The folder a host installs: its manifests and its skills."""

    MANIFESTS: ClassVar[frozendict[str, str]] = frozendict(
        {
            ".devin-plugin/plugin.json": "Devin",
            ".claude-plugin/plugin.json": "Claude Code",
            ".cursor-plugin/plugin.json": "Cursor",
        }
    )
    LICENSE: ClassVar[str] = "LICENSE"
    LOADER: ClassVar[str] = "opencode.ts"
    OPENCODE: ClassVar[tuple[str, ...]] = (LOADER, "package.json")
    SYMLINK: ClassVar[str] = (
        "is a symlink, which the check never reads through, so it stops here; "
        "put the file itself here, or close the editor whose lock file it is"
    )
    root: Path

    @cached_property
    def manifest_readings(self) -> tuple[Manifest | Problem, ...]:
        return tuple(
            self.read_manifest(self.root / relative) for relative in self.MANIFESTS
        )

    @cached_property
    def manifests(self) -> tuple[Manifest, ...]:
        return tuple(
            reading
            for reading in self.manifest_readings
            if isinstance(reading, Manifest)
        )

    @cached_property
    def manifest(self) -> Manifest:
        return self.manifests[0]

    @property
    def skills_folder(self) -> Path:
        return self.root / "skills"

    @cached_property
    def skills(self) -> list[Skill]:
        return [
            Skill(folder)
            for folder in sorted(self.skills_folder.iterdir())
            if folder.is_dir()
        ]

    @cached_property
    def playbooks(self) -> list[Path]:
        return sorted(
            path
            for skill in self.skills
            if skill.kind is Kind.MODE
            for path in (skill.folder / "playbooks").glob("*.md")
            if path.is_file()
        )

    @cached_property
    def scan(self) -> Scan:
        return walk(self.root)

    @property
    def unopened(self) -> list[Problem]:
        return self.scan.unopened

    @cached_property
    def links(self) -> list[Path]:
        return sorted(
            (path for path in self.scan.paths if path.is_symlink()), key=Path.as_posix
        )

    @property
    def is_unsafe_to_read(self) -> bool:
        return self.root.is_symlink() or bool(self.links) or bool(self.unopened)

    @cached_property
    def files(self) -> list[Path]:
        return sorted(
            (path for path in self.scan.paths if path.is_file()), key=Path.as_posix
        )

    @cached_property
    def specials(self) -> list[Path]:
        return sorted(
            (
                path
                for path in self.scan.paths
                if not (path.is_file() or path.is_dir() or path.is_symlink())
            ),
            key=Path.as_posix,
        )

    @cached_property
    def documents(self) -> list[Document]:
        return [Document(path) for path in self.files if path.suffix == ".md"]

    @cached_property
    def unreadable(self) -> dict[Path, str]:
        return {
            document.path: reason
            for document in self.documents
            if (reason := document.unreadable) is not None
        }

    @cached_property
    def manifest_problems(self) -> list[Problem]:
        problems = [
            reading
            for reading in self.manifest_readings
            if isinstance(reading, Problem)
        ]
        valid = [
            (relative, reading)
            for relative, reading in zip(
                self.MANIFESTS, self.manifest_readings, strict=True
            )
            if isinstance(reading, Manifest)
        ]
        if not valid:
            return problems
        (first, reference), *others = valid
        host = self.MANIFESTS[first]
        return problems + [
            Problem(
                self.root / relative,
                f"differs from the {host} manifest in "
                f"{self.differing_fields(reference, other)}; "
                f"make it identical to the {host} manifest",
            )
            for relative, other in others
            if other != reference
        ]

    def problems(self) -> list[Problem]:
        if self.root.is_symlink():
            return [Problem(self.root, self.SYMLINK)]
        if self.links or self.unopened:
            return [
                *(Problem(path, self.SYMLINK) for path in self.links),
                *self.unopened,
            ]
        problems = [
            *self.manifest_problems,
            *self.license_problems(),
            *self.loader_problems(),
        ]
        if not self.skills_folder.is_dir():
            return [
                *problems,
                Problem(
                    self.skills_folder, "is missing; add it with the plugin's skills"
                ),
            ]
        problems += self.file_problems()
        problems += [
            Problem(path, "is neither a file nor a folder; remove it")
            for path in self.specials
        ]
        problems += [
            Problem(path, reason) for path, reason in sorted(self.unreadable.items())
        ]
        problems += [
            *skill.problems()
            for skill in self.skills
            if skill.document.path not in self.unreadable
        ]
        problems += self.mode_problems()
        problems += [
            *document.link_problems(self.root)
            for document in self.documents
            if document.path not in self.unreadable
        ]
        return problems

    def loader_problems(self) -> list[Problem]:
        path = self.root / self.LOADER
        if not path.is_file():
            return [
                Problem(
                    path,
                    "is missing; restore it from the repository, "
                    "so OpenCode can load the plugin",
                )
            ]
        try:
            _ = path.read_bytes()
        except OSError as error:
            return [Problem(path, cannot_read(error))]
        return []

    def differing_fields(self, reference: Manifest, other: Manifest) -> str:
        return ", ".join(
            field
            for field in Manifest.model_fields
            if getattr(reference, field) != getattr(other, field)
        )

    def read_manifest(self, path: Path) -> Manifest | Problem:
        if not path.is_file():
            return Problem(
                path, "is missing; add it, since its host installs the plugin from it"
            )
        try:
            return Manifest.read(path)
        except InvalidMetadataError as error:
            return Problem(path, f"is invalid: {error}")

    def file_problems(self) -> list[Problem]:
        expected = {self.root / relative for relative in self.MANIFESTS}
        expected |= {self.root / name for name in (self.LICENSE, *self.OPENCODE)}
        expected |= {skill.document.path for skill in self.skills}
        expected |= set(self.playbooks)
        return [
            Problem(
                path,
                "is not Markdown; remove it or move it out of the plugin, "
                "which holds only the host manifests, skills, playbooks, the OpenCode "
                "loader with its package.json, and a LICENSE",
            )
            if path.suffix != ".md"
            else Problem(
                path,
                "is neither a skill's SKILL.md nor a playbook; "
                "move it into the mode's playbooks folder or out of the plugin",
            )
            for path in self.files
            if path not in expected
        ]

    def license_problems(self) -> list[Problem]:
        if not (self.root / self.LICENSE).is_file():
            return [
                Problem(
                    self.root / self.LICENSE,
                    "is missing; copy the repository's LICENSE here",
                )
            ]
        return []

    def mode_problems(self) -> list[Problem]:
        modes = [skill for skill in self.skills if skill.kind is Kind.MODE]
        if len(modes) != 1:
            return [
                Problem(
                    self.skills_folder,
                    f"holds {len(modes)} modes, where it needs exactly 1; "
                    f"keep one skill folder without the {Skill.PRINCIPLE_PREFIX!r} "
                    "prefix",
                )
            ]
        (mode,) = modes
        if not mode.document.path.is_file() or mode.document.path in self.unreadable:
            return []
        indexed = mode.document.targets
        principles = {
            skill.document.path.resolve()
            for skill in self.skills
            if skill.kind is Kind.PRINCIPLE
        }
        playbooks = {path.resolve() for path in self.playbooks}
        return [
            Problem(
                mode.document.path,
                f"does not index {path}; add a link to it with when it applies",
            )
            for path in sorted((principles | playbooks) - indexed)
        ]


def walk(root: Path) -> Scan:
    found: list[Path] = []
    unopened: list[Problem] = []
    pending = [root] if root.is_dir() else []
    while pending:
        folder = pending.pop()
        try:
            children = list(folder.iterdir())
            modes = [child.lstat().st_mode for child in children]
        except OSError as error:
            unopened.append(Problem(folder, cannot_open(error)))
            continue
        found += children
        pending += [
            child
            for child, mode in zip(children, modes, strict=True)
            if stat.S_ISDIR(mode)
        ]
    return Scan(found, sorted(unopened, key=lambda problem: problem.where.as_posix()))
