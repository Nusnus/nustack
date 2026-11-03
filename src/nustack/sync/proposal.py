"""The sync's pull request: opened, updated, left as it is or closed, as the copy needs.

Only a pull request from this repository's sync branch counts. A copy equal to the
checkout's closes it and deletes its branch; one it already proposes on the base's
head keeps its reviewed commit, and its description changes only where a reviewer
would see it.
"""

from dataclasses import dataclass
from pathlib import Path
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
    remote: str

    def propose(
        self, upstream: str, checkout: CopyGit, github: GitHub, body: str
    ) -> str | Problem:
        source = urlsplit(upstream).path.removeprefix("/")
        title = f"docs: sync writing-for-agents from {source}"
        match github.open_pulls(self.base, self.branch):
            case ():
                pull = None
            case (pull,):
                pass
            case pulls:
                numbers = ", ".join(f"#{number}" for number in pulls)
                return Problem(
                    Path(github.repository),
                    f"has pull requests {numbers} that all propose {self.branch} for"
                    f" {self.base}; close all but one, then rerun",
                )
        if not checkout.staged():
            if pull is None:
                return f"The copy on {self.base} matches upstream; nothing to propose."
            github.close_pull(
                pull,
                f"{source}'s writing-for-agents matches the copy on {self.base}"
                " again, so this sync proposes nothing.",
            )
            return f"Closed pull request #{pull}: the copy matches upstream again."
        if pull is not None and checkout.proposes(self.remote, self.branch):
            current = github.pull_body(pull)
            if SyncDescription.differs_beyond_the_run(current, body):
                github.edit_pull(pull, body)
            return (
                f"Pull request #{pull} already proposes this copy on {self.base}'s"
                " head."
            )
        checkout.push(
            self.remote,
            self.branch,
            title,
            f"Copies the newest writing-for-agents skill from {source} main.",
        )
        if pull is None:
            github.create_pull(self.base, self.branch, title, body)
            return f"Opened a pull request proposing {self.branch} for {self.base}."
        github.edit_pull(pull, body)
        return f"Updated pull request #{pull} with the new copy."
