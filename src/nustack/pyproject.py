"""`pyproject.toml`, down to the version the plugin's version must match."""

import tomllib
from pathlib import Path
from typing import Self

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationError

from nustack.problem import cannot_read


class InvalidPyprojectError(ValueError):
    """A `pyproject.toml` that is not valid TOML, or holds no project version."""


class MissingVersionError(InvalidPyprojectError):
    """A `pyproject.toml` whose `[project]` table holds no version string."""

    def __str__(self) -> str:
        return "needs a version string in its [project] table"


class Project(BaseModel):
    """The `[project]` table, down to its version."""

    model_config = ConfigDict(frozen=True)

    version: str


class Pyproject(BaseModel):
    """A `pyproject.toml`, down to its `[project]` table."""

    model_config = ConfigDict(frozen=True)

    project: Project

    @classmethod
    def read(cls, path: Path) -> Self:
        try:
            return cls.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
        except ValidationError as error:
            raise MissingVersionError from error
        except tomllib.TOMLDecodeError as error:
            msg = f"{error}; fix it"
            raise InvalidPyprojectError(msg) from error
        except UnicodeDecodeError as error:
            msg = "it is not valid UTF-8; save it as UTF-8"
            raise InvalidPyprojectError(msg) from error
        except ValueError as error:
            msg = "it holds a number too long to read; shorten it"
            raise InvalidPyprojectError(msg) from error
        except RecursionError as error:
            msg = "it nests too deeply to read; flatten it"
            raise InvalidPyprojectError(msg) from error
        except OSError as error:
            raise InvalidPyprojectError(cannot_read(error)) from error
