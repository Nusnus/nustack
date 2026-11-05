"""One skill folder, held to the rules it keeps on its own.

Its folder name gives its kind, which decides the frontmatter it holds and so how
hosts load it. Its name matches its folder, and its `SKILL.md` reads as UTF-8 and
stays under the line limit. A vendored skill keeps only what hosts need to load
it, since nustack's authors write none of it.
"""

import difflib
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from typing import ClassVar
from typing import Literal
from typing import assert_never
lazy from collections.abc import Iterable
lazy from pathlib import Path

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StrictBool
from pydantic import ValidationError
from pydantic import field_validator

from nustack.markdown.document import Document
from nustack.markdown.frontmatter import FrontmatterBlock
from nustack.markdown.frontmatter import InvalidFrontmatterError
from nustack.problem import Problem
from nustack.tree import Blocked
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Missing
from nustack.tree import Read
from nustack.tree import Special
from nustack.tree import Unreadable
from nustack.validation import Pattern
from nustack.validation import Schema


class Kind(StrEnum):
    """What a skill is to the plugin: the mode, a file the mode reads, or vendored.

    A record names a vendored skill, whatever its folder's name.
    """

    MODE = "mode"
    PRINCIPLE = "principle"
    LANGUAGE = "language"
    VENDORED = "vendored"

    @property
    def prefix(self) -> str | None:
        match self:
            case Kind.MODE | Kind.VENDORED:
                return None
            case Kind.PRINCIPLE:
                return "principle-"
            case Kind.LANGUAGE:
                return "language-"
            case unexpected:
                assert_never(unexpected)

    @property
    def index_heading(self) -> str | None:
        match self:
            case Kind.MODE:
                return None
            case Kind.PRINCIPLE:
                return "Principles"
            case Kind.LANGUAGE:
                return "Languages"
            case Kind.VENDORED:
                return None
            case unexpected:
                assert_never(unexpected)

    @classmethod
    def prefixes(cls) -> str:
        return " or ".join(repr(kind.prefix) for kind in cls if kind.prefix is not None)

    @classmethod
    def of(cls, name: str) -> Kind:
        return next(
            (
                kind
                for kind in cls
                if kind.prefix is not None and name.startswith(kind.prefix)
            ),
            cls.MODE,
        )


class HostFrontmatter(BaseModel):
    """The frontmatter fields every host needs to load a `SKILL.md`."""

    model_config = ConfigDict(frozen=True)

    # The Agent Skills limits: https://agentskills.io/specification
    NAME_LENGTH: ClassVar[int] = 64
    name: str = Field(pattern=Pattern.NAME.value, max_length=NAME_LENGTH)
    description: str = Field(pattern=Pattern.NON_BLANK.value, max_length=1024)


class Frontmatter(HostFrontmatter):
    """The frontmatter of a `SKILL.md` nustack's authors write, as hosts read it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # None leaves the field to each host's default.
    disable_model_invocation: StrictBool | None = Field(
        default=None, alias="disable-model-invocation"
    )
    triggers: tuple[Literal["user", "model"], ...] | None = None

    @property
    def hidden_from_model(self) -> bool:
        return self.disable_model_invocation is True and self.triggers == ("user",)

    @property
    def sets_invocation(self) -> bool:
        return self.disable_model_invocation is not None or self.triggers is not None

    @field_validator("disable_model_invocation", mode="before")
    @classmethod
    def disable_model_invocation_not_null(cls, disable: object) -> object:
        if disable is not None:
            return disable
        raise ValueError(Schema.FIXES["bool_type"])

    @field_validator("triggers", mode="before")
    @classmethod
    def triggers_from_a_list(cls, triggers: object) -> object:
        if isinstance(triggers, tuple):
            return triggers
        msg = "make it a YAML list, such as [user] or [user, model]"
        raise ValueError(msg)


@dataclass(frozen=True)
class Skill:
    """A skill folder, and the text of its `SKILL.md` when that reads as UTF-8."""

    FILE: ClassVar[str] = "SKILL.md"
    LICENSE: ClassVar[str] = "LICENSE"
    MAX_LINES: ClassVar[int] = 500
    TYPO_SIMILARITY: ClassVar[float] = 0.8
    folder: Path
    read: Read
    kind: Kind

    @property
    def name(self) -> str:
        return self.folder.name

    @property
    def path(self) -> Path:
        return self.folder / self.FILE

    @property
    def misspelled_kind(self) -> Kind | None:
        first = self.name.partition("-")[0] + "-"
        return next(
            (
                kind
                for kind in Kind
                if kind.prefix is not None
                and difflib.SequenceMatcher(a=first, b=kind.prefix).ratio()
                >= self.TYPO_SIMILARITY
            ),
            None,
        )

    @cached_property
    def document(self) -> Document | None:
        match self.read:
            case File(text=str() as text):
                return Document(self.path, text)
            case File() | Folder() | Special() | Missing() | Blocked() | Unreadable():
                return None
            case unexpected:
                assert_never(unexpected)

    def problems(self) -> list[Problem]:
        problems = self.name_problems()
        match self.read:
            case Folder() | Special():
                return [*problems, Problem(self.path, self.read.IN_A_FILES_PLACE)]
            case Missing():
                return [
                    *problems,
                    Problem(
                        self.folder, f"has no {self.FILE}; add one or remove the folder"
                    ),
                ]
            case File() | Blocked() | Unreadable():
                pass
            case unexpected:
                assert_never(unexpected)
        if self.document is None:
            return problems
        match self.kind:
            case Kind.VENDORED:
                # name_problems finds nothing in a vendored skill, so = and += agree.
                problems += self.frontmatter_problems(  # pragma: no mutate
                    self.read_frontmatter(self.document, HostFrontmatter)
                )
            case Kind.MODE | Kind.PRINCIPLE | Kind.LANGUAGE as kind:
                frontmatter = self.read_frontmatter(self.document, Frontmatter)
                problems += self.frontmatter_problems(frontmatter)
                if isinstance(frontmatter, Frontmatter):
                    problems += self.invocation_problems(kind, frontmatter)
            case unexpected:
                assert_never(unexpected)
        lines = len(self.document.text_lines)
        if lines >= self.MAX_LINES and self.kind is not Kind.VENDORED:
            problems.append(
                Problem(
                    self.path,
                    f"has {lines} lines, where it needs under {self.MAX_LINES}; "
                    "shorten it",
                )
            )
        return problems

    def name_problems(self) -> list[Problem]:
        near = self.misspelled_kind
        if self.kind is not Kind.MODE or near is None:
            return []
        return [
            Problem(
                self.folder,
                f"starts with a prefix close to {near.prefix!r}; rename the folder to "
                f"start with {near.prefix!r} if it is a {near} skill",
            )
        ]

    def frontmatter_problems(
        self, frontmatter: HostFrontmatter | tuple[Problem, ...]
    ) -> list[Problem]:
        match frontmatter:
            case tuple() as refused:
                return list(refused)
            case HostFrontmatter(name=name) if name != self.name:
                return [
                    Problem(
                        self.path,
                        f"name differs from its folder {self.name!r}; "
                        "use one name for both",
                    )
                ]
            case _:
                return []

    def invocation_problems(
        self,
        kind: Literal[Kind.MODE, Kind.PRINCIPLE, Kind.LANGUAGE],
        frontmatter: Frontmatter,
    ) -> list[Problem]:
        match kind:
            case Kind.PRINCIPLE | Kind.LANGUAGE:
                if frontmatter.hidden_from_model:
                    return []
                return [
                    Problem(
                        self.path,
                        f"a {kind} skill needs disable-model-invocation: true"
                        " and triggers: [user]; set both in its frontmatter",
                    )
                ]
            case Kind.MODE:
                if not frontmatter.sets_invocation:
                    return []
                return [
                    Problem(
                        self.path,
                        "a mode skill leaves disable-model-invocation and triggers"
                        " unset, so both keep their defaults; remove both from its"
                        " frontmatter",
                    )
                ]
            case unexpected:
                assert_never(unexpected)

    def read_frontmatter[M: HostFrontmatter](
        self, document: Document, model: type[M]
    ) -> M | tuple[Problem, ...]:
        try:
            block = FrontmatterBlock.of(document.text)
            if block is None:
                return (
                    Problem(
                        self.path,
                        "has no frontmatter; open it with a line that holds only ---,"
                        " and save it with no byte order mark and with LF or CRLF"
                        " line endings",
                    ),
                )
            fields = block.fields
        except InvalidFrontmatterError as error:
            return self.invalid_frontmatter(error.reasons)
        try:
            return model.model_validate(fields)
        except ValidationError as error:
            return self.invalid_frontmatter([Schema(model).reason(error)])

    def invalid_frontmatter(self, reasons: Iterable[str]) -> tuple[Problem, ...]:
        return tuple(
            Problem(self.path, f"frontmatter is invalid: {reason}")
            for reason in reasons
        )
