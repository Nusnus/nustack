"""How the check reads a YAML config file, held to the model of what it reads there.

A file that is not UTF-8 or valid YAML, or that lacks what the check reads, is
refused with the fix. Each file's model subclasses `YamlConfig`.
"""

from pathlib import PurePosixPath
from typing import ClassVar
from typing import Self

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import ValidationError

from nustack.problem import Problem
from nustack.validation import Schema
from nustack.yaml_reader import YamlError
from nustack.yaml_reader import YamlWarning
from nustack.yaml_reader import read_yaml


class InvalidConfigError(ValueError):
    """A YAML config file that does not parse, or lacks what the check reads."""


class YamlConfig(BaseModel):
    """A YAML config file, down to what the check reads from it."""

    PATH: ClassVar[PurePosixPath]
    # Its YAML opens on the file's first line, the line YamlWarning counts from.
    FIRST_LINE: ClassVar[int] = YamlWarning.FIRST_LINE
    model_config = ConfigDict(frozen=True)

    @classmethod
    def parse(cls, content: bytes) -> Self:
        try:
            return cls.model_validate(read_yaml(content.decode(), str(cls.PATH)))
        except UnicodeDecodeError as error:
            msg = f"it {Problem.NOT_UTF8}"
            raise InvalidConfigError(msg) from error
        except YamlError as error:
            raise InvalidConfigError(error.reason(cls.FIRST_LINE)) from error
        except ValidationError as error:
            raise InvalidConfigError(Schema(cls).reason(error)) from error
