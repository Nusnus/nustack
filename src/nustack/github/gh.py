"""GitHub, through the gh command: the pull requests and releases the workflows act on.

A release's state reads as missing, draft or published. gh takes its host and token
from the environment, as the workflows set them. A command that fails, outlasts its
time limit or prints output the harness cannot read stops with an error naming the
fix beside what gh printed.
"""

import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar
lazy from pathlib import Path

from nustack import process_group
from nustack.sha import NotSha1Error
from nustack.sha import Sha
lazy from nustack.github.name import NameWithOwner
lazy from nustack.release.tag import Tag


class ReleaseState(Enum):
    """Where a tag's GitHub release stands."""

    MISSING = "missing"
    DRAFT = "draft"
    PUBLISHED = "published"


class GitHubError(Exception):
    """A gh command that failed, stalled or printed unreadable output, with the fix."""

    def __init__(self, what: str) -> None:
        super().__init__(what)
        self.what = what


@dataclass(frozen=True)
class GitHub:
    """One repository's pull requests and releases, read and changed through gh."""

    # gh reports a missing release as exactly this:
    # https://github.com/cli/cli/blob/v2.103.3/pkg/cmd/release/shared/fetch.go
    NO_RELEASE: ClassVar[str] = "release not found"
    # GitHub numbers each pull request with decimal digits:
    # https://docs.github.com/rest/pulls/pulls#get-a-pull-request
    PULL_REQUEST_NUMBER: ClassVar[str] = "[0-9]+"
    # GitHub answers a tag it cannot find so, as
    # tests/fixtures/github/tag-commit/missing.json records:
    # https://docs.github.com/rest/commits/commits#get-a-commit
    NO_COMMIT: ClassVar[str] = "No commit found for SHA"
    name_with_owner: NameWithOwner
    # Each command, a few API calls or one small upload, takes seconds when GitHub
    # is healthy; a minute leaves room for a slow answer and still stops a stalled one.
    timeout: float = 60

    def default_branch(self) -> str:
        name = self.run(
            "api", f"repos/{self.name_with_owner}", "--jq", ".default_branch"
        ).strip()
        if not name:
            what = (
                f"gh names no default branch for {self.name_with_owner}; check that the"
                " token can read the repository"
            )
            raise GitHubError(what)
        return name

    # The lookup sends the base and the owner-qualified branch as query fields, so
    # any branch name stays one value, pages through every match, and keeps those
    # whose head is this repository, since a fork in the same organization has the
    # same owner: https://docs.github.com/en/rest/pulls/pulls#list-pull-requests
    def open_pulls(self, base: str, branch: str) -> tuple[int, ...]:
        printed = self.run(
            "api",
            "--method",
            "GET",
            "--paginate",
            f"repos/{self.name_with_owner}/pulls",
            "-f",
            "state=open",
            "-f",
            f"base={base}",
            "-f",
            f"head={self.name_with_owner.owner}:{branch}",
            "--jq",
            ".[] | select(.head.repo.id == .base.repo.id) | .number",
        )
        numbers = printed.split()
        for number in numbers:
            if re.fullmatch(self.PULL_REQUEST_NUMBER, number) is None:
                what = (
                    f"an open pull request from {branch} into {base} has no number (gh"
                    " printed other than digits for it); rerun once GitHub answers"
                )
                raise GitHubError(what)
        return tuple(map(int, numbers))

    def pull_body(self, number: int) -> str:
        return self.run(
            "api", f"repos/{self.name_with_owner}/pulls/{number}", "--jq", ".body"
        )

    def create_pull(self, base: str, branch: str, title: str, body: str) -> None:
        self.run(
            "pr",
            "create",
            "-R",
            str(self.name_with_owner),
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
            str(self.name_with_owner),
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
            str(self.name_with_owner),
            "--comment",
            comment,
        )

    def tag_commit(self, tag: Tag) -> Sha:
        args = (
            "api",
            f"repos/{self.name_with_owner}/commits/tags/{tag}",
            "--jq",
            ".sha",
        )
        completed = self.complete(*args)
        if completed.returncode != 0:
            if self.NO_COMMIT in completed.stdout:
                what = (
                    "names no commit GitHub can find; push it again if it was deleted,"
                    " then rerun"
                )
                raise GitHubError(what)
            raise self.exited(args[0], completed.returncode)
        try:
            return Sha(completed.stdout.strip())
        except NotSha1Error:
            what = (
                "names no commit (gh printed other than a SHA for it); rerun once"
                " GitHub answers"
            )
            raise GitHubError(what) from None

    def release_state(self, tag: Tag) -> ReleaseState:
        viewed = self.complete(
            "release",
            "view",
            str(tag),
            "-R",
            str(self.name_with_owner),
            "--json",
            "isDraft",
            "--jq",
            ".isDraft",
            capture_stderr=True,
        )
        if viewed.returncode == 0:
            match viewed.stdout.strip():
                case "true":
                    return ReleaseState.DRAFT
                case "false":
                    return ReleaseState.PUBLISHED
                case _:
                    what = (
                        "its release reads as neither a draft nor published (gh"
                        " printed other than true or false for isDraft); rerun once"
                        " GitHub answers"
                    )
                    raise GitHubError(what)
        if viewed.stderr.strip() == self.NO_RELEASE:
            return ReleaseState.MISSING
        what = (
            f"its release cannot be read ({viewed.stderr.strip()}); fix the cause gh"
            " names, or rerun once GitHub answers"
        )
        raise GitHubError(what)

    def create_draft(self, tag: Tag) -> None:
        self.run(
            "release",
            "create",
            str(tag),
            "-R",
            str(self.name_with_owner),
            "--draft",
            "--verify-tag",
            "--notes",
            "",
        )

    def upload(self, tag: Tag, assets: tuple[Path, ...]) -> None:
        self.run(
            "release",
            "upload",
            str(tag),
            "-R",
            str(self.name_with_owner),
            *map(str, assets),
            "--clobber",
        )

    def publish(self, tag: Tag, title: str, notes: Path, *, prerelease: bool) -> None:
        self.run(
            "release",
            "edit",
            str(tag),
            "-R",
            str(self.name_with_owner),
            "--draft=false",
            "--prerelease" if prerelease else "--prerelease=false",
            "--title",
            title,
            "--notes-file",
            str(notes),
        )

    def run(self, *args: str, stdin: str = "") -> str:
        completed = self.complete(*args, stdin=stdin)
        if completed.returncode != 0:
            raise self.exited(args[0], completed.returncode)
        return completed.stdout

    @staticmethod
    def exited(command: str, code: int) -> GitHubError:
        return GitHubError(
            f"gh {command} exited {code}; fix the cause gh printed above, then rerun"
        )

    def complete(
        self,
        *args: str,
        stdin: str = "",
        capture_stderr: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return process_group.run(
                ["gh", *args],
                timeout=self.timeout,
                stdin=stdin,
                stderr=subprocess.PIPE if capture_stderr else None,
                cwd=None,
                env=None,
            )
        except OSError as error:
            what = (
                f"cannot run gh ({error.strerror}); install it from"
                " https://cli.github.com"
            )
            raise GitHubError(what) from error
        except subprocess.TimeoutExpired as error:
            what = (
                f"gh {args[0]} took over {self.timeout:g} seconds; rerun once GitHub"
                " answers"
            )
            raise GitHubError(what) from error
