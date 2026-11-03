"""The schemas and text patterns a file's values are held to.

A value that breaks one becomes a Problem naming each field and its fix, and a text
pattern written once also serves the larger patterns built from it.
"""

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from typing import ClassVar
from typing import assert_never
from typing import get_args
lazy from collections.abc import Iterator

from pydantic import BaseModel
from pydantic import ValidationError
lazy from pydantic.fields import FieldInfo
lazy from pydantic_core import ErrorDetails


class UnmappedErrorTypeError(LookupError):
    """A pydantic error type that `Schema.fix` gives no fix for, a gap in nustack."""

    def __str__(self) -> str:
        return (
            f"pydantic's error type {self.args[0]!r} has no fix; "
            "add one to Schema.fix, with a test"
        )


class Pattern(StrEnum):
    """A text pattern a field must match, with the fix for a value that misses it."""

    NON_BLANK = (
        r"[^\t\n\v\f\r \x85\xa0\u1680\u2000-\u200d"
        r"\u2028\u2029\u202f\u205f\u2060\u3000\ufeff]"
    )
    NAME = r"^[a-z0-9]+(-[a-z0-9]+)*$"
    VERSION = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"

    @property
    def fix(self) -> str:
        match self:
            case Pattern.NON_BLANK:
                return "fill it in; it is blank"
            case Pattern.NAME:
                return "use kebab case, such as nus-mode"
            case Pattern.VERSION:
                return "use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"
            case unexpected:
                assert_never(unexpected)

    @property
    def unanchored(self) -> str:
        return self.removeprefix("^").removesuffix("$")


@dataclass(frozen=True)
class Schema:
    """A pydantic model, read as the keys a file may hold and where each sits."""

    UNKNOWN_KEY: ClassVar[str] = "an unknown key"
    FIXES: ClassVar[frozendict[str, str]] = frozendict(
        {
            "missing": "add it",
            "string_type": "make it a string",
            "bool_type": "make it true or false",
            "model_type": "make it an object of keys and values",
            "tuple_type": "make it a list",
            **dict.fromkeys(
                ("url_parsing", "url_scheme", "url_type"),
                "use a full http or https URL, such as https://example.com",
            ),
        }
    )
    model: type[BaseModel]

    @cached_property
    def fields(self) -> frozendict[str, FieldInfo]:
        return frozendict(
            (field.alias or name, field)
            for name, field in self.model.model_fields.items()
        )

    @cached_property
    def labels(self) -> frozenset[str]:
        return frozenset(
            found
            for key, field in self.fields.items()
            for found in (
                key,
                *(
                    inner
                    for model in self.models_in(field.annotation)
                    for inner in Schema(model).labels
                ),
            )
        )

    def reason(self, error: ValidationError) -> str:
        return "; ".join(
            f"{self.place(detail['loc'])}: {self.fix(detail)}"
            for detail in error.errors()
        )

    def fix(self, detail: ErrorDetails) -> str:
        match detail:
            case {"type": "extra_forbidden", "loc": loc}:
                fix = self.unknown_key_fix(loc[:-1])
            case {"type": "string_pattern_mismatch", "ctx": {"pattern": str() as rule}}:
                fix = Pattern(rule).fix
            case {
                "type": "string_too_long" | "url_too_long",
                "ctx": {"max_length": int() as limit},
            }:
                fix = f"shorten it to at most {limit} characters"
            case {"type": "literal_error", "ctx": {"expected": str() as expected}}:
                fix = f"set it to {expected}"
            case {"type": "json_invalid", "ctx": {"error": str() as where}}:
                fix = f"fix the JSON ({where})"
            case {"type": "value_error", "ctx": {"error": ValueError() as refusal}}:
                fix = str(refusal)
            case {"type": kind} if kind in self.FIXES:
                fix = self.FIXES[kind]
            case _:
                raise UnmappedErrorTypeError(detail["type"])
        return fix

    def place(self, loc: tuple[str | int, ...]) -> str:
        return ".".join(self.label(part) for part in loc) or "the file"

    def unknown_key_fix(self, place: tuple[str | int, ...]) -> str:
        keys = ", ".join(self.label(key) for key in self.keys_at(place))
        return f"rename it or remove it; nustack allows only {keys} here"

    def keys_at(self, place: tuple[str | int, ...]) -> Iterator[str]:
        current = self
        for part in place:
            if isinstance(part, str):
                current = Schema(next(self.models_in(current.fields[part].annotation)))
        yield from current.fields

    def label(self, part: str | int) -> str:
        if isinstance(part, int):
            return str(part)
        if part not in self.labels:
            return self.UNKNOWN_KEY
        return part if re.fullmatch(r"[a-z][a-z0-9_-]*", part) else json.dumps(part)

    @classmethod
    def models_in(cls, annotation: object) -> Iterator[type[BaseModel]]:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield annotation
        for arg in get_args(annotation):
            yield from cls.models_in(arg)


def version_order(version: str) -> tuple[tuple[int, str], ...]:
    # Each part orders by its length, then its digits, since int() refuses a part
    # longer than Python's digit limit:
    # https://docs.python.org/3/library/stdtypes.html#int-max-str-digits
    return tuple((len(part), part) for part in version.split("."))
