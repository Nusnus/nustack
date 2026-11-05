"""A release published on GitHub from its tag, as the tag's rules allow.

Publishing drafts the release, uploads the zip and publishes it with the notes, as a
pre-release before v0.1.0, only while the tag still names the commit CI passed on; a
published release stays as it is.
"""

from dataclasses import dataclass
from typing import assert_never
lazy from pathlib import Path

from nustack.github.gh import GitHub
from nustack.github.gh import GitHubError
from nustack.github.gh import ReleaseState
from nustack.problem import Problem
lazy from nustack.release.tag import Tag
lazy from nustack.sha import Sha


@dataclass(frozen=True)
class Publication:
    """The GitHub release for a tag, from the zip and notes CI built on its commit."""

    tag: Tag
    commit: Sha
    zip_folder: Path

    def publish(self, github: GitHub) -> str | Problem:
        try:
            if (moved := self.moved(github)) is not None:
                return moved
            match github.release_state(self.tag):
                case ReleaseState.MISSING:
                    github.create_draft(self.tag)
                case ReleaseState.DRAFT:
                    pass
                case ReleaseState.PUBLISHED:
                    return (
                        f"Release {self.tag} is already published, so it stays as it is"
                    )
                case unexpected:
                    assert_never(unexpected)
            github.upload(self.tag, tuple(sorted(self.zip_folder.glob("*.zip"))))
            if (moved := self.moved(github)) is not None:
                return moved
            github.publish(
                self.tag,
                f"nustack {self.tag.version}",
                self.zip_folder / "notes.md",
                prerelease=self.tag.prerelease,
            )
        except GitHubError as error:
            return Problem(str(self.tag), error.what)
        return f"Published release {self.tag}"

    def moved(self, github: GitHub) -> Problem | None:
        return self.tag.moved(self.commit, github.tag_commit(self.tag))
