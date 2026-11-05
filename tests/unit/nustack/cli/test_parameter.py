"""Each parser of the command's values takes a nonempty one and refuses ''.

The repository and tag parsers also refuse what their types' parse refuses, with its
fix, the version parser a version of the wrong form, with the fix, and the commit
parser a commit of the wrong form.
"""

from pathlib import Path

import pytest
import typer

from nustack.cli.parameter import commit
from nustack.cli.parameter import name_with_owner
from nustack.cli.parameter import nonempty
from nustack.cli.parameter import path
from nustack.cli.parameter import path_text
from nustack.cli.parameter import tag
from nustack.cli.parameter import text
from nustack.cli.parameter import version
from nustack.github.name import NameWithOwner
from nustack.release.tag import Tag
from nustack.sha import Sha


class TestPath:
    """A path option reads as a Path, and an empty one fails asking for a path."""

    def test_reads_a_path(self) -> None:
        assert path("dist/out") == Path("dist/out")

    def test_refuses_an_empty_path(self) -> None:
        with pytest.raises(
            typer.BadParameter, match=r"^give a path, not an empty string$"
        ):
            path("")


class TestNameWithOwner:
    """A repository's name reads as its type parses it; a refusal fails as given."""

    def test_reads_the_owner_and_the_name(self) -> None:
        assert name_with_owner("o/r") == NameWithOwner("o", "r")

    def test_refuses_what_its_type_refuses(self) -> None:
        with pytest.raises(typer.BadParameter) as caught:
            name_with_owner("o")
        assert str(caught.value) == "give the repository as <owner>/<name>, not o"

    def test_refuses_an_empty_value(self) -> None:
        with pytest.raises(
            typer.BadParameter, match=r"^give a value, not an empty string$"
        ):
            name_with_owner("")


class TestVersion:
    """A version reads as given; one of another form is refused with its fix."""

    def test_reads_the_version(self) -> None:
        assert version("0.10.0") == "0.10.0"

    def test_refuses_a_version_of_another_form(self) -> None:
        with pytest.raises(typer.BadParameter) as caught:
            version("v0.1.0")
        assert str(caught.value) == (
            "give the version as MAJOR.MINOR.PATCH, not v0.1.0; use MAJOR.MINOR.PATCH"
            " without leading zeros, such as 0.0.1"
        )

    def test_refuses_an_empty_value(self) -> None:
        with pytest.raises(
            typer.BadParameter, match=r"^give a value, not an empty string$"
        ):
            version("")


class TestTag:
    """A tag reads as its type parses it; a refusal fails as given."""

    def test_reads_the_version(self) -> None:
        assert tag("v1.2.3") == Tag("1.2.3")

    def test_refuses_what_its_type_refuses(self) -> None:
        with pytest.raises(typer.BadParameter) as caught:
            tag("1.2.3")
        assert str(caught.value) == (
            "give the tag as v<version>, not 1.2.3; for its version, use"
            " MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"
        )

    def test_refuses_an_empty_value(self) -> None:
        with pytest.raises(
            typer.BadParameter, match=r"^give a value, not an empty string$"
        ):
            tag("")


class TestCommit:
    """A commit reads as its type parses it; a refusal fails as given."""

    def test_keeps_the_sha(self) -> None:
        assert commit("81c986c0e0a7c511f2941ed3cec09f7975687f80") == Sha(
            "81c986c0e0a7c511f2941ed3cec09f7975687f80"
        )

    def test_refuses_what_its_type_refuses(self) -> None:
        with pytest.raises(typer.BadParameter) as caught:
            commit("81c986c")
        assert str(caught.value) == (
            "give the commit as its SHA, not 81c986c; use 40 lowercase hex digits,"
            " such as 81c986c0e0a7c511f2941ed3cec09f7975687f80"
        )

    def test_refuses_an_empty_value(self) -> None:
        with pytest.raises(
            typer.BadParameter, match=r"^give a value, not an empty string$"
        ):
            commit("")


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

    Each parser's class tests the refusal of an empty value.
    """

    def test_passes_a_nonempty_value_through(self) -> None:
        assert nonempty(" ", "name") == " "
