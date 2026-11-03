"""The changelog the release publishes its notes from.

Each entry is titled with a version and a real day. Entries run newest first, below an
optional `[Unreleased]` section. The top one, the plugin version's, is the body of the
release page and resolves each reference label it uses the same on its own as in the
file. It gives each link and image a full URL, and holds an optional lead, then its
changes, grouped under Keep a Changelog's types of change in the order that format
lists them, each type once and each group showing something. The release below it is
the one the page compares with. The changelog links each release and the plugin
version to its tag's page, and `[Unreleased]` to the changes since the plugin version.
"""

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import cached_property
from itertools import pairwise
from typing import ClassVar
from typing import Literal

from nustack.problem import Problem
from nustack.repository.page import PagePart
from nustack.validation import Pattern
from nustack.validation import version_order
lazy from nustack.markdown.document import Document
lazy from nustack.markdown.document import Section


class ChangeType(StrEnum):
    """A type of change Keep a Changelog groups an entry by, in the order it lists them.

    https://keepachangelog.com/en/1.1.0/#how
    """

    ADDED = "Added"
    CHANGED = "Changed"
    DEPRECATED = "Deprecated"
    REMOVED = "Removed"
    FIXED = "Fixed"
    SECURITY = "Security"

    @classmethod
    def listed(cls, conjunction: Literal["and", "or"]) -> str:
        *rest, last = cls
        return f"{', '.join(rest)} {conjunction} {last}"


@dataclass(frozen=True)
class Entry:
    """A release's entry: an optional lead, then its changes under third-level groups.

    The entry is read in the changelog it sits in, so its text is the changelog's.
    The lead is the text above the first group.
    """

    changelog: Document
    release: Section

    @property
    def body(self) -> str:
        return self.release.body

    @cached_property
    def groups(self) -> tuple[Section, ...]:
        return tuple(
            each for each in self.changelog.headed(3) if self.release.holds(each.start)
        )

    @cached_property
    def split(self) -> int:
        return self.groups[0].start if self.groups else self.release.end

    @property
    def lead(self) -> str:
        return self.changelog.text_between(self.release.body_start, self.split)

    @property
    def changes(self) -> str:
        return self.changelog.text_between(self.split, self.release.end)


@dataclass(frozen=True)
class Changelog:
    """The changelog's entries, newest first, each titled with its version and day."""

    UNRELEASED: ClassVar[str] = "[Unreleased]"
    ENTRY: ClassVar[re.Pattern[str]] = re.compile(
        rf"\[(?P<version>{Pattern.VERSION.unanchored})\] - "
        r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
    )
    document: Document

    @cached_property
    def releases(self) -> tuple[Section, ...]:
        sections = self.document.sections
        if sections and sections[0].title.casefold() == self.UNRELEASED.casefold():
            return sections[1:]
        return sections

    @cached_property
    def titles(self) -> tuple[tuple[str, re.Match[str] | None], ...]:
        return tuple(
            (section.title, self.ENTRY.fullmatch(section.title))
            for section in self.releases
        )

    @cached_property
    def titled(self) -> tuple[re.Match[str], ...]:
        return tuple(entry for _, entry in self.titles if entry is not None)

    @cached_property
    def top(self) -> re.Match[str] | None:
        return self.titles[0][1] if self.titles else None

    @property
    def previous(self) -> str | None:
        return self.titled[1]["version"] if len(self.titled) > 1 else None

    @cached_property
    def entry(self) -> Entry:
        return Entry(self.document, self.releases[0])

    def problems(self, version: str | None) -> list[Problem]:
        path = self.document.path
        sections = self.document.sections
        problems: list[Problem] = []
        if self.releases != sections and sections[0].title != self.UNRELEASED:
            problems.append(
                Problem(
                    path,
                    f"titles its {self.UNRELEASED} section {sections[0].title!r}; "
                    f"spell it {self.UNRELEASED}",
                )
            )
        problems += [
            Problem(
                path,
                f"has an {self.UNRELEASED} section below a release; "
                "move it above the releases",
            )
            if title.casefold() == self.UNRELEASED.casefold()
            else Problem(
                path,
                f"has an entry titled {title!r}; "
                "title it '[<version>] - <YYYY-MM-DD>' with the release's version",
            )
            if entry is None
            else Problem(
                path,
                f"has an entry dated {entry['date']}, which is no real day; "
                "date it with the release day",
            )
            for title, entry in self.titles
            if entry is None or not is_date(entry["date"])
        ]
        versions = [entry["version"] for entry in self.titled]
        problems += [
            Problem(path, f"has more than one entry for {each}; merge them into one")
            for each in sorted({each for each in versions if versions.count(each) > 1})
        ]
        problems += [
            Problem(
                path,
                f"has the entry for {above['version']} above the one for "
                f"{below['version']}; list releases newest first, by version",
            )
            for above, below in pairwise(self.titled)
            if version_order(above["version"]) < version_order(below["version"])
        ]
        problems += [
            Problem(
                path,
                f"has the entry dated {above['date']} above the one dated "
                f"{below['date']}; list releases newest first, by date",
            )
            for above, below in pairwise(self.titled)
            if above["date"] < below["date"]
        ]
        if version is None:
            return problems
        if self.top is None and problems:
            return problems
        if not self.opens_with(version):
            return [
                *problems,
                Problem(
                    path,
                    f"does not open with the entry for {version}; "
                    + self.opening(version),
                ),
            ]
        part = self.entry_part(version)
        problems += part.problems
        if part.shows:
            problems += self.group_problems(version)
        return problems

    def opens_with(self, version: str) -> bool:
        return self.top is not None and self.top["version"] == version

    def opening(self, version: str) -> str:
        if self.releases != self.document.sections:
            return (
                f"retitle its {self.UNRELEASED} section '[{version}] - <release date>'"
            )
        return f"add a '## [{version}] - <release date>' section above the releases"

    def entry_part(self, version: str) -> PagePart:
        return PagePart(
            self.document,
            self.entry.release,
            f"the entry for {version}",
            "list what the release changes under it, which the release page copies",
        )

    def group_problems(self, version: str) -> list[Problem]:
        path = self.document.path
        groups = self.entry.groups
        if not groups:
            return [
                Problem(
                    path,
                    f"lists the changes in the entry for {version} under no group; "
                    f"group them under '### <type>' headings, each one of "
                    f"{ChangeType.listed('or')}, as Keep a Changelog does",
                )
            ]
        types = list(ChangeType)
        known = [
            ChangeType(group.title) for group in groups if group.title in ChangeType
        ]
        return [
            *(
                Problem(
                    path,
                    f"has a group titled {group.title!r} in the entry for {version}; "
                    f"title it {ChangeType.listed('or')}, as Keep a Changelog does",
                )
                for group in groups
                if group.title not in ChangeType
            ),
            *(
                Problem(
                    path,
                    f"has more than one {title} group in the entry for {version}; "
                    "merge them into one",
                )
                for title in sorted(
                    {each for each in known if known.count(each) > 1}, key=types.index
                )
            ),
            *(
                Problem(
                    path,
                    f"has the {above} group above the {below} group in the entry for "
                    f"{version}; order the groups {ChangeType.listed('and')}, as Keep a"
                    " Changelog lists them",
                )
                for above, below in dict.fromkeys(pairwise(known))
                if types.index(above) > types.index(below)
            ),
            *(
                Problem(
                    path,
                    f"shows nothing in the {group.title} group of the entry for"
                    f" {version}; list its changes under it, or remove it",
                )
                for group in groups
                if not self.document.shows(group.body)
            ),
        ]

    def link_problems(self, repository_url: str, version: str) -> list[Problem]:
        if not self.releases:
            return []
        versions = [*(entry["version"] for entry in self.titled), version]
        # markdown-it keys each link reference by its label in upper case, and a
        # version holds no letter:
        # https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/markdown_it/common/utils.py
        targets = {
            (each, each): f"{repository_url}/releases/tag/v{each}" for each in versions
        }
        if self.releases != self.document.sections:
            targets["UNRELEASED", "Unreleased"] = (
                f"{repository_url}/compare/v{version}...HEAD"
            )
        references = self.document.references
        return [
            Problem(
                self.document.path,
                f"has no link for [{shown}]; add '[{shown}]: {target}' above the"
                " first ## heading",
            )
            if label not in references
            else Problem(
                self.document.path,
                f"links [{shown}] to {references[label]}; link it to {target}",
            )
            for (label, shown), target in targets.items()
            if references.get(label) != target
        ]


def is_date(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True
