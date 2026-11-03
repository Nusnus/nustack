"""The suite's settings collect every tier and require every line and branch covered."""

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
