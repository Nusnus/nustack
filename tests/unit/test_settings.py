"""The suite's settings run every tier, cover every line and bound each smoke test.

make mutate leaves out the tests that check the line calling the YAML reader.
"""

import tomllib
lazy from pathlib import Path


class TestPytest:
    """Every tier under the tests folder runs."""

    def test_collects_every_tier_under_tests(self, pyproject: Path) -> None:
        settings = tomllib.loads(pyproject.read_text())["tool"]["pytest"]
        assert settings["testpaths"] == ["tests"]


class TestCoverage:
    """No code goes untested."""

    def test_requires_every_line_and_branch(self, pyproject: Path) -> None:
        settings = tomllib.loads(pyproject.read_text())["tool"]["coverage"]
        assert (settings["run"]["branch"], settings["report"]["fail_under"]) == (
            True,
            100,
        )


class TestSmoke:
    """make smoke stops a stalled host's test after two minutes."""

    def test_bounds_each_test_at_two_minutes(self, repository_root: Path) -> None:
        makefile = (repository_root / "Makefile").read_text()
        runs = [line for line in makefile.splitlines() if "bun --config=" in line]
        assert runs == [
            "\tbun --config=tests/fixtures/smoke/bunfig.toml test --timeout=120000"
        ]


class TestMutmut:
    """make mutate deselects the tests marked caller_line."""

    def test_deselects_the_caller_line_tests(self, pyproject: Path) -> None:
        settings = tomllib.loads(pyproject.read_text())["tool"]["mutmut"]
        selection = settings["pytest_add_cli_args_test_selection"]
        assert selection == [
            "-m",
            "not caller_line",
            "tests/integration/nustack",
            "tests/unit",
        ]
