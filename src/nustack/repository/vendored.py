"""The vendored writing-for-agents copy, which review reads as its source wrote it.

The sync workflow names the folder it writes the copy to, and every commit hook that
rewrites files, and Ruff, must skip that folder.
"""

from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar
from typing import Self

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationError

from nustack.problem import Problem
from nustack.yaml_reader import YamlError
from nustack.yaml_reader import read_yaml
lazy from nustack.repository.pyproject import Pyproject


class InvalidConfigError(ValueError):
    """A YAML config file that does not parse, or lacks what the check reads."""


class YamlConfig(BaseModel):
    """A YAML config file, down to what the check reads from it."""

    SHAPE: ClassVar[str] = "holds a value the check cannot read; fix its shape"
    model_config = ConfigDict(frozen=True)

    @classmethod
    def parse(cls, content: bytes) -> Self:
        try:
            return cls.model_validate(read_yaml(content))
        except YamlError as error:
            msg = "it is not valid YAML; fix it"
            raise InvalidConfigError(msg) from error
        except ValidationError as error:
            raise InvalidConfigError(cls.SHAPE) from error


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

    SHAPE: ClassVar[str] = (
        "needs a repos list, each with a hooks list of entries that each hold an id; "
        "fix its shape"
    )
    repos: tuple[HookSource, ...]

    @property
    def hooks(self) -> tuple[Hook, ...]:
        return tuple(hook for source in self.repos for hook in source.hooks)


class Job(BaseModel):
    """A workflow job, down to its environment."""

    model_config = ConfigDict(frozen=True)

    env: frozendict[str, str] = frozendict()


class Workflow(YamlConfig):
    """A GitHub Actions workflow, down to its jobs' environments."""

    SHAPE: ClassVar[str] = (
        "needs a jobs mapping, each job with any env a mapping of strings; "
        "fix its shape"
    )
    jobs: frozendict[str, Job]


@dataclass(frozen=True)
class VendoredCopy:
    """The folder the sync workflow copies into, which Ruff and the text hooks skip.

    Review reads the copy byte for byte as its source wrote it.
    """

    HOOKS: ClassVar[PurePosixPath] = PurePosixPath(".pre-commit-config.yaml")
    WORKFLOW: ClassVar[PurePosixPath] = PurePosixPath(
        ".github/workflows/sync-writing-for-agents.yml"
    )
    PYPROJECT: ClassVar[PurePosixPath] = PurePosixPath("pyproject.toml")
    JOB: ClassVar[str] = "sync"
    REWRITERS: ClassVar[tuple[str, ...]] = (
        "end-of-file-fixer",
        "fix-byte-order-marker",
        "mixed-line-ending",
        "trailing-whitespace",
        "markdownlint-cli2",
    )
    root: Path
    hooks: Hooks
    workflow: Workflow
    pyproject: Pyproject

    @property
    def destination(self) -> str | None:
        job = self.workflow.jobs.get(self.JOB)
        return None if job is None else job.env.get("DESTINATION")

    def problems(self) -> list[Problem]:
        destination = self.destination
        if destination is None:
            return [
                Problem(
                    self.root / self.WORKFLOW,
                    f"has no DESTINATION in its {self.JOB} job's env; "
                    "set it to the folder the sync copies into",
                )
            ]
        exclude = "^" + destination.removesuffix("/").replace(".", r"\.") + "/"
        hooks = {hook.id: hook for hook in self.hooks.hooks}
        problems = [
            Problem(
                self.root / self.HOOKS,
                f"has no {name} hook; restore it, with an exclude of the sync "
                "workflow's DESTINATION folder",
            )
            for name in self.REWRITERS
            if name not in hooks
        ]
        problems += [
            Problem(
                self.root / self.HOOKS,
                f"has the {name} hook skip a folder other than the sync workflow's "
                "DESTINATION; set its exclude to ^, that folder with each . escaped, "
                "and /",
            )
            for name in self.REWRITERS
            if name in hooks and hooks[name].exclude != exclude
        ]
        skipped = self.pyproject.tool.ruff.extend_exclude
        if destination.removesuffix("/") not in {
            folder.removesuffix("/") for folder in skipped
        }:
            problems.append(
                Problem(
                    self.root / self.PYPROJECT,
                    "has a [tool.ruff] extend-exclude that leaves out the sync "
                    "workflow's DESTINATION; add that folder to it",
                )
            )
        return problems
