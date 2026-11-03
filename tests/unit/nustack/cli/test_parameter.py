"""Each parser of the command's values takes a nonempty one and refuses ''."""

from pathlib import Path

import pytest
import typer

from nustack.cli.parameter import nonempty
from nustack.cli.parameter import path
from nustack.cli.parameter import path_text
from nustack.cli.parameter import text


class TestPath:
    """A path option reads as a Path, and an empty one fails asking for a path."""

    def test_reads_a_path(self) -> None:
        assert path("dist/out") == Path("dist/out")

    def test_refuses_an_empty_path(self) -> None:
        with pytest.raises(
            typer.BadParameter, match=r"^give a path, not an empty string$"
        ):
            path("")


class TestPathText:
    """A path Git names as text stays text, and an empty one fails asking for a path."""

    def test_keeps_the_path_as_text(self) -> None:
        assert path_text("skills/writing") == "skills/writing"

    def test_refuses_an_empty_path(self) -> None:
        with pytest.raises(
            typer.BadParameter, match=r"^give a path, not an empty string$"
        ):
            path_text("")


class TestText:
    """A value that is no path stays as given; an empty one fails asking for a value."""

    def test_keeps_the_value(self) -> None:
        assert text("owner/name") == "owner/name"

    def test_refuses_an_empty_value(self) -> None:
        with pytest.raises(
            typer.BadParameter, match=r"^give a value, not an empty string$"
        ):
            text("")


class TestNonempty:
    """A nonempty value, even one of only spaces, passes through.

    TestPath, TestPathText and TestText test the refusal.
    """

    def test_passes_a_nonempty_value_through(self) -> None:
        assert nonempty(" ", "name") == " "
