"""A release publishes through gh from the zip and notes CI built, once per tag.

Publishing drafts the release when none exists, uploads the zips and publishes the
notes, as a pre-release before v0.1.0, only while the tag names the commit CI passed on,
and leaves a published release as it is.
"""

lazy from pathlib import Path

import pytest

from nustack.github import GitHub
from nustack.problem import Problem
from nustack.release import Publication
lazy from tests.fixtures.gh import FakeGh


class TestPublication:
    """A tag's release publishes from its commit's build, or names what stopped it.

    A tag naming another commit stops it, a release before v0.1.0 publishes as a
    pre-release, a published release is left alone, and a draft an earlier run left is
    published; a tag gone after the upload, or a failed gh, stops it.
    """

    TAG = ("api", "repos/o/r/commits/tags/v1.2.3", "--jq", ".sha")
    VIEW = (
        "release",
        "view",
        "v1.2.3",
        "-R",
        "o/r",
        "--json",
        "isDraft",
        "--jq",
        ".isDraft",
    )
    COMMIT = "81c986c0e0a7c511f2941ed3cec09f7975687f80"

    @pytest.fixture
    def zip_folder(self, tmp_path: Path) -> Path:
        zip_folder = tmp_path / "dist"
        zip_folder.mkdir()
        for name in ("b.zip", "a.zip", "notes.md"):
            (zip_folder / name).write_text(name)
        return zip_folder

    @pytest.fixture(autouse=True)
    def tagged(self, gh: FakeGh, github_fixtures: Path) -> None:
        gh.replay(*self.TAG, recording=github_fixtures / "tag-commit/found.json")

    def test_stops_when_the_tag_names_another_commit(
        self, gh: FakeGh, zip_folder: Path
    ) -> None:
        outcome = Publication("v1.2.3", "another", zip_folder).publish(GitHub("o/r"))
        assert (outcome, len(gh.calls)) == (
            Problem(
                "v1.2.3",
                "has moved off the commit CI passed on; the run the move started"
                " publishes it",
            ),
            1,
        )

    def test_drafts_uploads_and_publishes_a_new_release(
        self, gh: FakeGh, github_fixtures: Path, zip_folder: Path
    ) -> None:
        gh.replay(*self.VIEW, recording=github_fixtures / "release-state/missing.json")
        outcome = Publication("v1.2.3", self.COMMIT, zip_folder).publish(GitHub("o/r"))
        assert (outcome, [argv for argv, _ in gh.calls]) == (
            "Published release v1.2.3",
            [
                self.TAG,
                self.VIEW,
                (
                    "release",
                    "create",
                    "v1.2.3",
                    "-R",
                    "o/r",
                    "--draft",
                    "--verify-tag",
                    "--notes",
                    "",
                ),
                (
                    "release",
                    "upload",
                    "v1.2.3",
                    "-R",
                    "o/r",
                    str(zip_folder / "a.zip"),
                    str(zip_folder / "b.zip"),
                    "--clobber",
                ),
                self.TAG,
                (
                    "release",
                    "edit",
                    "v1.2.3",
                    "-R",
                    "o/r",
                    "--draft=false",
                    "--prerelease=false",
                    "--title",
                    "nustack 1.2.3",
                    "--notes-file",
                    str(zip_folder / "notes.md"),
                ),
            ],
        )

    @pytest.mark.parametrize(
        ("tag", "expected"),
        [
            (
                "v0.0.1",
                (
                    "Published release v0.0.1",
                    (
                        *("release", "edit", "v0.0.1", "-R", "o/r", "--draft=false"),
                        *("--prerelease", "--title", "nustack 0.0.1", "--notes-file"),
                    ),
                ),
            ),
            (
                "v0.1.0",
                (
                    "Published release v0.1.0",
                    (
                        *("release", "edit", "v0.1.0", "-R", "o/r", "--draft=false"),
                        *(
                            "--prerelease=false",
                            "--title",
                            "nustack 0.1.0",
                            "--notes-file",
                        ),
                    ),
                ),
            ),
        ],
    )
    def test_publishes_a_pre_release_only_before_0_1_0(
        self,
        gh: FakeGh,
        github_fixtures: Path,
        zip_folder: Path,
        tag: str,
        expected: tuple[str, tuple[str, ...]],
    ) -> None:
        gh.replay(
            *("api", f"repos/o/r/commits/tags/{tag}", "--jq", ".sha"),
            recording=github_fixtures / "tag-commit/found.json",
        )
        gh.replay(
            *("release", "view", tag, "-R", "o/r", "--json", "isDraft"),
            *("--jq", ".isDraft"),
            recording=github_fixtures / "release-state/draft.json",
        )
        outcome = Publication(tag, self.COMMIT, zip_folder).publish(GitHub("o/r"))
        message, argv = expected
        assert (outcome, gh.calls[-1][0]) == (
            message,
            (*argv, str(zip_folder / "notes.md")),
        )

    def test_leaves_a_published_release_as_it_is(
        self, gh: FakeGh, github_fixtures: Path, zip_folder: Path
    ) -> None:
        gh.replay(
            *self.VIEW, recording=github_fixtures / "release-state/published.json"
        )
        outcome = Publication("v1.2.3", self.COMMIT, zip_folder).publish(GitHub("o/r"))
        assert (outcome, len(gh.calls)) == (
            "Release v1.2.3 is already published, so it stays as it is",
            2,
        )

    def test_publishes_a_draft_an_earlier_run_left(
        self, gh: FakeGh, github_fixtures: Path, zip_folder: Path
    ) -> None:
        gh.replay(*self.VIEW, recording=github_fixtures / "release-state/draft.json")
        outcome = Publication("v1.2.3", self.COMMIT, zip_folder).publish(GitHub("o/r"))
        assert (outcome, [argv[:2] for argv, _ in gh.calls]) == (
            "Published release v1.2.3",
            [
                ("api", "repos/o/r/commits/tags/v1.2.3"),
                ("release", "view"),
                ("release", "upload"),
                ("api", "repos/o/r/commits/tags/v1.2.3"),
                ("release", "edit"),
            ],
        )

    def test_stops_before_publishing_when_the_tag_is_gone_after_the_upload(
        self, gh: FakeGh, github_fixtures: Path, zip_folder: Path
    ) -> None:
        gh.replay(*self.TAG, recording=github_fixtures / "tag-commit/missing.json")
        gh.replay(*self.VIEW, recording=github_fixtures / "release-state/missing.json")
        outcome = Publication("v1.2.3", self.COMMIT, zip_folder).publish(GitHub("o/r"))
        assert (outcome, gh.calls[-1][0][:2]) == (
            Problem(
                "v1.2.3",
                "cannot be read (gh api exited 1; fix the cause gh printed above, then"
                " rerun); push it again if it was deleted, then rerun",
            ),
            ("api", "repos/o/r/commits/tags/v1.2.3"),
        )

    def test_names_a_gh_command_that_failed(
        self, gh: FakeGh, github_fixtures: Path, zip_folder: Path
    ) -> None:
        gh.replay(*self.VIEW, recording=github_fixtures / "release-state/draft.json")
        gh.replay(
            "release",
            "upload",
            "v1.2.3",
            "-R",
            "o/r",
            str(zip_folder / "a.zip"),
            str(zip_folder / "b.zip"),
            "--clobber",
            recording=github_fixtures / "upload/missing.json",
        )
        outcome = Publication("v1.2.3", self.COMMIT, zip_folder).publish(GitHub("o/r"))
        assert outcome == Problem(
            "v1.2.3",
            "gh release exited 1; fix the cause gh printed above, then rerun",
        )
