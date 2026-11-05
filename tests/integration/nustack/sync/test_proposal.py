"""The sync's pull request follows the copy: opened, updated, kept or closed.

These tests run on real Git repositories and a gh that replays GitHub's replies. A close
that fails keeps the branch.
"""

from pathlib import PurePosixPath
lazy from pathlib import Path

import pytest

from nustack.github.gh import GitHub
from nustack.github.gh import GitHubError
from nustack.problem import Problem
from nustack.record import CopyRecord
from nustack.sync.git import CopyGit
from nustack.sync.proposal import Proposal
from tests.fixtures.gh import GhArgv
lazy from tests.fixtures.gh import FakeGh
lazy from tests.fixtures.sync.repositories import Sync


class TestProposal:
    """One pull request proposes the newest copy, and none once the copy matches.

    Two pull requests proposing the branch stop the sync. A close that fails keeps
    the branch.
    """

    RECORD = CopyRecord(
        upstream="https://github.com/mattpocock/skills",
        source="skills",
        folder=".agents/skills",
        skills=("writing-for-agents",),
        commit=None,
        files=frozendict(),
    )
    BODY = "- [Copy](https://x.io/runs/2): passed.\n"
    CREATE = (
        "pr",
        "create",
        "-R",
        "o/r",
        "--base",
        "main",
        "--head",
        "sync/w",
        "--title",
        "docs: sync writing-for-agents from mattpocock/skills",
        "--body-file",
        "-",
    )
    EDIT = ("pr", "edit", "267", "-R", "o/r", "--body-file", "-")

    @pytest.fixture
    def checkout_git(self, sync: Sync) -> CopyGit:
        return CopyGit(sync.checkout.root)

    @pytest.fixture
    def staged(self, sync: Sync, checkout_git: CopyGit) -> None:
        upstream_git = CopyGit(sync.upstream.root)
        checkout_git.stage(
            sync.RECORD,
            sync.record,
            sync.second,
            upstream_git,
            upstream_git.tree("HEAD", [sync.SOURCE_FOLDER], "LICENSE"),
        )

    @pytest.fixture
    def proposal(self, remote_url: str) -> Proposal:
        return Proposal("main", "sync/w", remote_url)

    @pytest.fixture
    def one_pull(self, gh: FakeGh, github_fixtures: Path) -> None:
        gh.replay(*GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/one.json")

    def test_stops_when_more_than_one_pull_request_proposes_the_branch(
        self,
        gh: FakeGh,
        github_fixtures: Path,
        checkout_git: CopyGit,
        proposal: Proposal,
    ) -> None:
        gh.replay(
            *GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/several.json"
        )
        outcome = proposal.propose(
            "writing-for-agents",
            self.RECORD,
            checkout_git,
            GitHub(GhArgv.REPOSITORY),
            self.BODY,
        )
        assert outcome == Problem(
            "o/r",
            "has pull requests #267, #265, #264, #259, #258 that all propose sync/w"
            " for main; close all but one, then rerun",
        )

    def test_proposes_nothing_while_the_copy_matches(
        self,
        gh: FakeGh,
        github_fixtures: Path,
        checkout_git: CopyGit,
        proposal: Proposal,
    ) -> None:
        gh.replay(
            *GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/none.json"
        )
        _ = checkout_git.run("push", proposal.remote_url, "HEAD:refs/heads/sync/w")
        outcome = proposal.propose(
            "writing-for-agents",
            self.RECORD,
            checkout_git,
            GitHub(GhArgv.REPOSITORY),
            "",
        )
        assert (
            outcome,
            len(gh.calls),
            checkout_git.run("ls-remote", proposal.remote_url),
        ) == (
            "The copy on main matches upstream; nothing to propose.",
            1,
            b"",
        )

    @pytest.mark.usefixtures("one_pull")
    def test_closes_the_pull_request_once_the_copy_matches_again(
        self, gh: FakeGh, checkout_git: CopyGit, proposal: Proposal
    ) -> None:
        _ = checkout_git.run("push", proposal.remote_url, "HEAD:refs/heads/sync/w")
        outcome = proposal.propose(
            "writing-for-agents",
            self.RECORD,
            checkout_git,
            GitHub(GhArgv.REPOSITORY),
            "",
        )
        assert (
            outcome,
            gh.calls[1:],
            checkout_git.run("ls-remote", proposal.remote_url),
        ) == (
            "Closed pull request #267: the copy matches upstream again.",
            [
                (
                    (
                        "pr",
                        "close",
                        "267",
                        "-R",
                        "o/r",
                        "--comment",
                        (
                            "mattpocock/skills's writing-for-agents matches the copy"
                            " on main again, so this sync proposes nothing."
                        ),
                    ),
                    "",
                )
            ],
            b"",
        )

    @pytest.mark.usefixtures("one_pull")
    def test_keeps_the_branch_while_the_pull_request_stays_open(
        self,
        gh: FakeGh,
        github_fixtures: Path,
        checkout_git: CopyGit,
        proposal: Proposal,
    ) -> None:
        gh.replay(
            "pr",
            "close",
            "267",
            "-R",
            "o/r",
            "--comment",
            "mattpocock/skills's writing-for-agents matches the copy on main again,"
            " so this sync proposes nothing.",
            recording=github_fixtures / "pull-close/unauthorized.json",
        )
        _ = checkout_git.run("push", proposal.remote_url, "HEAD:refs/heads/sync/w")
        with pytest.raises(GitHubError):
            _ = proposal.propose(
                "writing-for-agents",
                self.RECORD,
                checkout_git,
                GitHub(GhArgv.REPOSITORY),
                "",
            )
        assert checkout_git.run("ls-remote", proposal.remote_url) == (
            f"{checkout_git.head}\trefs/heads/sync/w\n".encode()
        )

    @pytest.mark.usefixtures("staged", "one_pull")
    @pytest.mark.parametrize(
        ("posted", "edits"),
        [
            ("- [Copy](https://x.io/runs/1): passed.\n", []),
            ("Edited.\n", [(EDIT, BODY)]),
        ],
    )
    def test_keeps_a_pull_request_that_proposes_the_copy_editing_only_what_differs(
        self,
        gh: FakeGh,
        checkout_git: CopyGit,
        proposal: Proposal,
        posted: str,
        edits: list[tuple[tuple[str, ...], str]],
    ) -> None:
        checkout_git.push(proposal.remote_url, "sync/w", "docs: sync", "Copies it.")
        _ = checkout_git.run("reset", "-q", "--soft", "HEAD~1")
        # Each row's body is one the sync posts, written by the test.
        gh.reply(*GhArgv.PULL_BODY_267, stdout=posted)
        outcome = proposal.propose(
            "writing-for-agents",
            self.RECORD,
            checkout_git,
            GitHub(GhArgv.REPOSITORY),
            self.BODY,
        )
        assert (outcome, gh.calls[2:]) == (
            "Pull request #267 already proposes this copy on main's head.",
            edits,
        )

    @pytest.mark.usefixtures("staged")
    def test_opens_a_pull_request_for_a_new_copy(
        self,
        gh: FakeGh,
        github_fixtures: Path,
        checkout_git: CopyGit,
        proposal: Proposal,
    ) -> None:
        gh.replay(
            *GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/none.json"
        )
        outcome = proposal.propose(
            "writing-for-agents",
            self.RECORD,
            checkout_git,
            GitHub(GhArgv.REPOSITORY),
            self.BODY,
        )
        pushed = checkout_git.run("log", "-1", "--format=%B", "HEAD")
        assert (outcome, gh.calls[1:], pushed) == (
            "Opened a pull request proposing sync/w for main.",
            [(self.CREATE, self.BODY)],
            (
                b"docs: sync writing-for-agents from mattpocock/skills\n\n"
                b"Copies the newest writing-for-agents from mattpocock/skills's"
                b" default branch.\n\n"
            ),
        )

    @pytest.mark.usefixtures("staged")
    def test_titles_a_copy_into_the_plugin_as_a_feature(
        self,
        gh: FakeGh,
        github_fixtures: Path,
        checkout_git: CopyGit,
        proposal: Proposal,
    ) -> None:
        gh.replay(
            *GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/none.json"
        )
        record = self.RECORD.model_copy(
            update={"folder": PurePosixPath("plugin/skills")}
        )
        outcome = proposal.propose(
            "obsidian-skills",
            record,
            checkout_git,
            GitHub(GhArgv.REPOSITORY),
            self.BODY,
        )
        pushed = checkout_git.run("log", "-1", "--format=%B", "HEAD")
        assert (outcome, gh.calls[1:], pushed) == (
            "Opened a pull request proposing sync/w for main.",
            [
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
                        "feat: sync obsidian-skills from mattpocock/skills",
                        "--body-file",
                        "-",
                    ),
                    self.BODY,
                )
            ],
            (
                b"feat: sync obsidian-skills from mattpocock/skills\n\n"
                b"Copies the newest obsidian-skills from mattpocock/skills's"
                b" default branch.\n\n"
            ),
        )

    @pytest.mark.usefixtures("staged", "one_pull")
    def test_updates_the_pull_request_with_a_newer_copy(
        self, gh: FakeGh, sync: Sync, checkout_git: CopyGit, proposal: Proposal
    ) -> None:
        checkout_git.push(proposal.remote_url, "sync/w", "docs: sync", "Copies it.")
        sync.checkout.git("reset", "-q", "--soft", "HEAD~1")
        sync.checkout.write(f"{sync.COPY}/SKILL.md", "newer\n")
        sync.checkout.git("add", f"{sync.COPY}/SKILL.md")
        outcome = proposal.propose(
            "writing-for-agents",
            self.RECORD,
            checkout_git,
            GitHub(GhArgv.REPOSITORY),
            self.BODY,
        )
        pushed = sync.checkout.git(
            "--git-dir", proposal.remote_url, "log", "-1", "--format=%H%n%B", "sync/w"
        )
        assert (outcome, gh.calls[1:], pushed) == (
            "Updated pull request #267 with the new copy.",
            [(self.EDIT, self.BODY)],
            (
                f"{checkout_git.head}\n"
                "docs: sync writing-for-agents from mattpocock/skills\n\n"
                "Copies the newest writing-for-agents from mattpocock/skills's default"
                " branch.\n\n"
            ),
        )
