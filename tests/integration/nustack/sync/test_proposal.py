"""The sync's pull request follows the copy: opened, updated, kept or closed.

It runs on real Git repositories and a gh that replays GitHub's replies.
"""

lazy from pathlib import Path

import pytest

from nustack.github import GitHub
from nustack.problem import Problem
from nustack.sync.git import CopyGit
from nustack.sync.proposal import Proposal
lazy from tests.fixtures.gh import FakeGh
lazy from tests.fixtures.sync.git_repository import Sync


class TestProposal:
    """One pull request proposes the newest copy, and none once the copy matches.

    Two pull requests proposing the branch stop it.
    """

    UPSTREAM = "https://github.com/mattpocock/skills"

    BODY = "| ✅ **[Copy](https://x.io/runs/2)** | Compared. |\n"

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
    def checkout(self, sync: Sync) -> CopyGit:
        return CopyGit(sync.checkout.root)

    @pytest.fixture
    def staged(self, sync: Sync, checkout: CopyGit) -> None:
        upstream = CopyGit(sync.upstream.root)
        checkout.stage(
            sync.FOLDER, upstream, upstream.tree("HEAD", sync.SOURCE, "LICENSE")
        )

    @pytest.fixture
    def proposal(self, remote: str) -> Proposal:
        return Proposal("main", "sync/w", remote)

    @pytest.fixture
    def one_pull(self, gh: FakeGh, github_fixtures: Path) -> None:
        gh.replay(*self.PULLS, recording=github_fixtures / "open-pulls/one.json")

    @pytest.mark.usefixtures("staged")
    def test_opens_a_pull_request_for_a_new_copy(
        self, gh: FakeGh, github_fixtures: Path, checkout: CopyGit, proposal: Proposal
    ) -> None:
        gh.replay(*self.PULLS, recording=github_fixtures / "open-pulls/none.json")
        outcome = proposal.propose(self.UPSTREAM, checkout, GitHub("o/r"), self.BODY)
        pushed = checkout.run("log", "-1", "--format=%s", "HEAD")
        assert (outcome, gh.calls[1:], pushed) == (
            "Opened a pull request proposing sync/w for main.",
            [(self.CREATE, self.BODY)],
            b"docs: sync writing-for-agents from mattpocock/skills\n",
        )

    @pytest.mark.usefixtures("one_pull")
    def test_closes_the_pull_request_once_the_copy_matches_again(
        self, gh: FakeGh, checkout: CopyGit, proposal: Proposal
    ) -> None:
        outcome = proposal.propose(self.UPSTREAM, checkout, GitHub("o/r"), "")
        assert (outcome, gh.calls[1:]) == (
            "Closed pull request #267: the copy matches upstream again.",
            [
                (
                    (
                        "pr",
                        "close",
                        "267",
                        "-R",
                        "o/r",
                        "--delete-branch",
                        "--comment",
                        (
                            "mattpocock/skills's writing-for-agents matches the copy"
                            " on main again, so this sync proposes nothing."
                        ),
                    ),
                    "",
                )
            ],
        )

    @pytest.mark.usefixtures("staged", "one_pull")
    def test_updates_the_pull_request_with_a_newer_copy(
        self, gh: FakeGh, sync: Sync, checkout: CopyGit, proposal: Proposal
    ) -> None:
        checkout.push(proposal.remote, "sync/w", "docs: sync", "Copies it.")
        sync.checkout.git("reset", "-q", "--soft", "HEAD~1")
        sync.checkout.write(f"{sync.FOLDER}/SKILL.md", "newer\n")
        sync.checkout.git("add", f"{sync.FOLDER}/SKILL.md")
        outcome = proposal.propose(self.UPSTREAM, checkout, GitHub("o/r"), self.BODY)
        pushed = sync.checkout.git(
            "--git-dir", proposal.remote, "rev-parse", "refs/heads/sync/w"
        )
        assert (outcome, gh.calls[1:], pushed) == (
            "Updated pull request #267 with the new copy.",
            [(self.EDIT, self.BODY)],
            f"{checkout.head}\n",
        )

    @pytest.mark.usefixtures("staged", "one_pull")
    @pytest.mark.parametrize(
        ("posted", "edits"),
        [
            ("| ✅ **[Copy](https://x.io/runs/1)** | Compared. |\n", []),
            ("Edited.\n", [(EDIT, BODY)]),
        ],
    )
    def test_keeps_a_pull_request_that_proposes_the_copy_editing_only_what_differs(
        self,
        gh: FakeGh,
        checkout: CopyGit,
        proposal: Proposal,
        posted: str,
        edits: list[tuple[tuple[str, ...], str]],
    ) -> None:
        checkout.push(proposal.remote, "sync/w", "docs: sync", "Copies it.")
        checkout.run("reset", "-q", "--soft", "HEAD~1")
        gh.reply("api", "repos/o/r/pulls/267", "--jq", ".body", stdout=posted)
        outcome = proposal.propose(self.UPSTREAM, checkout, GitHub("o/r"), self.BODY)
        assert (outcome, gh.calls[2:]) == (
            "Pull request #267 already proposes this copy on main's head.",
            edits,
        )

    def test_proposes_nothing_while_the_copy_matches(
        self, gh: FakeGh, github_fixtures: Path, checkout: CopyGit, proposal: Proposal
    ) -> None:
        gh.replay(*self.PULLS, recording=github_fixtures / "open-pulls/none.json")
        outcome = proposal.propose(self.UPSTREAM, checkout, GitHub("o/r"), "")
        assert (outcome, len(gh.calls)) == (
            "The copy on main matches upstream; nothing to propose.",
            1,
        )

    def test_stops_when_more_than_one_pull_request_proposes_the_branch(
        self, gh: FakeGh, github_fixtures: Path, checkout: CopyGit, proposal: Proposal
    ) -> None:
        gh.replay(*self.PULLS, recording=github_fixtures / "open-pulls/several.json")
        outcome = proposal.propose(self.UPSTREAM, checkout, GitHub("o/r"), self.BODY)
        assert outcome == Problem(
            Path("o/r"),
            "has pull requests #267, #265, #264, #259, #258 that all propose sync/w"
            " for main; close all but one, then rerun",
        )
