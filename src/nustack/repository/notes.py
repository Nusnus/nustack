"""The release page: the notes GitHub shows under a release's title.

The page opens with what the plugin is, then the changelog entry's lead and its
changes, README's install and use steps and, from the second release on, a link to
every change since the previous one, so it reads well to someone who never saw the
repository. It leaves out README's third step, which turns nus-mode on for every
session in a project: installing and using it is all a reader needs to try the
release, and the repository the page's first line links holds the rest.
"""

from dataclasses import dataclass
from typing import ClassVar

lazy from nustack.markdown.document import Section
lazy from nustack.plugin.manifest import Manifest
lazy from nustack.repository.changelog import Entry
lazy from nustack.repository.page import PageStep


@dataclass(frozen=True)
class ReleaseNotes:
    """One release's page, from its manifest, its changelog entry and the README."""

    CHANGES_HEADING: ClassVar[str] = "## 🆕 What's new"
    PAGE_STEPS_HEADING: ClassVar[str] = "## 🚀 Quick start"
    manifest: Manifest
    entry: Entry
    page_steps: frozendict[PageStep, Section]
    previous: str | None

    @property
    def about(self) -> str:
        name, description = self.manifest.name, self.manifest.description
        return f"> **[{name}]({self.manifest.repository_url})** · {description}"

    @property
    def compared(self) -> str | None:
        if self.previous is None:
            return None
        span = f"v{self.previous}...v{self.manifest.version}"
        comparison = f"{self.manifest.repository_url}/compare/{span}"
        return f"**Full changelog:** [`{span}`]({comparison})"

    @property
    def text(self) -> str:
        parts = (
            self.about,
            self.entry.lead,
            self.CHANGES_HEADING,
            self.entry.changes,
            self.PAGE_STEPS_HEADING,
            *(
                f"{step.heading}\n\n{section.body}"
                for step, section in self.page_steps.items()
            ),
            self.compared,
        )
        return "\n\n".join(part for part in parts if part)
