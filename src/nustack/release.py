"""A release: its tag held to main and the plugin version, then published on GitHub.

Publishing drafts the release, uploads the zip and publishes it with the notes,
only while the tag still names the commit CI passed on; a published release stays
as it is.
"""

from dataclasses import dataclass
from pathlib import Path

from nustack.github import GitHub
from nustack.github import GitHubError
from nustack.problem import Problem


@dataclass(frozen=True)
class Tag:
    """A pushed v<version> tag, which publishes from main and the declared version."""

    name: str

    def problems(self, version: str, *, on_main: bool) -> list[Problem]:
        problems = []
        if not on_main:
            problems.append(
                Problem(
                    Path(self.name),
                    "is not on main; delete it and tag the commit the squash merge made"
                    " on main",
                )
            )
        if self.name != f"v{version}":
            problems.append(
                Problem(
                    Path(self.name),
                    f"does not match plugin version {version}; delete it and tag"
                    f" v{version}, or set the version as AGENTS.md's Releases section"
                    " says",
                )
            )
        return problems


@dataclass(frozen=True)
class Publication:
    """The GitHub release for a tag, from the zip and notes CI built on its commit."""

    tag: str
    commit: str
    folder: Path

    def publish(self, github: GitHub) -> str | Problem:
        try:
            if (moved := self.moved(github)) is not None:
                return moved
            draft = github.release_draft(self.tag)
            if draft is None:
                github.create_draft(self.tag)
            elif not draft:
                return f"Release {self.tag} is already published, so it stays as it is"
            github.upload(self.tag, tuple(sorted(self.folder.glob("*.zip"))))
            if (moved := self.moved(github)) is not None:
                return moved
            github.publish(
                self.tag,
                f"nustack {self.tag.removeprefix('v')}",
                self.folder / "notes.md",
            )
        except GitHubError as error:
            return Problem(Path(self.tag), error.what)
        return f"Published release {self.tag}"

    def moved(self, github: GitHub) -> Problem | None:
        try:
            tagged = github.tag_commit(self.tag)
        except GitHubError as error:
            return Problem(
                Path(self.tag),
                f"cannot be read ({error.what}); push it again if it was deleted, then"
                " rerun",
            )
        if tagged == self.commit:
            return None
        return Problem(
            Path(self.tag),
            "has moved off the commit CI passed on; the run the move started"
            " publishes it",
        )
