"""A release tag publishes only from main and only when it names the plugin version.

A release before v0.1.0 publishes as a pre-release.
"""

from pathlib import Path

import pytest

from nustack.problem import Problem
from nustack.release import Publication
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


class TestPublication:
    """A release before v0.1.0 is a pre-release, and none from v0.1.0 on is."""

    @pytest.mark.parametrize(
        ("tag", "prerelease"),
        [("v0.0.1", True), ("v0.1.0", False), ("v1.0.0", False)],
    )
    def test_is_a_pre_release_only_before_0_1_0(
        self, tag: str, *, prerelease: bool
    ) -> None:
        assert Publication(tag, "commit", Path()).prerelease is prerelease
