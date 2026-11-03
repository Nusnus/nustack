"""A Problem reads the same wherever a check reports it."""

from pathlib import Path

from nustack.problem import Problem


class TestProblem:
    """A report reads the same in every check's output, and duplicates collapse."""

    def test_reads_as_its_place_then_what_breaks(self) -> None:
        assert str(Problem(Path("/r/a.md"), "is missing; add it")) == (
            "/r/a.md: is missing; add it"
        )

    def test_can_key_a_set_since_it_never_changes(self) -> None:
        problems = {
            Problem(Path("/r/a.md"), "is missing"),
            Problem(Path("/r/a.md"), "is missing"),
        }
        assert len(problems) == 1
