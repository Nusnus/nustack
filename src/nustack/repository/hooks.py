"""The commit hooks `.pre-commit-config.yaml` runs, down to the files each skips.

A config that does not parse, or lacks a hooks list of entries that each hold an id,
is refused with the fix.
"""

from pathlib import PurePosixPath
from typing import ClassVar

from pydantic import BaseModel
from pydantic import ConfigDict

from nustack.repository.config import YamlConfig


class Hook(BaseModel):
    """One commit hook, down to the files it skips."""

    model_config = ConfigDict(frozen=True)

    id: str
    exclude: str | None = None


class HookSource(BaseModel):
    """One repository of commit hooks."""

    model_config = ConfigDict(frozen=True)

    hooks: tuple[Hook, ...]


class Hooks(YamlConfig):
    """`.pre-commit-config.yaml`, down to its hooks."""

    PATH: ClassVar[PurePosixPath] = PurePosixPath(".pre-commit-config.yaml")

    repos: tuple[HookSource, ...]

    @property
    def hooks(self) -> tuple[Hook, ...]:
        return tuple(hook for source in self.repos for hook in source.hooks)
