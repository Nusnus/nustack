"""The harness's project settings, down to what the checks compare with other files.

That is the project's version, the files commitizen's `cz bump` sets the version in
beside it, the tag format it finds the last release by, the folders mutmut mutates and
the other files its tests read, and the folders Ruff leaves alone. A file that is not
valid TOML, or a field that breaks its schema, is refused with the fix.
"""

import tomllib
from pathlib import PurePosixPath
from typing import ClassVar
from typing import Self

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError

from nustack.problem import Problem
from nustack.validation import Schema
from nustack.version import Version


class InvalidPyprojectError(ValueError):
    """A `pyproject.toml` that is not valid TOML, or breaks its schema."""


class Project(BaseModel):
    """The `[project]` table, down to its version."""

    model_config = ConfigDict(frozen=True)

    version: Version


class Commitizen(BaseModel):
    """The `[tool.commitizen]` table, down to the files and tags `cz bump` versions."""

    model_config = ConfigDict(frozen=True)

    tag_format: str | None = None
    version_files: tuple[str, ...] = ()


class Mutmut(BaseModel):
    """The `[tool.mutmut]` table, down to the folders mutmut mutates."""

    model_config = ConfigDict(frozen=True)

    source_paths: tuple[str, ...] = ()


class Mutation(BaseModel):
    """The `[tool.nustack.mutation]` table: what mutmut's tests read beyond code.

    nustack owns the table, so the model holds all of it and refuses any other key.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    reads: tuple[str, ...] = ()


class Nustack(BaseModel):
    """The `[tool.nustack]` table: its mutation settings.

    nustack owns the table, so the model holds all of it and refuses any other key.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    mutation: Mutation = Mutation()


class Ruff(BaseModel):
    """The `[tool.ruff]` table, down to the folders it leaves alone."""

    model_config = ConfigDict(frozen=True)

    extend_exclude: tuple[str, ...] = Field(default=(), alias="extend-exclude")


class Tools(BaseModel):
    """The `[tool]` table, down to commitizen's, mutmut's, nustack's and Ruff's."""

    model_config = ConfigDict(frozen=True)

    commitizen: Commitizen = Commitizen()
    mutmut: Mutmut = Mutmut()
    nustack: Nustack = Nustack()
    ruff: Ruff = Ruff()


class Pyproject(BaseModel):
    """A `pyproject.toml`, down to `[project]` and the tools' tables nustack reads."""

    PATH: ClassVar[PurePosixPath] = PurePosixPath("pyproject.toml")
    model_config = ConfigDict(frozen=True)

    project: Project
    tool: Tools = Tools()

    @classmethod
    def parse(cls, content: bytes) -> Self:
        try:
            return cls.model_validate(tomllib.loads(content.decode()))
        except ValidationError as error:
            raise InvalidPyprojectError(Schema(cls).reason(error)) from error
        except tomllib.TOMLDecodeError as error:
            msg = f"it is not valid TOML on line {error.lineno}; fix it"
            raise InvalidPyprojectError(msg) from error
        except UnicodeDecodeError as error:
            msg = f"it {Problem.NOT_UTF8}"
            raise InvalidPyprojectError(msg) from error
        except ValueError as error:
            msg = f"it {Problem.NUMBER_TOO_LONG}; shorten it"
            raise InvalidPyprojectError(msg) from error
        except RecursionError as error:
            msg = f"it {Problem.TOO_DEEP}"
            raise InvalidPyprojectError(msg) from error
