"""The rules the plugin folder keeps as a whole, beyond any one skill.

No check reads through an entry that could lead outside it. It holds only the files
nustack ships, each of the kind it should be. Its manifests agree, its mode indexes
every skill, each playbook step ends on a done condition, its skill text holds on
every host and every day, and every link resolves.
"""

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar
from typing import assert_never

from nustack.markdown.document import Document
from nustack.plugin.manifest import Exports
from nustack.plugin.manifest import InvalidMetadataError
from nustack.plugin.manifest import Manifest
from nustack.plugin.skill import Kind
from nustack.plugin.skill import Skill
from nustack.problem import Problem
from nustack.tree import Absent
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Missing
from nustack.tree import NotAFolder
from nustack.tree import Special
from nustack.tree import Symlink
from nustack.tree import Tree
from nustack.tree import Unopened
from nustack.tree import Unreadable


@dataclass(frozen=True)
class Plugin:
    """The folder a host installs: its manifests, its skills and its loader.

    Its manifest is the one the release files match: every valid manifest, when
    they agree. A manifest that differs from the first in a field other than its
    version is named here; the repository names a differing version, since it
    compares versions across every file that holds one.
    """

    MANIFESTS: ClassVar[frozendict[PurePosixPath, str]] = frozendict(
        {
            PurePosixPath(".devin-plugin/plugin.json"): "Devin",
            PurePosixPath(".claude-plugin/plugin.json"): "Claude Code",
            PurePosixPath(".cursor-plugin/plugin.json"): "Cursor",
        }
    )
    LICENSE: ClassVar[PurePosixPath] = PurePosixPath("LICENSE")
    LOADER: ClassVar[PurePosixPath] = Exports.LOADER
    PACKAGE: ClassVar[PurePosixPath] = PurePosixPath("package.json")
    HOOKS: ClassVar[tuple[PurePosixPath, ...]] = (
        PurePosixPath("hooks/hooks.json"),
        PurePosixPath("hooks/reload-nus-mode.sh"),
    )
    SKILLS: ClassVar[PurePosixPath] = PurePosixPath("skills")
    PLAYBOOKS: ClassVar[str] = "playbooks"
    SYMLINK: ClassVar[str] = (
        "is a symlink, which the check never reads through, so it stops here; "
        "put the file itself here, or close the editor whose lock file it is"
    )
    NOT_A_FOLDER: ClassVar[str] = (
        f"{Problem.NOT_A_FOLDER}; replace it with the plugin folder"
    )
    MISSING: ClassVar[str] = (
        "is missing, so the check stops here; restore the plugin folder from the"
        " repository"
    )
    MODE_NAME: ClassVar[re.Pattern[str]] = re.compile(
        r"\b[a-z0-9]+(?:-[a-z0-9]+)*-mode\b"
    )
    HOST: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(?:Devin|Claude|Cursor|OpenCode|Codex|Copilot|Gemini|GPT|Windsurf"
        r"|Anthropic|OpenAI)\b|(?<![\w.])\.(?:claude|cursor|devin|opencode|codex)\b"
    )
    DATE: ClassVar[re.Pattern[str]] = re.compile(
        r"\b[0-9]{4}-[0-9]{2}-[0-9]{2}\b|\b(?:19|20)[0-9]{2}\b"
    )
    DONE: ClassVar[str] = "Done when"
    # Claude Code caps a hook's plain stdout at this many characters; the reload
    # hook adds a preamble and the mode's folder to the body, which HOOK_ROOM leaves
    # room for: https://code.claude.com/docs/en/hooks#json-output
    HOOK_OUTPUT: ClassVar[int] = 10_000
    HOOK_ROOM: ClassVar[int] = 1_000
    tree: Tree

    @property
    def root(self) -> Path:
        return self.tree.root

    @property
    def unsafe(
        self,
    ) -> tuple[tuple[PurePosixPath, Symlink | NotAFolder | Missing | Unopened], ...]:
        return tuple(
            (path, entry)
            for path, entry in self.tree.entries.items()
            if isinstance(entry, Symlink | NotAFolder | Missing | Unopened)
        )

    @cached_property
    def manifest_readings(self) -> tuple[Manifest | Problem | None, ...]:
        return tuple(self.read_manifest(path) for path in self.MANIFESTS)

    @cached_property
    def manifests(self) -> tuple[Manifest, ...]:
        return tuple(
            reading
            for reading in self.manifest_readings
            if isinstance(reading, Manifest)
        )

    @property
    def manifest(self) -> Manifest | None:
        match self.manifests:
            case (first, *others) if all(other == first for other in others):
                return first
            case _:
                return None

    @cached_property
    def skills(self) -> tuple[Skill, ...]:
        return tuple(
            Skill(self.root / path, self.tree.read(path / Skill.FILE))
            for path, entry in self.tree.entries.items()
            if isinstance(entry, Folder) and path.parent == self.SKILLS
        )

    @cached_property
    def playbooks(self) -> tuple[PurePosixPath, ...]:
        folders = {
            self.SKILLS / skill.name / self.PLAYBOOKS
            for skill in self.skills
            if skill.kind is Kind.MODE
        }
        return tuple(
            path
            for path in self.tree.files
            if path.parent in folders and path.suffix == ".md"
        )

    @cached_property
    def documents(self) -> frozendict[PurePosixPath, Document]:
        return frozendict(
            (path, Document(self.root / path, file.text))
            for path, file in self.tree.files.items()
            if path.suffix == ".md" and file.text is not None
        )

    @cached_property
    def manifest_problems(self) -> tuple[Problem, ...]:
        problems = [
            reading
            for reading in self.manifest_readings
            if isinstance(reading, Problem)
        ]
        valid = [
            (path, reading)
            for path, reading in zip(
                self.MANIFESTS, self.manifest_readings, strict=True
            )
            if isinstance(reading, Manifest)
        ]
        if not valid:
            return tuple(problems)
        (first, reference), *others = valid
        host = self.MANIFESTS[first]
        return (
            *problems,
            *(
                Problem(
                    self.root / path,
                    f"differs from the {host} manifest in {', '.join(fields)}; "
                    f"make it identical to the {host} manifest",
                )
                for path, other in others
                if (
                    fields := tuple(
                        field
                        for field in reference.differing(other)
                        if field != "version"
                    )
                )
            ),
        )

    def problems(self) -> list[Problem]:
        if self.unsafe:
            return [self.unsafe_problem(path, entry) for path, entry in self.unsafe]
        return [
            *self.manifest_problems,
            *self.required_problems(),
            *self.file_problems(),
            *(problem for skill in self.skills for problem in skill.problems()),
            *self.mode_problems(),
            *self.playbook_problems(),
            *self.text_problems(),
            *self.link_problems(),
        ]

    def unsafe_problem(
        self, path: PurePosixPath, entry: Symlink | NotAFolder | Missing | Unopened
    ) -> Problem:
        match entry:
            case Unopened(reason=reason):
                return Problem(self.root / path, reason)
            case NotAFolder():
                return Problem(self.root / path, self.NOT_A_FOLDER)
            case Missing():
                return Problem(self.root / path, self.MISSING)
            case Symlink():
                return Problem(self.root / path, self.SYMLINK)
            case unexpected:
                assert_never(unexpected)

    def read_manifest(self, path: PurePosixPath) -> Manifest | Problem | None:
        match self.tree.read(path):
            case Absent() as absent:
                return Problem(
                    self.root / path,
                    absent.absence(
                        "is missing; add it, since its host installs the plugin from it"
                    ),
                )
            case Unreadable():
                return None
            case File(content=content):
                try:
                    return Manifest.parse(content)
                except InvalidMetadataError as error:
                    return Problem(self.root / path, f"is invalid: {error}")
            case unexpected:
                assert_never(unexpected)

    def required_problems(self) -> list[Problem]:
        problems = [
            Problem(self.root / path, absent.absence(missing))
            for path, missing in {
                self.LICENSE: "is missing; copy the repository's LICENSE here",
                self.LOADER: (
                    "is missing; restore it from the repository, "
                    "so OpenCode can load the plugin"
                ),
                **dict.fromkeys(
                    self.HOOKS,
                    "is missing; restore it from the repository, so Claude Code "
                    "reloads the mode after a summarization",
                ),
            }.items()
            if isinstance(absent := self.tree.read(path), Absent)
        ]
        match self.tree.entries.get(self.SKILLS):
            case Folder():
                return problems
            case File() | Unreadable():
                skills = File.IN_A_FOLDERS_PLACE
            case Special():
                skills = Special.IN_A_FOLDERS_PLACE
            case Symlink() | NotAFolder() | Missing() | Unopened() | None:
                skills = "is missing; add it with the plugin's skills"
            case unexpected:
                assert_never(unexpected)
        return [*problems, Problem(self.root / self.SKILLS, skills)]

    def file_problems(self) -> list[Problem]:
        expected = {
            *self.MANIFESTS,
            self.LICENSE,
            self.LOADER,
            self.PACKAGE,
            *self.HOOKS,
            self.SKILLS,
        }
        expected |= {
            PurePosixPath(skill.path.relative_to(self.root)) for skill in self.skills
        }
        expected |= set(self.playbooks)
        problems = []
        for path, entry in self.tree.entries.items():
            match entry:
                case Special():
                    if path not in expected:
                        problems.append(Problem(self.root / path, Special.UNEXPECTED))
                case Unreadable():
                    if path not in expected:
                        problems.append(self.unexpected_problem(path))
                    problems.append(Problem(self.root / path, entry.reason))
                case File():
                    if path not in expected:
                        problems.append(self.unexpected_problem(path))
                    if entry.text is None and path.suffix == ".md":
                        problems.append(Problem(self.root / path, Problem.NOT_UTF8))
                case Folder() | Symlink() | NotAFolder() | Missing() | Unopened():
                    pass
                case unexpected:
                    assert_never(unexpected)
        return problems

    def unexpected_problem(self, path: PurePosixPath) -> Problem:
        if path.suffix != ".md":
            return Problem(
                self.root / path,
                "is not Markdown; remove it or move it out of the plugin",
            )
        return Problem(
            self.root / path,
            f"is neither a skill's {Skill.FILE} nor a playbook; "
            "move it into the mode's playbooks folder or out of the plugin",
        )

    def mode_problems(self) -> list[Problem]:
        modes = [skill for skill in self.skills if skill.kind is Kind.MODE]
        if len(modes) != 1:
            return [
                Problem(
                    self.root / self.SKILLS,
                    f"holds {len(modes)} modes, where it needs exactly 1; "
                    f"keep one skill folder without the {Kind.prefixes()} prefix",
                )
            ]
        (mode,) = modes
        if mode.document is None:
            return []
        title = f"# {mode.name}"
        opening = [line for line in mode.document.body.splitlines() if line][:1]
        indexed = {
            (link.target, section.title)
            for link in mode.document.links
            for section in mode.document.sections
            if section.holds(link.line)
        }
        expected = [
            (skill.path, skill.kind)
            for skill in self.skills
            if skill.kind is not Kind.MODE and not isinstance(skill.read, Absent)
        ]
        expected += [(self.root / path, Kind.MODE) for path in self.playbooks]
        problems = (
            []
            if opening == [title]
            else [
                Problem(
                    mode.path,
                    f"does not open its body with the line {title!r}; restore it, "
                    "since the Claude Code hook finds the mode in a transcript by it",
                )
            ]
        )
        length = len(mode.document.body.strip())
        if length > self.HOOK_OUTPUT - self.HOOK_ROOM:
            problems.append(
                Problem(
                    mode.path,
                    f"has a body of {length} characters, over the "
                    f"{self.HOOK_OUTPUT - self.HOOK_ROOM} that leave the Claude Code "
                    "hook room for its preamble and the mode's folder within the "
                    f"{self.HOOK_OUTPUT} characters Claude Code passes on "
                    "(https://code.claude.com/docs/en/hooks#json-output); shorten it",
                )
            )
        problems += [
            Problem(
                mode.path,
                f"does not index {path} under ## {kind.section}; add a link to it "
                "there with when it applies",
            )
            for path, kind in sorted(expected)
            if (path, kind.section) not in indexed
        ]
        problems += [
            Problem(
                document.path,
                f"names a mode other than {mode.name}; call the mode by its "
                "folder's name",
            )
            for document in self.documents.values()
            if any(name != mode.name for name in self.MODE_NAME.findall(document.text))
        ]
        return problems

    def playbook_problems(self) -> list[Problem]:
        return [
            Problem(
                self.root / path,
                f"has step {number} with no done condition; end it with a sentence "
                f"that starts {self.DONE!r} and names what an agent can check",
            )
            for path in self.playbooks
            if path in self.documents
            for number, step in enumerate(self.documents[path].steps, start=1)
            if self.DONE not in step
        ]

    def text_problems(self) -> list[Problem]:
        return [
            problem
            for path, document in self.documents.items()
            if path.is_relative_to(self.SKILLS)
            for problem in self.skill_text_problems(document)
        ]

    def skill_text_problems(self, document: Document) -> list[Problem]:
        return [
            *(
                Problem(
                    document.path,
                    f"line {document.line_at(found.start())} names an agent host, a "
                    "model or a host's folder; state the rule for every host",
                )
                for found in self.HOST.finditer(document.text)
            ),
            *(
                Problem(
                    document.path,
                    f"line {document.line_at(found.start())} holds a date or a year; "
                    "state the rule without it, since skill text outlives any date",
                )
                for found in self.DATE.finditer(document.text)
            ),
        ]

    def link_problems(self) -> list[Problem]:
        problems = []
        for document in self.documents.values():
            problems += [
                Problem(
                    document.path,
                    f"has a malformed link {href!r}; "
                    "write it as a full URL or a path to a file",
                )
                for href in document.malformed
            ]
            problems += [
                Problem(
                    document.path,
                    f"links to the absolute path {href!r}, which breaks once the "
                    "plugin moves; link to it by its path from this file",
                )
                for href in document.absolute
            ]
            targets = sorted(
                {
                    (link.target, link.fragment)
                    for link in document.links
                    if link.target is not None
                }
            )
            problems += [
                problem
                for target, fragment in targets
                if (problem := self.target_problem(document, target, fragment))
                is not None
            ]
        return problems

    def target_problem(
        self, document: Document, target: Path, fragment: str
    ) -> Problem | None:
        inside = (
            PurePosixPath(target.relative_to(self.root).as_posix())
            if target.is_relative_to(self.root)
            else None
        )
        if inside is None or isinstance(self.tree.read(inside), Absent):
            return Problem(
                document.path,
                f"links to {target}, which is not a file inside {self.root}; "
                "link to a file inside it, or to a full URL",
            )
        linked = self.documents.get(inside)
        if fragment and linked is not None and fragment not in linked.anchors:
            return Problem(
                document.path,
                f"links to {target}#{fragment}, which names no heading there; "
                "link to a heading's anchor, or drop the part after #",
            )
        return None
