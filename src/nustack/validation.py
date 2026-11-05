"""The schemas and text patterns that values read from outside are held to.

A value that breaks a schema becomes a Problem naming each field and its fix. A text
pattern carries the fix for a value that misses it, and written once also serves the
larger patterns built from it.
"""

import json
import re
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from typing import ClassVar
from typing import assert_never
from typing import get_args
from typing import get_origin
lazy from collections.abc import Iterator
lazy from collections.abc import Mapping

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
    # Git writes a commit's SHA-1 as 40 lowercase hex digits, as GitHub names it:
    # https://github.com/git/git/blob/v2.51.0/hex.c#L80-L83
    SHA = r"^[0-9a-f]{40}$"
    # GitHub's owner and repository names, as its sign-up and new-repository forms
    # take them: https://github.com/join and https://github.com/new. A managed user's
    # name ends in an underscore and its enterprise's short code, such as
    # mona-cat_octo:
    # https://docs.github.com/en/enterprise-cloud@latest/admin/managing-iam/iam-configuration-reference/username-considerations-for-external-authentication
    OWNER = r"^[A-Za-z0-9](-?[A-Za-z0-9])*(_[A-Za-z0-9]+)?$"
    REPOSITORY = r"^(?!\.\.?$)[A-Za-z0-9._-]+$"
    # A host name is dot-separated labels of letters, digits and hyphens, with no
    # hyphen first or last: https://www.rfc-editor.org/rfc/rfc1123#section-2.1
    HOST = r"^[A-Za-z0-9](-*[A-Za-z0-9])*(\.[A-Za-z0-9](-*[A-Za-z0-9])*)*$"

    @property
    def fix(self) -> str:  # noqa: PLR0911 -- one return per member
        match self:
            case Pattern.NON_BLANK:
                return "fill it in; it is blank"
            case Pattern.NAME:
                return "use kebab case, such as nus-mode"
            case Pattern.VERSION:
                return "use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"
            case Pattern.SHA:
                return (
                    "use 40 lowercase hex digits, such as"
                    " 81c986c0e0a7c511f2941ed3cec09f7975687f80"
                )
            case Pattern.OWNER:
                return (
                    "use letters, digits and single hyphens, with no hyphen first or"
                    " last, such as Nusnus, and for a managed user an underscore and"
                    " its enterprise's short code at the end, such as mona-cat_octo"
                )
            case Pattern.REPOSITORY:
                return (
                    "use letters, digits, '.', '-' and '_', other than . and .., such"
                    " as nustack"
                )
            case Pattern.HOST:
                return (
                    "use labels of letters, digits and hyphens, joined by dots, with no"
                    " hyphen first or last in a label, such as github.com"
                )
            case unexpected:
                assert_never(unexpected)

    @property
    def unanchored(self) -> str:
        return self.removeprefix("^").removesuffix("$")


@dataclass(frozen=True)
class JsonObject:
    """A JSON object's key-value pairs in their order, each repeated key kept."""

    pairs: tuple[tuple[str, object], ...]

    @classmethod
    def of(cls, pairs: list[tuple[str, object]]) -> JsonObject:
        return cls(tuple(pairs))


@dataclass(frozen=True)
class Schema:
    """A pydantic model, read as the keys a file may hold and where each sits."""

    UNKNOWN_KEY: ClassVar[str] = "an unknown key"
    # A mapping's key is a value read from the file, so its place names no key.
    MAPPING_KEY: ClassVar[str] = "<key>"
    # pydantic places an error in a mapping's key at that key, then this part, then
    # the place inside the key; a place stops at the mapping, and its fix speaks of
    # each key:
    # https://github.com/pydantic/pydantic/blob/v2.14.2/pydantic-core/src/validators/dict.rs#L133-L134
    KEY_ERROR: ClassVar[str] = "[key]"
    FIXES: ClassVar[frozendict[str, str]] = frozendict(
        {
            "missing": "add it",
            "string_type": "make it a string",
            "bool_type": "make it true or false",
            **dict.fromkeys(
                ("model_type", "frozen_dict_type"),
                "make it an object of keys and values",
            ),
            "tuple_type": "make it a list",
            "path_type": "make it a string",
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

    def refusal(self, content: bytes, error: ValidationError | None = None) -> str:
        return "; ".join(
            [*self.repeats(content), *([] if error is None else [self.reason(error)])]
        )

    # json keeps only the last of repeated keys, so this pass finds them first,
    # with numbers left as text, and leaves every other error to Pydantic:
    # https://docs.python.org/3/library/json.html#repeated-names-within-an-object
    def repeats(self, content: bytes) -> list[str]:
        with suppress(json.JSONDecodeError, UnicodeDecodeError, RecursionError):
            return list(
                self.repeats_in(
                    json.loads(content, object_pairs_hook=JsonObject.of, parse_int=str),
                    (),
                )
            )
        return []

    def repeats_in(self, value: object, place: tuple[str | int, ...]) -> Iterator[str]:
        match value:
            case JsonObject(pairs=pairs):
                keys = [name for name, _ in pairs]
                for key in dict.fromkeys(keys):
                    if keys.count(key) > 1:
                        if self.mapping_value(self.annotation_at(place)) is not None:
                            what = "a key"
                        elif key in self.labels:
                            what = f"the key {key!r}"
                        else:
                            what = self.UNKNOWN_KEY
                        yield (
                            f"has {what} more than once in {self.place(place)}; "
                            "keep one"
                        )
                for key, inner in pairs:
                    yield from self.repeats_in(inner, (*place, key))
            case list():
                for index, inner in enumerate(value):
                    yield from self.repeats_in(inner, (*place, index))

    def reason(self, error: ValidationError) -> str:
        return "; ".join(self.located_fix(detail) for detail in error.errors())

    # A model validator's refusal has no place, so its message opens on the fields
    # it holds together.
    def located_fix(self, detail: ErrorDetails) -> str:
        if detail["type"] == "value_error" and not detail["loc"]:
            return self.fix(detail)
        labels = tuple(self.labels_along(detail["loc"]))
        if labels[-1:] == (self.KEY_ERROR,):
            return f"{self.joined(labels[:-1])}: for each key, {self.fix(detail)}"
        return f"{self.joined(labels)}: {self.fix(detail)}"

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

    # Pydantic places an error in a mapping's key at the key, then at KEY, and one
    # in its value at the key alone, so the place names the mapping and repeats no
    # key read from the file.
    def place(self, loc: tuple[str | int, ...]) -> str:
        return self.joined(tuple(self.labels_along(loc)))

    # A run of unknown keys reads as one, since none of them can be named.
    def joined(self, labels: tuple[str, ...]) -> str:
        return (
            ".".join(
                label
                for index, label in enumerate(labels)
                if index == 0 or not label == labels[index - 1] == self.UNKNOWN_KEY
            )
            or "the file"
        )

    def labels_along(self, loc: tuple[str | int, ...]) -> Iterator[str]:
        annotation: object = self.model
        for index, part in enumerate(loc):
            if (value := self.mapping_value(annotation)) is not None:
                if loc[index + 1 : index + 2] == (self.KEY_ERROR,):
                    yield self.KEY_ERROR
                    return
                yield self.MAPPING_KEY
                annotation = value
            else:
                yield self.label(part)
                annotation = self.inner(annotation, part)

    def annotation_at(self, place: tuple[str | int, ...]) -> object:
        annotation: object = self.model
        for part in place:
            value = self.mapping_value(annotation)
            annotation = self.inner(annotation, part) if value is None else value
        return annotation

    def unknown_key_fix(self, place: tuple[str | int, ...]) -> str:
        keys = ", ".join(self.label(key) for key in self.keys_at(place))
        return f"rename it or remove it; nustack allows only {keys} here"

    def keys_at(self, place: tuple[str | int, ...]) -> Iterator[str]:
        yield from Schema(next(self.models_in(self.annotation_at(place)))).fields

    def label(self, part: str | int) -> str:
        if isinstance(part, int):
            return str(part)
        if part not in self.labels:
            return self.UNKNOWN_KEY
        return part if re.fullmatch(r"[a-z][a-z0-9_-]*", part) else json.dumps(part)

    @staticmethod
    def mapping_value(annotation: object) -> object | None:
        return next(
            (
                get_args(arg)[1]
                for arg in (annotation, *get_args(annotation))
                if isinstance(origin := get_origin(arg), type)
                and issubclass(origin, Mapping)
            ),
            None,
        )

    @classmethod
    def inner(cls, annotation: object, part: str | int) -> object:
        if isinstance(part, int):
            return next(
                (
                    get_args(arg)[0]
                    for arg in (annotation, *get_args(annotation))
                    if get_origin(arg) is tuple
                ),
                None,
            )
        return next(
            (
                Schema(model).fields[part].annotation
                for model in cls.models_in(annotation)
                if part in Schema(model).fields
            ),
            None,
        )

    @classmethod
    def models_in(cls, annotation: object) -> Iterator[type[BaseModel]]:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            yield annotation
        for arg in get_args(annotation):
            yield from cls.models_in(arg)
