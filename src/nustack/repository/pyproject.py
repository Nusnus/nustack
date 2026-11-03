"""The harness's project settings, down to what the checks compare with other files.

That is the project's version and the folders Ruff leaves alone. A file that is not
valid TOML, or holds no version, is refused with the fix.
"""

import tomllib
from typing import Self

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError

from nustack.plugin.manifest import Version
from nustack.problem import Problem


class InvalidPyprojectError(ValueError):
    """A `pyproject.toml` that is not valid TOML, or holds no project version."""


class Project(BaseModel):
    """The `[project]` table, down to its version."""

    model_config = ConfigDict(frozen=True)

    version: Version


class Ruff(BaseModel):
    """The `[tool.ruff]` table, down to the folders it leaves alone."""

    model_config = ConfigDict(frozen=True)

    extend_exclude: tuple[str, ...] = Field(default=(), alias="extend-exclude")


class Tools(BaseModel):
    """The `[tool]` table, down to Ruff's."""

    model_config = ConfigDict(frozen=True)

    ruff: Ruff = Ruff()


class Pyproject(BaseModel):
    """A `pyproject.toml`, down to its `[project]` and `[tool.ruff]` tables."""

    model_config = ConfigDict(frozen=True)

    project: Project
    tool: Tools = Tools()

    @classmethod
    def parse(cls, content: bytes) -> Self:
        try:
            return cls.model_validate(tomllib.loads(content.decode()))
        except ValidationError as error:
            msg = (
                "needs a MAJOR.MINOR.PATCH version, such as 0.0.1, in its [project] "
                "table, and a list of strings as any [tool.ruff] extend-exclude"
            )
            raise InvalidPyprojectError(msg) from error
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
