"""A version is MAJOR.MINOR.PATCH with no leading zeros.

Versions order as numbers do, part by part, however long each part is.
"""

import pytest
from pydantic import TypeAdapter
from pydantic import ValidationError

from nustack.version import Version
from nustack.version import version_order


class TestVersion:
    """A version is MAJOR.MINOR.PATCH, with no leading zeros."""

    @pytest.mark.parametrize(
        ("text", "version"), [("1.2.3", "1.2.3"), ("0.10.2", "0.10.2")]
    )
    def test_takes_a_release_version(self, text: str, version: str) -> None:
        assert TypeAdapter(Version).validate_python(text) == version

    @pytest.mark.parametrize("text", ["1.2", "01.2.3", "1.2.3-rc1"])
    def test_refuses_text_that_is_no_release_version(self, text: str) -> None:
        with pytest.raises(ValidationError):
            TypeAdapter(Version).validate_python(text)


class TestVersionOrder:
    """Each part orders by its value, even past Python's integer digit limit."""

    @pytest.mark.parametrize(
        ("lower", "higher"),
        [
            ("0.0.9", "0.0.10"),
            ("0.9.9", "1.0.0"),
            ("1.2.3", "1.10.0"),
            ("1.0.0", f"1.0.1{'0' * 5000}"),
        ],
    )
    def test_orders_versions_as_numbers(self, lower: str, higher: str) -> None:
        assert version_order(lower) < version_order(higher)

    def test_orders_a_version_equal_to_itself(self) -> None:
        assert version_order("1.2.3") == version_order("1.2.3")
