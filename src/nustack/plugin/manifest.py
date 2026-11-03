"""The JSON files through which hosts and marketplaces find the plugin.

The manifests, the marketplaces and the loader's package are each read in key
order, every repeated key kept, and held to the fields their host accepts. A file
that is not valid JSON, or a field that breaks its schema, is refused with the fix.
"""

import json
from abc import abstractmethod
from contextlib import suppress
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Annotated
from typing import ClassVar
from typing import Literal
from typing import Self
from typing import get_args
lazy from collections.abc import Iterator

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import HttpUrl
from pydantic import ValidationError

from nustack.validation import Pattern
from nustack.validation import Schema

type NonEmptyStr = Annotated[str, Field(pattern=Pattern.NON_BLANK.value)]
type Name = Annotated[str, Field(pattern=Pattern.NAME.value)]
type Version = Annotated[str, Field(pattern=Pattern.VERSION.value)]
type LoaderExport = Literal["./opencode.ts"]


class InvalidMetadataError(ValueError):
    """A metadata file that is not valid JSON, or breaks its schema."""


@dataclass(frozen=True)
class JsonObject:
    """A JSON object's key-value pairs in their order, each repeated key kept."""

    pairs: tuple[tuple[str, object], ...]

    @classmethod
    def of(cls, pairs: list[tuple[str, object]]) -> JsonObject:
        return cls(tuple(pairs))


class Metadata(BaseModel):
    """JSON metadata a host reads, which allows no unknown field and never changes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def parse(cls, content: bytes) -> Self:
        repeats: list[str] = []
        # json keeps only the last of repeated keys, so this pass finds them first,
        # with numbers left as text, and leaves every other error to Pydantic:
        # https://docs.python.org/3/library/json.html#repeated-names-within-an-object
        with suppress(json.JSONDecodeError, UnicodeDecodeError, RecursionError):
            repeats = list(
                cls.repeats_in(
                    json.loads(content, object_pairs_hook=JsonObject.of, parse_int=str),
                    (),
                )
            )
        try:
            metadata = cls.model_validate_json(content)
        except ValidationError as error:
            reasons = [*repeats, Schema(cls).reason(error)]
            raise InvalidMetadataError("; ".join(reasons)) from error
        if repeats:
            raise InvalidMetadataError("; ".join(repeats))
        return metadata

    @classmethod
    def repeats_in(cls, value: object, place: tuple[str | int, ...]) -> Iterator[str]:
        match value:
            case JsonObject(pairs=pairs):
                schema = Schema(cls)
                keys = [name for name, _ in pairs]
                for key in dict.fromkeys(keys):
                    if keys.count(key) > 1:
                        what = (
                            f"the key {key!r}"
                            if key in schema.labels
                            else schema.UNKNOWN_KEY
                        )
                        yield (
                            f"has {what} more than once in {schema.place(place)}; "
                            "keep one"
                        )
                for key, inner in pairs:
                    yield from cls.repeats_in(inner, (*place, key))
            case list():
                for index, inner in enumerate(value):
                    yield from cls.repeats_in(inner, (*place, index))


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

    def differing(self, other: Manifest) -> tuple[str, ...]:
        mine, theirs = self.model_dump(), other.model_dump()
        return tuple(field for field, value in mine.items() if value != theirs[field])


class PluginListing(Metadata):
    """One plugin, as a marketplace lists it."""

    name: Name
    source: NonEmptyStr
    description: NonEmptyStr


class Marketplace(Metadata):
    """A marketplace file that lists the plugin for a host to install from."""

    name: Name
    owner: Person
    plugins: tuple[PluginListing, ...]

    @property
    @abstractmethod
    def description(self) -> str: ...


class ClaudeMarketplace(Marketplace):
    """The Claude Code marketplace, which describes itself at its top level."""

    summary: NonEmptyStr = Field(alias="description")

    @property
    def description(self) -> str:
        return self.summary


class MarketplaceDetails(Metadata):
    """What a Cursor marketplace says about itself."""

    description: NonEmptyStr


class CursorMarketplace(Marketplace):
    """The Cursor marketplace, which describes itself under its metadata."""

    metadata: MarketplaceDetails

    @property
    def description(self) -> str:
        return self.metadata.description


class Exports(Metadata):
    """The one export OpenCode loads, which points at the loader."""

    LOADER: ClassVar[PurePosixPath] = PurePosixPath(*get_args(LoaderExport.__value__))
    loader: Annotated[LoaderExport, Field(alias=".")]


class Package(Metadata):
    """The package file through which OpenCode loads the plugin's loader."""

    name: NonEmptyStr
    version: Version
    type: Literal["module"]
    exports: Exports
