"""A release tag publishes only from main and only when it names the plugin version.

It reads from and as v<version>, refusing text of another form with the fix, and a
release before v0.1.0 publishes as a pre-release.
"""

import pytest

from nustack.problem import Problem
from nustack.release.tag import Tag
from nustack.release.tag import TagError
from nustack.sha import Sha


class TestTag:
    """A tag off main, naming another version or moved off its commit stops the release.

    A release before v0.1.0 is a pre-release, and none from v0.1.0 on is. Text given as
    v<version> reads as that version's tag; any other form fails, and so does a tag
    built from a version of another form.
    """

    @pytest.mark.parametrize(
        ("version", "prerelease"),
        [("0.0.1", True), ("0.1.0", False), ("1.0.0", False)],
    )
    def test_is_a_pre_release_only_before_0_1_0(
        self, version: str, *, prerelease: bool
    ) -> None:
        assert Tag(version).prerelease is prerelease

    def test_refuses_a_version_of_another_form(self) -> None:
        with pytest.raises(TagError) as caught:
            Tag("garbage")
        assert str(caught.value) == (
            "build the tag from a version; use MAJOR.MINOR.PATCH without leading zeros,"
            " such as 0.0.1"
        )

    @pytest.mark.parametrize(
        ("version", "on_main", "problems"),
        [
            ("1.2.3", True, []),
            (
                "1.2.3",
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
                "9.9.9",
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
        self, version: str, problems: list[Problem], *, on_main: bool
    ) -> None:
        assert Tag(version).problems("1.2.3", on_main=on_main) == problems

    def test_has_not_moved_while_it_names_the_commit_ci_passed_on(self) -> None:
        assert Tag("1.2.3").moved(Sha("a" * 40), Sha("a" * 40)) is None

    def test_names_a_tag_that_moved_off_the_commit_ci_passed_on(self) -> None:
        assert Tag("1.2.3").moved(Sha("a" * 40), Sha("b" * 40)) == Problem(
            "v1.2.3",
            "has moved off the commit CI passed on; the run the move started"
            " publishes it",
        )

    def test_reads_the_version(self) -> None:
        assert Tag.parse("v1.2.3") == Tag("1.2.3")

    @pytest.mark.parametrize(
        ("value", "what"),
        [
            (
                "1.2.3",
                (
                    "give the tag as v<version>, not 1.2.3; for its version, use "
                    "MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"
                ),
            ),
            (
                "v1.2",
                (
                    "give the tag as v<version>, not v1.2; for its version, use "
                    "MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"
                ),
            ),
            (
                "v01.2.3",
                (
                    "give the tag as v<version>, not v01.2.3; for its version, use "
                    "MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"
                ),
            ),
            (
                "v1.2.3\n",
                (
                    "give the tag as v<version>, not v1.2.3\n; for its version, use "
                    "MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"
                ),
            ),
        ],
    )
    def test_refuses_a_tag_of_another_form(self, value: str, what: str) -> None:
        with pytest.raises(TagError) as caught:
            Tag.parse(value)
        assert str(caught.value) == what

    def test_reads_as_v_and_its_version(self) -> None:
        assert str(Tag("1.2.3")) == "v1.2.3"
