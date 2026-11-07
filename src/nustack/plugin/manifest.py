"""The JSON files through which hosts and marketplaces find the plugin.

The manifests, the marketplaces and the loader's package are each read in key
order, every repeated key kept, and held to the fields their host accepts. A file
that is not valid JSON, or a field that breaks its schema, is refused with the fix.
"""

from abc import abstractmethod
from pathlib import PurePosixPath
from typing import Annotated
from typing import ClassVar
from typing import Literal
from typing import Self
from typing import get_args

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import HttpUrl
from pydantic import ValidationError
from pydantic import field_validator

from nustack.github.name import RepositoryUrl
from nustack.validation import Pattern
from nustack.validation import Schema
from nustack.version import Version

type NonEmptyStr = Annotated[str, Field(pattern=Pattern.NON_BLANK.value)]
type Name = Annotated[str, Field(pattern=Pattern.NAME.value)]
type LoaderExport = Literal["./opencode.ts"]


class InvalidMetadataError(ValueError):
    """A metadata file that is not valid JSON, or breaks its schema."""


class Metadata(BaseModel):
    """JSON metadata a host reads, which allows no unknown field and never changes.

    nustack writes these files itself, so an unknown field in one is its own typo.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def parse(cls, content: bytes) -> Self:
        schema = Schema(cls)
        try:
            metadata = cls.model_validate_json(content)
        except ValidationError as error:
            raise InvalidMetadataError(schema.refusal(content, error)) from error
        if refusal := schema.refusal(content):
            raise InvalidMetadataError(refusal)
        return metadata


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
    repository: RepositoryUrl
    license: NonEmptyStr

    # The changelog's and release page's links add GitHub's paths to it.
    @field_validator("repository", mode="before")
    @classmethod
    def repository_of_url(cls, value: object) -> object:
        return RepositoryUrl.parse(str(value))

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
