"""The vendored writing-for-agents copy, which review reads as its source wrote it.

The sync workflow names the folder it writes the copy to, and every commit hook that
rewrites files, and Ruff, must skip that folder.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator

from nustack.problem import Problem
from nustack.repository.config import YamlConfig
lazy from nustack.repository.pyproject import Pyproject


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


# GitHub reads a null, a number or a boolean in env as text, a null as "":
# https://github.com/actions/languageservices/blob/4043eda158e16579cc5fb1b0b07a4bce2a76f0b5/workflow-parser/src/workflow-v1.0.json#L2016-L2031
# https://github.com/actions/languageservices/blob/4043eda158e16579cc5fb1b0b07a4bce2a76f0b5/workflow-parser/src/templates/template-reader.ts#L411-L441
# https://github.com/actions/languageservices/blob/4043eda158e16579cc5fb1b0b07a4bce2a76f0b5/workflow-parser/src/templates/tokens/null-token.ts#L21-L23
type EnvValue = str | int | float | bool | None


class Job(BaseModel):
    """A workflow job, down to its environment."""

    model_config = ConfigDict(frozen=True)

    env: frozendict[str, EnvValue] = frozendict()

    # Without this check, pydantic refuses a value of another type once per union
    # member, with int_type and float_type among them, which Schema.FIXES does not
    # map, so this one check gives the one fix.
    @field_validator("env", mode="before")
    @classmethod
    def env_of_scalars(cls, env: object) -> object:
        if isinstance(env, dict) and all(
            isinstance(key, str) and isinstance(value, EnvValue.__value__)
            for key, value in env.items()
        ):
            return env
        msg = "make it an object of names to text, numbers, booleans or nulls"
        raise ValueError(msg)


class SyncWorkflow(YamlConfig):
    """The sync workflow, down to its jobs' environments."""

    PATH: ClassVar[PurePosixPath] = PurePosixPath(
        ".github/workflows/sync-writing-for-agents.yml"
    )

    jobs: frozendict[str, Job]


@dataclass(frozen=True)
class VendoredCopy:
    """The folder the sync workflow copies into, which Ruff and the text hooks skip.

    Review reads the copy byte for byte as its source wrote it.
    """

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
    workflow: SyncWorkflow
    pyproject: Pyproject

    @property
    def folder(self) -> EnvValue:
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
                    self.root / SyncWorkflow.PATH,
                    f"has no FOLDER in its {self.JOB} job's env; "
                    "set it to the folder the sync copies into",
                )
            ]
        if not isinstance(folder, str):
            return [
                Problem(
                    self.root / SyncWorkflow.PATH,
                    f"has a FOLDER in its {self.JOB} job's env that YAML reads as "
                    "a number or a boolean; quote it",
                )
            ]
        path = PurePosixPath(folder)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            return [
                Problem(
                    self.root / SyncWorkflow.PATH,
                    f"has a FOLDER in its {self.JOB} job's env that names no "
                    "folder inside the repository; set it to the folder the sync "
                    "copies into",
                )
            ]
        # pre-commit matches the paths git ls-files prints, which are always plain.
        if folder.removesuffix("/") != str(path):
            return [
                Problem(
                    self.root / SyncWorkflow.PATH,
                    f"has a FOLDER in its {self.JOB} job's env that is not a "
                    "plain path; write it with no . part, no //, and no more than one "
                    "/ at its end",
                )
            ]
        exclude = "^" + re.escape(str(path)) + "/"
        hooks = {hook.id for hook in self.hooks.hooks}
        problems = [
            Problem(
                self.root / Hooks.PATH,
                f"has no {name} hook; restore it, with an exclude of the folder the "
                "sync workflow's FOLDER env var names",
            )
            for name in self.REWRITERS
            if name not in hooks
        ]
        problems += [
            Problem(
                self.root / Hooks.PATH,
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
                    self.root / Pyproject.PATH,
                    "has a [tool.ruff] extend-exclude that leaves out the folder the "
                    "sync workflow's FOLDER env var names; add that folder to it",
                )
            )
        return problems
