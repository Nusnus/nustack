"""A release tag, and what it must name to publish.

A v<version> tag publishes only from main, only when it names the plugin version and
only while it names the commit CI passed on, and a release before v0.1.0 is a
pre-release. A tag given as text other than v<version> is refused with the fix.
"""

import contextlib
import re
from dataclasses import dataclass
from typing import ClassVar

from nustack.problem import Problem
from nustack.validation import Pattern
lazy from nustack.sha import Sha
lazy from nustack.version import Version


class TagError(ValueError):
    """A release tag is not of the v<version> form."""


@dataclass(frozen=True)
class Tag:
    """A release's v<version> tag; it publishes from main and the declared version."""

    # commitizen's tag_format in pyproject.toml and the release workflow's push tags
    # filter spell the same prefix; nustack check holds both to it.
    PREFIX: ClassVar[str] = "v"
    version: Version

    @property
    def prerelease(self) -> bool:
        return self.version.startswith("0.0.")

    def problems(self, version: Version, *, on_main: bool) -> list[Problem]:
        problems = []
        if not on_main:
            problems.append(
                Problem(
                    str(self),
                    "is not on main; delete it and tag the commit the squash merge made"
                    " on main",
                )
            )
        if self.version != version:
            problems.append(
                Problem(
                    str(self),
                    f"does not match plugin version {version}; delete it and tag"
                    f" {Tag(version)}, or set the version as"
                    " .agents/skills/release/SKILL.md says",
                )
            )
        return problems

    def moved(self, commit: Sha, tagged: Sha) -> Problem | None:
        if tagged == commit:
            return None
        return Problem(
            str(self),
            "has moved off the commit CI passed on; the run the move started"
            " publishes it",
        )

    @classmethod
    def parse(cls, value: str) -> Tag:
        if value.startswith(cls.PREFIX):
            with contextlib.suppress(TagError):
                return cls(value.removeprefix(cls.PREFIX))
        message = (
            f"give the tag as {cls.PREFIX}<version>, not {value}; for its version,"
            f" {Pattern.VERSION.fix}"
        )
        raise TagError(message)

    def __str__(self) -> str:
        return f"{self.PREFIX}{self.version}"

    def __post_init__(self) -> None:
        if not re.fullmatch(Pattern.VERSION, self.version):
            message = f"build the tag from a version; {Pattern.VERSION.fix}"
            raise TagError(message)
