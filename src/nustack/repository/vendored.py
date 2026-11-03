"""The vendored writing-for-agents copy, which review reads as its source wrote it.

The sync workflow names the folder it writes the copy to, and every commit hook that
rewrites files, and Ruff, must skip that folder.
"""

import re
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

    FIRST_LINE: ClassVar[int] = 1
    SHAPE: ClassVar[str] = "holds a value the check cannot read; fix its shape"
    model_config = ConfigDict(frozen=True)

    @classmethod
    def parse(cls, content: bytes) -> Self:
        try:
            return cls.model_validate(read_yaml(content.decode()))
        except UnicodeDecodeError as error:
            msg = f"it {Problem.NOT_UTF8}"
            raise InvalidConfigError(msg) from error
        except YamlError as error:
            raise InvalidConfigError(error.reason(cls.FIRST_LINE)) from error
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

    # GitHub reads a null, a number or a boolean in env as text, a null as "":
    # https://github.com/actions/languageservices/blob/4043eda158e16579cc5fb1b0b07a4bce2a76f0b5/workflow-parser/src/workflow-v1.0.json#L2016-L2031
    # https://github.com/actions/languageservices/blob/4043eda158e16579cc5fb1b0b07a4bce2a76f0b5/workflow-parser/src/templates/template-reader.ts#L411-L441
    # https://github.com/actions/languageservices/blob/4043eda158e16579cc5fb1b0b07a4bce2a76f0b5/workflow-parser/src/templates/tokens/null-token.ts#L21-L23
    env: frozendict[str, str | int | float | bool | None] = frozendict()


class Workflow(YamlConfig):
    """A GitHub Actions workflow, down to its jobs' environments."""

    SHAPE: ClassVar[str] = (
        "needs a jobs mapping, each job with any env a mapping of scalars; "
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
    def folder(self) -> str | int | float | bool | None:
        job = self.workflow.jobs.get(self.JOB)
        if job is None or "FOLDER" not in job.env:
            return None
        value = job.env["FOLDER"]
        return "" if value is None else value

    def problems(self) -> list[Problem]:
        folder = self.folder
        if folder is None:
            return [
                Problem(
                    self.root / self.WORKFLOW,
                    f"has no FOLDER in its {self.JOB} job's env; "
                    "set it to the folder the sync copies into",
                )
            ]
        if not isinstance(folder, str):
            return [
                Problem(
                    self.root / self.WORKFLOW,
                    f"has a FOLDER in its {self.JOB} job's env that YAML reads as "
                    "a number or a boolean; quote it",
                )
            ]
        path = PurePosixPath(folder)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            return [
                Problem(
                    self.root / self.WORKFLOW,
                    f"has a FOLDER in its {self.JOB} job's env that names no "
                    "folder inside the repository; set it to the folder the sync "
                    "copies into",
                )
            ]
        # pre-commit matches the paths git ls-files prints, which are always plain.
        if folder.removesuffix("/") != str(path):
            return [
                Problem(
                    self.root / self.WORKFLOW,
                    f"has a FOLDER in its {self.JOB} job's env that is not a "
                    "plain path; write it with no . part, no //, and no more than one "
                    "/ at its end",
                )
            ]
        exclude = "^" + re.escape(str(path)) + "/"
        hooks = {hook.id for hook in self.hooks.hooks}
        problems = [
            Problem(
                self.root / self.HOOKS,
                f"has no {name} hook; restore it, with an exclude of the folder the "
                "sync workflow's FOLDER env var names",
            )
            for name in self.REWRITERS
            if name not in hooks
        ]
        problems += [
            Problem(
                self.root / self.HOOKS,
                f"has the {name} hook skip a folder other than the one the sync "
                "workflow's FOLDER env var names; set its exclude to ^, that folder "
                "passed through Python's re.escape, and /",
            )
            for name in self.REWRITERS
            if any(
                hook.id == name and hook.exclude != exclude for hook in self.hooks.hooks
            )
        ]
        skipped = self.pyproject.tool.ruff.extend_exclude
        if folder.removesuffix("/") not in {skip.removesuffix("/") for skip in skipped}:
            problems.append(
                Problem(
                    self.root / self.PYPROJECT,
                    "has a [tool.ruff] extend-exclude that leaves out the folder the "
                    "sync workflow's FOLDER env var names; add that folder to it",
                )
            )
        return problems
