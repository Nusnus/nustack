"""A release tag publishes only from main and only when it names the plugin version."""

import pytest

from nustack.problem import Problem
from nustack.release import Tag


class TestTag:
    """A tag off main or naming another version stops the release, naming the fix."""

    @pytest.mark.parametrize(
        ("name", "on_main", "problems"),
        [
            ("v1.2.3", True, []),
            (
                "v1.2.3",
                False,
                [
                    Problem(
                        "v1.2.3",
                        "is not on main; delete it and tag the commit the squash"
                        " merge made on main",
                    )
                ],
            ),
            (
                "v9.9.9",
                True,
                [
                    Problem(
                        "v9.9.9",
                        "does not match plugin version 1.2.3; delete it and tag"
                        " v1.2.3, or set the version as AGENTS.md's Releases section"
                        " says",
                    )
                ],
            ),
        ],
    )
    def test_names_each_reason_it_cannot_publish(
        self, name: str, problems: list[Problem], *, on_main: bool
    ) -> None:
        assert Tag(name).problems("1.2.3", on_main=on_main) == problems
