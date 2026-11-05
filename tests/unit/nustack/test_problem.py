"""A Problem reads the same wherever a check reports it.

A file whose parser refuses its content reads as a Problem that the file is invalid.
"""

import tomllib
from pathlib import Path

import pytest

from nustack.problem import Problem


class TestProblem:
    """A report reads the same in every check's output, and duplicates collapse.

    Content parses to its value, and a parse error the caller names reads as invalid.
    """

    def test_can_key_a_set_since_it_never_changes(self) -> None:
        problems = {
            Problem(Path("/r/a.md"), "is missing"),
            Problem(Path("/r/a.md"), "is missing"),
        }
        assert len(problems) == 1

    def test_reads_as_its_place_then_what_breaks(self) -> None:
        assert str(Problem(Path("/r/a.md"), "is missing; add it")) == (
            "/r/a.md: is missing; add it"
        )

    def test_gives_the_parsed_value(self) -> None:
        assert Problem.parsed(Path("/r/a"), b"a: 1", bytes.decode, ValueError) == "a: 1"

    def test_reports_the_error_it_names_as_invalid(self) -> None:
        assert Problem.parsed(
            Path("/r/a"), b"\xff", bytes.decode, ValueError
        ) == Problem(
            Path("/r/a"),
            "is invalid: 'utf-8' codec can't decode byte 0xff in position 0:"
            " invalid start byte",
        )

    def test_lets_any_other_error_through(self) -> None:
        with pytest.raises(UnicodeDecodeError, match=r"^'utf-8' codec"):
            Problem.parsed(Path("/r/a"), b"\xff", bytes.decode, tomllib.TOMLDecodeError)
