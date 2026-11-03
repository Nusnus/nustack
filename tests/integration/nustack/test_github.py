"""GitHub, read and changed through gh, as the release and sync workflows need.

Each read parses gh's real reply, each change sends gh the arguments and input it
takes, and a failed or missing gh stops with an error naming the fix.
"""

lazy from pathlib import Path

import pytest

from nustack.github import GitHub
from nustack.github import GitHubError
lazy from tests.fixtures.gh import FakeGh


class TestGitHub:
    """The workflows get GitHub's answers, or an error naming what to do next.

    A repository gh cannot read, an empty default branch, a release it cannot read,
    a failed command or a missing gh stops it; a missing release reads as none. A
    reply no recording holds, such as an empty default branch or a 502 that GitHub
    sends only while it is failing, is written in the form of gh's recorded replies.
    """

    PULLS = (
        "api",
        "--method",
        "GET",
        "--paginate",
        "repos/o/r/pulls",
        "-f",
        "state=open",
        "-f",
        "base=main",
        "-f",
        "head=o:sync/w",
        "--jq",
        ".[] | select(.head.repo.id == .base.repo.id) | .number",
    )
    VIEW = (
        "release",
        "view",
        "v1",
        "-R",
        "o/r",
        "--json",
        "isDraft",
        "--jq",
        ".isDraft",
    )

    DEFAULT = ("api", "repos/o/r", "--jq", ".default_branch")

    def test_reads_the_default_branch(self, gh: FakeGh, github_fixtures: Path) -> None:
        gh.replay(
            *self.DEFAULT, recording=github_fixtures / "default-branch/found.json"
        )
        assert GitHub("o/r").default_branch() == "main"

    def test_stops_on_a_repository_gh_cannot_read(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *self.DEFAULT, recording=github_fixtures / "default-branch/missing.json"
        )
        with pytest.raises(GitHubError) as failed:
            GitHub("o/r").default_branch()
        assert str(failed.value) == (
            "gh api exited 1; fix the cause gh printed above, then rerun"
        )

    def test_stops_on_an_empty_default_branch(self, gh: FakeGh) -> None:
        gh.reply(*self.DEFAULT, stdout="\n")
        with pytest.raises(GitHubError) as failed:
            GitHub("o/r").default_branch()
        assert str(failed.value) == (
            "gh names no default branch for o/r; check that the token can read the"
            " repository"
        )

    @pytest.mark.parametrize(
        ("reply", "pulls"),
        [("open-pulls/one.json", (267,)), ("open-pulls/none.json", ())],
    )
    def test_lists_the_open_pull_requests_from_this_repositorys_branch(
        self, gh: FakeGh, github_fixtures: Path, reply: str, pulls: tuple[int, ...]
    ) -> None:
        gh.replay(*self.PULLS, recording=github_fixtures / reply)
        assert GitHub("o/r").open_pulls("main", "sync/w") == pulls

    def test_reads_a_pull_requests_description(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        body = gh.replay(
            "api",
            "repos/o/r/pulls/5",
            "--jq",
            ".body",
            recording=github_fixtures / "pull-body/found.json",
        )
        # The harness reads gh's output as text, which turns the body's CRLF line ends
        # into LF.
        assert GitHub("o/r").pull_body(5) == body.replace("\r\n", "\n")

    def test_opens_edits_and_closes_a_pull_request(self, gh: FakeGh) -> None:
        github = GitHub("o/r")
        github.create_pull("main", "sync/w", "docs: sync", "Body.\n")
        github.edit_pull(12, "New.\n")
        github.close_pull(12, "Nothing to propose.")
        assert gh.calls == [
            (
                (
                    "pr",
                    "create",
                    "-R",
                    "o/r",
                    "--base",
                    "main",
                    "--head",
                    "sync/w",
                    "--title",
                    "docs: sync",
                    "--body-file",
                    "-",
                ),
                "Body.\n",
            ),
            (("pr", "edit", "12", "-R", "o/r", "--body-file", "-"), "New.\n"),
            (
                (
                    "pr",
                    "close",
                    "12",
                    "-R",
                    "o/r",
                    "--delete-branch",
                    "--comment",
                    "Nothing to propose.",
                ),
                "",
            ),
        ]

    def test_reads_the_commit_a_tag_names(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            "api",
            "repos/o/r/commits/tags/v1",
            "--jq",
            ".sha",
            recording=github_fixtures / "tag-commit/found.json",
        )
        assert GitHub("o/r").tag_commit("v1") == (
            "81c986c0e0a7c511f2941ed3cec09f7975687f80"
        )

    def test_reads_a_published_release_as_no_draft(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *self.VIEW, recording=github_fixtures / "release-draft/published.json"
        )
        assert GitHub("o/r").release_draft("v1") is False

    def test_reads_a_draft_release_as_a_draft(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(*self.VIEW, recording=github_fixtures / "release-draft/draft.json")
        assert GitHub("o/r").release_draft("v1") is True

    def test_reads_a_missing_release_as_none(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(*self.VIEW, recording=github_fixtures / "release-draft/missing.json")
        assert GitHub("o/r").release_draft("v1") is None

    def test_names_why_a_release_cannot_be_read(self, gh: FakeGh) -> None:
        gh.reply(*self.VIEW, stderr="gh: Bad Gateway (HTTP 502)\n", code=1)
        with pytest.raises(GitHubError) as failed:
            GitHub("o/r").release_draft("v1")
        assert failed.value.what == (
            "release v1 cannot be read (gh: Bad Gateway (HTTP 502)); rerun once"
            " GitHub answers"
        )

    def test_drafts_uploads_to_and_publishes_a_release(
        self, gh: FakeGh, tmp_path: Path
    ) -> None:
        github = GitHub("o/r")
        github.create_draft("v1")
        github.upload("v1", (tmp_path / "a.zip", tmp_path / "b.zip"))
        github.publish("v1", "nustack 1", tmp_path / "notes.md")
        assert [argv for argv, _ in gh.calls] == [
            (
                "release",
                "create",
                "v1",
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
                "v1",
                "-R",
                "o/r",
                str(tmp_path / "a.zip"),
                str(tmp_path / "b.zip"),
                "--clobber",
            ),
            (
                "release",
                "edit",
                "v1",
                "-R",
                "o/r",
                "--draft=false",
                "--title",
                "nustack 1",
                "--notes-file",
                str(tmp_path / "notes.md"),
            ),
        ]

    def test_names_the_command_that_failed_and_the_next_step(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            "api",
            "repos/o/r/pulls/5",
            "--jq",
            ".body",
            recording=github_fixtures / "pull-body/missing.json",
        )
        with pytest.raises(GitHubError) as failed:
            GitHub("o/r").pull_body(5)
        assert str(failed.value) == (
            "gh api exited 1; fix the cause gh printed above, then rerun"
        )

    def test_names_a_missing_gh_and_where_to_get_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PATH", str(tmp_path))
        with pytest.raises(GitHubError) as failed:
            GitHub("o/r").pull_body(5)
        assert failed.value.what == (
            "cannot run gh (No such file or directory); install it from"
            " https://cli.github.com"
        )
