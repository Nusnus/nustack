"""The release workflow, down to the tags whose push starts it.

An `on` key that `%YAML 1.1` reads as true is refused with the fix.
"""

from pathlib import PurePosixPath
from typing import ClassVar

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator
from pydantic import model_validator

from nustack.repository.config import YamlConfig


class Push(BaseModel):
    """A workflow's push trigger, down to the tag filters it runs for."""

    model_config = ConfigDict(frozen=True)

    tags: tuple[str, ...] = ()

    # GitHub's workflow parser takes one tag filter as a string, as well as a list:
    # https://github.com/actions/languageservices/blob/4043eda/workflow-parser/src/workflow-v1.0.json
    @field_validator("tags", mode="before")
    @classmethod
    def tags_of_one_filter(cls, value: object) -> object:
        return (value,) if isinstance(value, str) else value


class Triggers(BaseModel):
    """A workflow's `on` table, down to its push trigger."""

    model_config = ConfigDict(frozen=True)

    push: Push = Push()

    # A push trigger with no filters may be null:
    # https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#on
    @field_validator("push", mode="before")
    @classmethod
    def push_of_null(cls, value: object) -> object:
        return {} if value is None else value


class ReleaseWorkflow(YamlConfig):
    """`.github/workflows/release.yml`, down to the tags whose push publishes."""

    PATH: ClassVar[PurePosixPath] = PurePosixPath(".github/workflows/release.yml")

    on: Triggers

    # on names one event, or a list of events, as well as a table of them:
    # https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#on
    @field_validator("on", mode="before")
    @classmethod
    def on_of_event_names(cls, value: object) -> object:
        match value:
            case str() as event:
                return {event: None}
            case list() as events if all(isinstance(each, str) for each in events):
                return dict.fromkeys(events)
            case _:
                return value

    # YAML 1.1 reads a plain on as true: https://yaml.org/type/bool.html
    @model_validator(mode="before")
    @classmethod
    def refuse_on_read_as_true(cls, data: object) -> object:
        if isinstance(data, dict) and any(key is True for key in data):
            msg = (
                "%YAML 1.1 reads its on key as true; drop the %YAML 1.1 directive, or"
                ' quote the key as "on"'
            )
            raise ValueError(msg)
        return data
