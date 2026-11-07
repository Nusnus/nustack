"""A value that breaks its schema becomes Problems naming each field and its fix.

A text pattern written once serves a field's check and any larger pattern.
"""

import re
from typing import Annotated
lazy from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import HttpUrl
from pydantic import ValidationError

from nustack.validation import JsonObject
from nustack.validation import Pattern
from nustack.validation import Schema
from nustack.validation import UnmappedErrorTypeError


class TestPattern:
    """A text rule written once serves a field's check and any larger pattern.

    Inside a larger pattern it drops its anchors, and it counts as blank what the
    loader counts as blank.
    """

    def test_counts_as_blank_the_characters_the_loader_counts_as_blank(
        self, repository_root: Path
    ) -> None:
        loader = (repository_root / "plugin/opencode.ts").read_text()
        blank = re.search(r"static readonly BLANK =\s*/\^\[(.+)\]\*\$/", loader)
        assert blank is not None
        assert f"[^{blank[1]}]" == Pattern.NON_BLANK

    @pytest.mark.parametrize(
        ("pattern", "fix"),
        [
            (Pattern.NON_BLANK, "fill it in; it is blank"),
            (Pattern.NAME, "use kebab case, such as nus-mode"),
            (
                Pattern.VERSION,
                "use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1",
            ),
            (
                Pattern.SHA,
                (
                    "use 40 lowercase hex digits, such as"
                    " 81c986c0e0a7c511f2941ed3cec09f7975687f80"
                ),
            ),
            (
                Pattern.OWNER,
                (
                    "use letters, digits and single hyphens, with no hyphen first or"
                    " last, such as Nusnus, and for a managed user an underscore and"
                    " its enterprise's short code at the end, such as mona-cat_octo"
                ),
            ),
            (
                Pattern.REPOSITORY,
                (
                    "use letters, digits, '.', '-' and '_', other than . and .., such"
                    " as nustack"
                ),
            ),
            (
                Pattern.HOST,
                (
                    "use labels of letters, digits and hyphens, joined by dots, with no"
                    " hyphen first or last in a label, such as github.com"
                ),
            ),
        ],
    )
    def test_names_the_fix_for_a_value_that_misses_it(
        self, pattern: Pattern, fix: str
    ) -> None:
        assert pattern.fix == fix

    def test_drops_its_anchors_to_sit_inside_another_pattern(self) -> None:
        assert Pattern.VERSION.unanchored == (
            r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
        )


class TestJsonObject:
    """A JSON object keeps each of its pairs in order, a repeated key included."""

    def test_keeps_each_pair_of_a_repeated_key(self) -> None:
        assert JsonObject.of([("a", 1), ("a", 2)]).pairs == (("a", 1), ("a", 2))


class TestSchema:
    """Every way a value breaks its schema reaches the user as a field and a fix.

    An error type with no fix is refused rather than shown without one, and a place
    shows a key the file names in a mapping as <key>, never as the key itself, even
    one that reads as the part pydantic places after a key that fails.
    """

    class Outer(BaseModel):
        """A model that holds the nested one in a list."""

        model_config = ConfigDict(extra="forbid")

        class Inner(BaseModel):
            """A plain, a dashed and a dotted key, so a place shows which it quotes."""

            model_config = ConfigDict(extra="forbid")

            plain: str
            dashed_key: str = Field(alias="dashed-key")
            dotted: str = Field(alias="a.b")

        inner: tuple[Inner, ...]
        name: str = Field(pattern=Pattern.NAME.value)

    class Counted(BaseModel):
        """A model whose field fails with an error type no harness model meets.

        Its field, left out, also shows a missing key's fix.
        """

        count: int

    class Typed(BaseModel):
        """A model with one field per error type that has a fixed fix."""

        model_config = ConfigDict(strict=True)

        text: str = "a"
        flag: bool = True
        items: tuple[str, ...] = ()
        table: frozendict[str, str] = frozendict()
        link: HttpUrl = HttpUrl("https://example.com")
        required: str

    class Keyed(BaseModel):
        """A model that holds the nested one under keys a file names."""

        tables: frozendict[str, TestSchema.Outer]

    class Shaped(BaseModel):
        """A model with a mapping, tuple or list in each shape a place walks through."""

        model_config = ConfigDict(strict=True)

        pairs: frozendict[tuple[str, str], str] = frozendict()
        optional_table: frozendict[str, str] | None = None
        optional_inner: tuple[TestSchema.Outer.Inner, ...] | None = None
        listed: list[str] = Field(default_factory=list)
        nested: frozendict[str, frozendict[str, str]] = frozendict()

    class Mapped(BaseModel):
        """A model with a mapping field, whose keys and values each have a pattern."""

        model_config = ConfigDict(extra="forbid")

        files: frozendict[
            Annotated[str, Field(pattern=Pattern.NAME.value)],
            Annotated[str, Field(pattern=Pattern.SHA.value)],
        ]
        name: str = "a"

    def test_labels_every_key_at_every_depth(self) -> None:
        assert Schema(self.Outer).labels == {
            "inner",
            "name",
            "plain",
            "dashed-key",
            "a.b",
        }

    def test_names_the_place_and_the_fix_of_each_error(self) -> None:
        with pytest.raises(ValidationError) as caught:
            self.Outer.model_validate(
                {
                    "inner": [{"plain": "x", "dashed-key": "y", "a.b": 1, "odd": 2}],
                    "name": "Bad",
                    "extra": 3,
                }
            )
        assert Schema(self.Outer).reason(caught.value) == (
            'inner.0."a.b": make it a string; '
            "inner.0.an unknown key: rename it or remove it; nustack allows only"
            ' plain, dashed-key, "a.b" here; '
            "name: use kebab case, such as nus-mode; "
            "an unknown key: rename it or remove it; nustack allows only inner,"
            " name here"
        )

    @pytest.mark.parametrize(
        ("change", "reason"),
        [
            ({"required": None}, "required: make it a string"),
            ({"text": 1}, "text: make it a string"),
            ({"flag": "yes"}, "flag: make it true or false"),
            ({"items": "a"}, "items: make it a list"),
            ({"table": []}, "table: make it an object of keys and values"),
            (
                {"link": "nowhere"},
                "link: use a full http or https URL, such as https://example.com",
            ),
            (
                {"link": "ftp://example.com"},
                "link: use a full http or https URL, such as https://example.com",
            ),
            (
                {"link": "https://example.com/" + "a" * 2100},
                "link: shorten it to at most 2083 characters",
            ),
            (
                {"link": 1},
                "link: use a full http or https URL, such as https://example.com",
            ),
        ],
    )
    def test_names_the_fix_for_each_error_type_it_maps(
        self, change: dict[str, object], reason: str
    ) -> None:
        with pytest.raises(ValidationError) as caught:
            self.Typed.model_validate({"required": "a"} | change)
        assert Schema(self.Typed).reason(caught.value) == reason

    def test_names_the_fix_for_an_error_type_it_has_a_fix_for(self) -> None:
        with pytest.raises(ValidationError) as caught:
            self.Counted.model_validate({})
        assert Schema(self.Counted).reason(caught.value) == "count: add it"

    def test_refuses_an_error_type_it_has_no_fix_for(self) -> None:
        with pytest.raises(ValidationError) as invalid:
            self.Counted.model_validate({"count": "many"})
        with pytest.raises(UnmappedErrorTypeError) as caught:
            Schema(self.Counted).reason(invalid.value)
        assert str(caught.value) == (
            "pydantic's error type 'int_parsing' has no fix; add one to Schema.fix,"
            " with a test"
        )

    def test_places_an_error_in_a_mappings_key_or_value_without_its_key(
        self,
    ) -> None:
        with pytest.raises(ValidationError) as caught:
            self.Mapped.model_validate({"files": {"Bad": "x"}})
        assert Schema(self.Mapped).reason(caught.value) == (
            "files: for each key, use kebab case, such as nus-mode; files.<key>: use"
            " 40 lowercase hex digits, such as 81c986c0e0a7c511f2941ed3cec09f7975687f80"
        )

    @pytest.mark.parametrize(
        ("content", "repeats"),
        [
            (
                b'{"name": "a", "name": "b"}',
                ["has the key 'name' more than once in the file; keep one"],
            ),
            (
                b'{"inner": [{"plain": "x", "plain": "y"}]}',
                ["has the key 'plain' more than once in inner.0; keep one"],
            ),
            (
                b'{"odd": {"k": 1, "k": 2}}',
                ["has an unknown key more than once in an unknown key; keep one"],
            ),
            (
                b'{"odd": {"x": {"k": 1, "k": 2}}}',
                ["has an unknown key more than once in an unknown key; keep one"],
            ),
            (
                b'{"odd": {"plain": 1, "plain": 2}}',
                ["has the key 'plain' more than once in an unknown key; keep one"],
            ),
        ],
    )
    def test_names_each_key_written_twice(
        self, content: bytes, repeats: list[str]
    ) -> None:
        assert Schema(self.Outer).repeats(content) == repeats

    def test_names_a_key_written_twice_in_a_mapping_without_the_key(self) -> None:
        assert Schema(self.Mapped).repeats(b'{"files": {"a": "1", "a": "2"}}') == [
            "has a key more than once in files; keep one"
        ]

    @pytest.mark.parametrize(
        "content",
        [
            b'{"name": "a", "inner": [{"plain": "x"}], "odd": {"k": 1}}',
            b'{"name": "a", "name"',
            b"\xff",
            b"[" * 100_000,
        ],
    )
    def test_finds_no_repeat_in_content_without_one_or_that_does_not_parse(
        self, content: bytes
    ) -> None:
        assert Schema(self.Outer).repeats(content) == []

    def test_refuses_content_naming_its_repeats_then_its_errors(self) -> None:
        content = b'{"name": "Bad", "name": "Bad"}'
        with pytest.raises(ValidationError) as caught:
            self.Outer.model_validate_json(content)
        assert Schema(self.Outer).refusal(content, caught.value) == (
            "has the key 'name' more than once in the file; keep one; inner: add it;"
            " name: use kebab case, such as nus-mode"
        )

    def test_refuses_content_by_its_repeats_alone_without_an_error(self) -> None:
        assert Schema(self.Outer).refusal(b'{"name": "a", "name": "b"}') == (
            "has the key 'name' more than once in the file; keep one"
        )

    def test_names_the_file_for_an_error_at_its_top(self) -> None:
        with pytest.raises(ValidationError) as caught:
            self.Outer.model_validate([])
        assert Schema(self.Outer).reason(caught.value) == (
            "the file: make it an object of keys and values"
        )

    def test_names_no_mapping_key_in_a_place(self) -> None:
        with pytest.raises(ValidationError) as caught:
            self.Keyed.model_validate(
                {
                    "tables": {
                        1: {"inner": [], "name": "a"},
                        "secret": {
                            "inner": [{"plain": 1, "dashed-key": "x", "a.b": "y"}],
                            "name": "a",
                            "odd": 2,
                        },
                        "[key]": 1,
                    }
                }
            )
        assert Schema(self.Keyed).reason(caught.value) == (
            "tables: for each key, make it a string; tables.<key>.inner.0.plain:"
            " make it a string; tables.<key>.an unknown key: rename it or remove it;"
            " nustack allows only inner, name here; tables.<key>: make it an object of"
            " keys and values"
        )

    def test_names_the_place_through_each_mapping_tuple_and_list(self) -> None:
        with pytest.raises(ValidationError) as caught:
            self.Shaped.model_validate(
                {
                    "pairs": frozendict({("a", 1): "x"}),
                    "optional_table": frozendict({"a": 1}),
                    "optional_inner": (
                        {"plain": 1, "dashed-key": "x", "a.b": "y", "odd": 2},
                    ),
                    "listed": [1],
                    "nested": frozendict(
                        {"a": frozendict({"b": 1}), "c": frozendict({2: "x"})}
                    ),
                }
            )
        assert Schema(self.Shaped).reason(caught.value) == (
            "pairs: for each key, make it a string; optional_table.<key>: make it a"
            " string;"
            " optional_inner.0.plain: make it a string; optional_inner.0.an unknown"
            ' key: rename it or remove it; nustack allows only plain, dashed-key, "a.b"'
            " here; listed.0: make it a string;"
            " nested.<key>.<key>: make it a string; nested.<key>: for each key, make"
            " it a string"
        )
