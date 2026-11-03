"""A value that breaks its schema becomes Problems naming each field and its fix.

A text pattern written once serves a field's check and any larger pattern.
"""

import re
lazy from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import HttpUrl
from pydantic import ValidationError

from nustack.validation import Pattern
from nustack.validation import Schema
from nustack.validation import UnmappedErrorTypeError


class TestPattern:
    """A text rule written once serves a field's check and any larger pattern.

    Inside a larger pattern it drops its anchors, and it counts as blank what the
    loader counts as blank.
    """

    @pytest.mark.parametrize(
        ("pattern", "fix"),
        [
            (Pattern.NON_BLANK, "fill it in; it is blank"),
            (Pattern.NAME, "use kebab case, such as nus-mode"),
            (
                Pattern.VERSION,
                "use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1",
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

    def test_counts_as_blank_the_characters_the_loader_counts_as_blank(
        self, repository_root: Path
    ) -> None:
        loader = (repository_root / "plugin/opencode.ts").read_text()
        blank = re.search(r"static readonly BLANK =\s*/\^\[(.+)\]\*\$/", loader)
        assert blank is not None
        assert f"[^{blank[1]}]" == Pattern.NON_BLANK


class TestSchema:
    """Every way a value breaks its schema reaches the user as a field and a fix.

    An error type with no fix is refused rather than shown without one.
    """

    class Outer(BaseModel):
        """A model that holds the nested one in a list."""

        model_config = ConfigDict(extra="forbid")

        class Inner(BaseModel):
            """A nested model."""

            model_config = ConfigDict(extra="forbid")

            plain: str
            dashed_key: str = Field(alias="dashed-key")
            dotted: str = Field(alias="a.b")

        inner: tuple[Inner, ...]
        name: str = Field(pattern=Pattern.NAME.value)

    class Counted(BaseModel):
        """A model whose field fails with an error type no harness model meets."""

        count: int

    class Typed(BaseModel):
        """A model with one field per error type that has a fixed fix."""

        model_config = ConfigDict(strict=True)

        text: str = "a"
        flag: bool = True
        items: tuple[str, ...] = ()
        link: HttpUrl = HttpUrl("https://example.com")
        required: str

    @pytest.mark.parametrize(
        ("change", "reason"),
        [
            ({"required": None}, "required: make it a string"),
            ({"text": 1}, "text: make it a string"),
            ({"flag": "yes"}, "flag: make it true or false"),
            ({"items": "a"}, "items: make it a list"),
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

    def test_names_the_fix_for_a_missing_key(self) -> None:
        with pytest.raises(ValidationError) as caught:
            self.Typed.model_validate({})
        assert Schema(self.Typed).reason(caught.value) == "required: add it"

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

    def test_names_the_file_for_an_error_at_its_top(self) -> None:
        with pytest.raises(ValidationError) as caught:
            self.Outer.model_validate([])
        assert Schema(self.Outer).reason(caught.value) == (
            "the file: make it an object of keys and values"
        )

    def test_refuses_an_error_type_it_has_no_fix_for(self) -> None:
        with pytest.raises(ValidationError) as caught:
            self.Counted.model_validate({"count": "many"})
        with pytest.raises(UnmappedErrorTypeError) as refused:
            Schema(self.Counted).reason(caught.value)
        assert str(refused.value) == (
            "pydantic's error type 'int_parsing' has no fix; add one to Schema.fix,"
            " with a test"
        )
