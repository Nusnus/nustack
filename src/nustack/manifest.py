"""The JSON metadata through which hosts and marketplaces find the plugin."""

import json
from collections.abc import Iterator
from contextlib import suppress
from functools import cache
from pathlib import Path
from typing import Annotated
from typing import Literal
from typing import Self
from typing import get_args

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import HttpUrl
from pydantic import ValidationError
from pydantic.fields import FieldInfo

from nustack.problem import cannot_read

NON_BLANK = r"[^\s\ufeff]"
type NonEmptyStr = Annotated[str, Field(pattern=NON_BLANK)]
NAME = r"^[a-z0-9]+(-[a-z0-9]+)*$"
SEMVER = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
VERSION = f"^{SEMVER}$"
RULES = {
    NON_BLANK: "fill it in; it is blank",
    NAME: "use kebab case, such as nus-mode",
    VERSION: "use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1",
}

type Name = Annotated[str, Field(pattern=NAME)]
type Version = Annotated[str, Field(pattern=VERSION)]


class InvalidMetadataError(ValueError):
    """A metadata file that is not valid JSON, or breaks its schema."""


class Metadata(BaseModel):
    """JSON metadata a host reads, which allows no unknown field and never changes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def read(cls, path: Path) -> Self:
        def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
            keys = [key for key, _ in pairs]
            for key in keys:
                if keys.count(key) > 1:
                    what = (
                        f"the key {key!r}"
                        if key in schema_labels(cls)
                        else "an unknown key"
                    )
                    msg = f"has {what} more than once; keep one"
                    raise InvalidMetadataError(msg)
            return dict(pairs)

        try:
            content = path.read_bytes()
        except OSError as error:
            raise InvalidMetadataError(cannot_read(error)) from error
        # json keeps only the last of repeated keys, so this pass finds them first,
        # with numbers left as text, and leaves every other error to Pydantic:
        # https://docs.python.org/3/library/json.html#repeated-names-within-an-object
        with suppress(json.JSONDecodeError, UnicodeDecodeError, RecursionError):
            json.loads(content, object_pairs_hook=unique, parse_int=str)
        try:
            return cls.model_validate_json(content)
        except ValidationError as error:
            raise InvalidMetadataError(reason_of(error, cls)) from error


class Person(Metadata):
    """A person a manifest names, as its author or owner."""

    name: NonEmptyStr


class Manifest(Metadata):
    """A plugin manifest, as every host reads it."""

    name: Name
    version: Version
    description: NonEmptyStr
    author: Person
    homepage: HttpUrl
    repository: HttpUrl
    license: NonEmptyStr


class Entry(Metadata):
    """One plugin, as a marketplace lists it."""

    name: Name
    source: NonEmptyStr
    description: NonEmptyStr


class Marketplace(Metadata):
    """A marketplace file that lists the plugin for a host to install from."""

    name: Name
    owner: Person
    plugins: tuple[Entry, ...]


class ClaudeMarketplace(Marketplace):
    """The Claude Code marketplace, which describes itself at its top level."""

    description: NonEmptyStr


class MarketplaceDetails(Metadata):
    """What a Cursor marketplace says about itself."""

    description: NonEmptyStr


class CursorMarketplace(Marketplace):
    """The Cursor marketplace, which describes itself under its metadata."""

    metadata: MarketplaceDetails


class Exports(Metadata):
    """The one export OpenCode loads, which points at the loader."""

    loader: Annotated[Literal["./opencode.ts"], Field(alias=".")]


class Package(Metadata):
    """The package file through which OpenCode loads the plugin's loader."""

    name: NonEmptyStr
    version: Version
    type: Literal["module"]
    exports: Exports


def reason_of(error: ValidationError, model: type[BaseModel]) -> str:
    labels = schema_labels(model)
    return "; ".join(
        f"{place_of(detail['loc'], labels)}: "
        + (
            unknown_key_fix(model, detail["loc"][:-1])
            if detail["type"] == "extra_forbidden"
            else RULES.get(detail.get("ctx", {}).get("pattern"), detail["msg"])
        )
        for detail in error.errors()
    )


def place_of(loc: tuple[str | int, ...], labels: frozenset[str]) -> str:
    return ".".join(label(part, labels) for part in loc) or "the file"


def unknown_key_fix(model: type[BaseModel], place: tuple[str | int, ...]) -> str:
    labels = schema_labels(model)
    keys = ", ".join(label(key, labels) for key in keys_at(model, place))
    return f"rename it or remove it; nustack allows only {keys} here"


def keys_at(model: type[BaseModel], place: tuple[str | int, ...]) -> Iterator[str]:
    current = model
    for part in place:
        if isinstance(part, str):
            current = next(models_in(fields_of(current)[part].annotation))
    yield from fields_of(current)


def label(part: str | int, labels: frozenset[str]) -> str:
    if isinstance(part, int):
        return str(part)
    if part not in labels:
        return "an unknown key"
    return part if part.replace("-", "_").isidentifier() else json.dumps(part)


@cache
def schema_labels(model: type[BaseModel]) -> frozenset[str]:
    return frozenset(
        found
        for key, field in fields_of(model).items()
        for found in (
            key,
            *(
                inner
                for model in models_in(field.annotation)
                for inner in schema_labels(model)
            ),
        )
    )


def fields_of(model: type[BaseModel]) -> dict[str, FieldInfo]:
    return {field.alias or name: field for name, field in model.model_fields.items()}


def models_in(annotation: object) -> Iterator[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
    for arg in get_args(annotation):
        yield from models_in(arg)
