"""The rules each skill folder follows on its own."""

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import ClassVar
from typing import Literal
from typing import assert_never

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StrictBool
from pydantic import ValidationError
from pydantic import field_validator

from nustack.document import Document
from nustack.document import InvalidFrontmatterError
from nustack.document import lines_of
from nustack.manifest import NAME
from nustack.manifest import NON_BLANK
from nustack.manifest import reason_of
from nustack.problem import Problem


class Kind(StrEnum):
    """What a skill is to the plugin: the mode, or a principle the mode reads."""

    MODE = "mode"
    PRINCIPLE = "principle"


class Frontmatter(BaseModel):
    """The YAML header of a `SKILL.md`, as every host reads it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # The Agent Skills limits: https://agentskills.io/specification
    name: str = Field(pattern=NAME, max_length=64)
    description: str = Field(pattern=NON_BLANK, max_length=1024)
    disable_model_invocation: StrictBool = Field(
        default=False, alias="disable-model-invocation"
    )
    triggers: tuple[Literal["user", "model"], ...] = Field(
        default=("user", "model"), strict=True
    )

    @property
    def hidden_from_model(self) -> bool:
        return self.disable_model_invocation and self.triggers == ("user",)

    @field_validator("triggers", mode="before")
    @classmethod
    def triggers_from_a_list(cls, triggers: object) -> object:
        if isinstance(triggers, list):
            return tuple(triggers)
        msg = "triggers must be a YAML list, such as [user] or [user, model]"
        raise ValueError(msg)


@dataclass
class Skill:
    """A skill folder: its `SKILL.md` and every file beside it."""

    PRINCIPLE_PREFIX: ClassVar[str] = "principle-"
    MAX_LINES: ClassVar[int] = 500
    folder: Path

    @property
    def name(self) -> str:
        return self.folder.name

    @property
    def kind(self) -> Kind:
        if self.name.startswith(self.PRINCIPLE_PREFIX):
            return Kind.PRINCIPLE
        return Kind.MODE

    @cached_property
    def document(self) -> Document:
        return Document(self.folder / "SKILL.md")

    def problems(self) -> list[Problem]:
        if not self.document.path.is_file():
            return [
                Problem(self.folder, "has no SKILL.md; add one or remove the folder")
            ]
        frontmatter = self.read_frontmatter()
        if isinstance(frontmatter, Problem):
            return [frontmatter]
        problems = []
        if frontmatter.name != self.name:
            problems.append(
                Problem(
                    self.document.path,
                    f"name differs from its folder {self.name!r}; "
                    "use one name for both",
                )
            )
        match self.kind:
            case Kind.PRINCIPLE:
                if not frontmatter.hidden_from_model:
                    problems.append(
                        Problem(
                            self.document.path,
                            "a principle skill needs disable-model-invocation: true"
                            " and triggers: [user]; set both in its frontmatter",
                        )
                    )
            case Kind.MODE:
                if frontmatter.disable_model_invocation or sorted(
                    frontmatter.triggers
                ) != ["model", "user"]:
                    problems.append(
                        Problem(
                            self.document.path,
                            "a mode skill keeps disable-model-invocation and"
                            " triggers at their defaults; remove both from its"
                            " frontmatter",
                        )
                    )
            case unexpected:
                assert_never(unexpected)
        lines = len(lines_of(self.document.text))
        if lines >= self.MAX_LINES:
            problems.append(
                Problem(
                    self.document.path,
                    f"has {lines} lines, where it needs under {self.MAX_LINES}; "
                    "shorten it",
                )
            )
        return problems

    def read_frontmatter(self) -> Frontmatter | Problem:
        try:
            data = self.document.frontmatter
        except InvalidFrontmatterError as error:
            return Problem(self.document.path, f"frontmatter is invalid: {error}")
        if data is None:
            return Problem(
                self.document.path,
                "has no frontmatter; open it with a line that holds only ---,"
                " and save it with no byte order mark and with LF or CRLF"
                " line endings",
            )
        try:
            return Frontmatter.model_validate(data)
        except ValidationError as error:
            return Problem(
                self.document.path,
                f"frontmatter is invalid: {reason_of(error, Frontmatter)}",
            )
