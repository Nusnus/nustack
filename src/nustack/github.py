"""GitHub, through the gh command: the pull requests and releases the workflows act on.

gh takes its host and token from the environment, as the workflows set them. A
command that fails stops with an error naming the fix beside what gh printed.
"""

import json
import subprocess
from dataclasses import dataclass
from typing import ClassVar
lazy from pathlib import Path


class GitHubError(Exception):
    """A gh command failed; what it printed names why."""

    def __init__(self, what: str) -> None:
        super().__init__(what)
        self.what = what


@dataclass(frozen=True)
class GitHub:
    """One repository's pull requests and releases, read and changed through gh."""

    # gh reports a missing release as exactly this:
    # https://github.com/cli/cli/blob/v2.103.3/pkg/cmd/release/shared/fetch.go
    NO_RELEASE: ClassVar[str] = "release not found"
    repository: str

    def default_branch(self) -> str:
        name = self.run(
            "api", f"repos/{self.repository}", "--jq", ".default_branch"
        ).strip()
        if not name:
            what = (
                f"gh names no default branch for {self.repository}; check that the"
                " token can read the repository"
            )
            raise GitHubError(what)
        return name

    # The lookup sends the base and the owner-qualified branch as query fields, so
    # any branch name stays one value, pages through every match, and keeps those
    # whose head is this repository, since a fork in the same organization has the
    # same owner: https://docs.github.com/en/rest/pulls/pulls#list-pull-requests
    def open_pulls(self, base: str, branch: str) -> tuple[int, ...]:
        owner = self.repository.split("/")[0]
        numbers = self.run(
            "api",
            "--method",
            "GET",
            "--paginate",
            f"repos/{self.repository}/pulls",
            "-f",
            "state=open",
            "-f",
            f"base={base}",
            "-f",
            f"head={owner}:{branch}",
            "--jq",
            ".[] | select(.head.repo.id == .base.repo.id) | .number",
        )
        return tuple(int(number) for number in numbers.split())

    def pull_body(self, number: int) -> str:
        return self.run(
            "api", f"repos/{self.repository}/pulls/{number}", "--jq", ".body"
        )

    def create_pull(self, base: str, branch: str, title: str, body: str) -> None:
        self.run(
            "pr",
            "create",
            "-R",
            self.repository,
            "--base",
            base,
            "--head",
            branch,
            "--title",
            title,
            "--body-file",
            "-",
            stdin=body,
        )

    def edit_pull(self, number: int, body: str) -> None:
        self.run(
            "pr",
            "edit",
            str(number),
            "-R",
            self.repository,
            "--body-file",
            "-",
            stdin=body,
        )

    def close_pull(self, number: int, comment: str) -> None:
        self.run(
            "pr",
            "close",
            str(number),
            "-R",
            self.repository,
            "--delete-branch",
            "--comment",
            comment,
        )

    def tag_commit(self, tag: str) -> str:
        return self.run(
            "api", f"repos/{self.repository}/commits/tags/{tag}", "--jq", ".sha"
        ).strip()

    def release_draft(self, tag: str) -> bool | None:
        viewed = self.complete(
            "release",
            "view",
            tag,
            "-R",
            self.repository,
            "--json",
            "isDraft",
            "--jq",
            ".isDraft",
            stderr=subprocess.PIPE,
        )
        if viewed.returncode == 0:
            return json.loads(viewed.stdout) is True
        if viewed.stderr.strip() == self.NO_RELEASE:
            return None
        what = (
            f"release {tag} cannot be read ({viewed.stderr.strip()}); rerun once"
            " GitHub answers"
        )
        raise GitHubError(what)

    def create_draft(self, tag: str) -> None:
        self.run(
            "release",
            "create",
            tag,
            "-R",
            self.repository,
            "--draft",
            "--verify-tag",
            "--notes",
            "",
        )

    def upload(self, tag: str, assets: tuple[Path, ...]) -> None:
        self.run(
            "release",
            "upload",
            tag,
            "-R",
            self.repository,
            *map(str, assets),
            "--clobber",
        )

    def publish(self, tag: str, title: str, notes: Path) -> None:
        self.run(
            "release",
            "edit",
            tag,
            "-R",
            self.repository,
            "--draft=false",
            "--title",
            title,
            "--notes-file",
            str(notes),
        )

    def run(self, *args: str, stdin: str = "") -> str:
        completed = self.complete(*args, stdin=stdin)
        if completed.returncode != 0:
            what = (
                f"gh {args[0]} exited {completed.returncode}; fix the cause gh printed"
                " above, then rerun"
            )
            raise GitHubError(what)
        return completed.stdout

    def complete(
        self,
        *args: str,
        # Only the commands given input read it, so no test tells the default from
        # another value.
        stdin: str = "",  # pragma: no mutate
        stderr: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(  # noqa: S603 -- argv only, no shell
                ["gh", *args],  # noqa: S607 -- the runner's gh
                input=stdin,
                stdout=subprocess.PIPE,
                # Ruff asks for check, and the caller reads the exit status; False is
                # subprocess.run's default, so no mutant of it acts differently:
                # https://docs.astral.sh/ruff/rules/subprocess-run-without-check/
                check=False,  # pragma: no mutate
                stderr=stderr,
                text=True,
            )
        except OSError as error:
            what = (
                f"cannot run gh ({error.strerror}); install it from"
                " https://cli.github.com"
            )
            raise GitHubError(what) from error
