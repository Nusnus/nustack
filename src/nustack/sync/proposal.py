"""The sync's pull request: opened, updated, left as it is or closed, as the copy needs.

Only a pull request from this repository's sync branch counts. A copy equal to the
checkout's closes it and deletes its branch; one it already proposes on the base's
head keeps its reviewed commit, and its description changes only where a reviewer
would see it.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

from nustack.problem import Problem
from nustack.sync.description import SyncDescription
lazy from nustack.github import GitHub
lazy from nustack.sync.git import CopyGit


@dataclass(frozen=True)
class Proposal:
    """A copy of upstream's skill, proposed on one branch for one base."""

    base: str
    branch: str
    remote_url: str

    def propose(
        self, upstream_url: str, checkout_git: CopyGit, github: GitHub, body: str
    ) -> str | Problem:
        upstream_name_with_owner = urlsplit(upstream_url).path.removeprefix("/")
        title = f"docs: sync writing-for-agents from {upstream_name_with_owner}"
        match github.open_pulls(self.base, self.branch):
            case ():
                pull = None
            case (pull,):
                pass
            case pulls:
                numbers = ", ".join(f"#{number}" for number in pulls)
                return Problem(
                    github.name_with_owner,
                    f"has pull requests {numbers} that all propose {self.branch} for"
                    f" {self.base}; close all but one, then rerun",
                )
        if not checkout_git.staged():
            if pull is None:
                checkout_git.withdraw(self.remote_url, self.branch)
                return f"The copy on {self.base} matches upstream; nothing to propose."
            # gh posts the comment, then closes: a run stopped between the two posts
            # it again on rerun, a harmless repeat, where closing first would lose it.
            # The branch goes last, since deleting it closes the pull request:
            # https://docs.github.com/en/pull-requests/how-tos/commit-changes/managing-branches-within-your-repository#deleting-a-branch
            # and gh then posts no comment on a closed one:
            # https://github.com/cli/cli/blob/v2.103.3/pkg/cmd/pr/close/close.go#L80-L109
            github.close_pull(
                pull,
                f"{upstream_name_with_owner}'s writing-for-agents matches the copy on"
                f" {self.base} again, so this sync proposes nothing.",
            )
            checkout_git.withdraw(self.remote_url, self.branch)
            return f"Closed pull request #{pull}: the copy matches upstream again."
        if pull is not None and checkout_git.proposes(self.remote_url, self.branch):
            current = github.pull_body(pull)
            if SyncDescription.differs_beyond_the_run(current, body):
                github.edit_pull(pull, body)
            return (
                f"Pull request #{pull} already proposes this copy on {self.base}'s"
                " head."
            )
        checkout_git.push(
            self.remote_url,
            self.branch,
            title,
            "Copies the newest writing-for-agents skill from"
            f" {upstream_name_with_owner} main.",
        )
        if pull is None:
            github.create_pull(self.base, self.branch, title, body)
            return f"Opened a pull request proposing {self.branch} for {self.base}."
        github.edit_pull(pull, body)
        return f"Updated pull request #{pull} with the new copy."
